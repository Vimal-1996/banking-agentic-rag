"""
Chunk Embedder
Reads chunks from S3, generates embeddings using OpenAI,
stores vectors back to S3 with metadata.
Ready to load into OpenSearch in Day 7.
"""

import os
import json
import time
import boto3
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

load_dotenv("/home/vimal/banking-rag/.env")

# ── Clients ────────────────────────────────────────────────
OPENAI_CLIENT    = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
S3_CLIENT        = boto3.client("s3", region_name="ca-central-1")

# ── Config ─────────────────────────────────────────────────
PROCESSED_BUCKET = "banking-rag-processed-docs-418272768931"
EMBEDDING_MODEL  = "text-embedding-3-large"
EMBEDDING_DIMS   = 3072
BATCH_SIZE       = 20    # embed 20 chunks at a time
RATE_LIMIT_DELAY = 0.5   # seconds between batches


def get_embedding(texts: list) -> list:
    """
    Get embeddings for a batch of texts from OpenAI.
    Returns list of vectors (each vector is 3072 floats).
    """
    response = OPENAI_CLIENT.embeddings.create(
        model = EMBEDDING_MODEL,
        input = texts
    )
    return [item.embedding for item in response.data]


def embed_chunks(chunks: list) -> list:
    """
    Embed all chunks in batches.
    Adds embedding vector to each chunk object.
    """
    embedded  = []
    total     = len(chunks)
    batches   = [
        chunks[i:i + BATCH_SIZE]
        for i in range(0, total, BATCH_SIZE)
    ]

    print(f"  Embedding {total} chunks in {len(batches)} batches...")

    for batch_num, batch in enumerate(batches):
        try:
            # Extract text from each chunk
            texts    = [c["text"] for c in batch]

            # Get embeddings from OpenAI
            vectors  = get_embedding(texts)

            # Add embedding to each chunk
            for chunk, vector in zip(batch, vectors):
                chunk["embedding"]       = vector
                chunk["embedding_model"] = EMBEDDING_MODEL
                chunk["embedding_dims"]  = EMBEDDING_DIMS
                chunk["embedded_at"]     = datetime.utcnow().isoformat()
                embedded.append(chunk)

            # Progress update
            done = min((batch_num + 1) * BATCH_SIZE, total)
            print(f"  Progress: {done}/{total} chunks embedded")

            # Rate limit protection
            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            print(f"  ERROR in batch {batch_num}: {e}")
            time.sleep(5)  # wait longer on error
            continue

    return embedded


def list_chunk_files() -> list:
    """List all chunk files in processed-docs bucket."""
    response = S3_CLIENT.list_objects_v2(
        Bucket=PROCESSED_BUCKET
    )
    return [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].endswith("_chunks.json")
    ]


def load_chunks_from_s3(key: str) -> list:
    """Load chunks from S3."""
    response = S3_CLIENT.get_object(
        Bucket=PROCESSED_BUCKET,
        Key=key
    )
    return json.loads(response["Body"].read())


def save_embedded_chunks(chunks: list, source_key: str) -> str:
    """Save embedded chunks to S3."""
    output_key = source_key.replace(
        "_chunks.json",
        "_embedded.json"
    )

    # Save full embedded chunks (with vectors)
    S3_CLIENT.put_object(
        Bucket      = PROCESSED_BUCKET,
        Key         = output_key,
        Body        = json.dumps(chunks, ensure_ascii=False),
        ContentType = "application/json",
        Metadata    = {
            "chunk-count":  str(len(chunks)),
            "model":        EMBEDDING_MODEL,
            "embedded-at":  datetime.utcnow().isoformat()
        }
    )

    print(f"  Saved: s3://{PROCESSED_BUCKET}/{output_key}")
    return output_key


def print_sample(chunk: dict):
    """Print a sample embedded chunk for verification."""
    vector = chunk.get("embedding", [])
    print(f"\n  Sample chunk:")
    print(f"    company:    {chunk.get('company')}")
    print(f"    text:       {chunk.get('text', '')[:100]}...")
    print(f"    dimensions: {len(vector)}")
    print(f"    vector[0]:  {vector[0]:.6f}" if vector else "")


def main():
    print("=" * 60)
    print("Banking RAG — Chunk Embedder")
    print(f"Model: {EMBEDDING_MODEL} ({EMBEDDING_DIMS} dims)")
    print("=" * 60)

    # List all chunk files
    chunk_files = list_chunk_files()
    print(f"\nFound {len(chunk_files)} chunk files:")
    for f in chunk_files:
        print(f"  {f}")

    if not chunk_files:
        print("No chunk files found. Run chunker first.")
        return

    # Process each file
    total_embedded  = 0
    embedded_keys   = []

    for chunk_key in chunk_files:
        print(f"\n{'─' * 50}")
        print(f"Processing: {chunk_key}")

        # Load chunks
        chunks = load_chunks_from_s3(chunk_key)
        print(f"  Loaded {len(chunks)} chunks")

        # Skip if already embedded
        embedded_key = chunk_key.replace(
            "_chunks.json", "_embedded.json"
        )
        try:
            S3_CLIENT.head_object(
                Bucket=PROCESSED_BUCKET,
                Key=embedded_key
            )
            print(f"  Already embedded — skipping ✅")
            embedded_keys.append(embedded_key)
            continue
        except:
            pass  # not yet embedded, continue

        # Embed chunks
        embedded = embed_chunks(chunks)

        # Print sample
        if embedded:
            print_sample(embedded[0])

        # Save to S3
        output_key = save_embedded_chunks(embedded, chunk_key)
        embedded_keys.append(output_key)
        total_embedded += len(embedded)

        # Small delay between documents
        time.sleep(1)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Embedding complete!")
    print(f"  Total chunks embedded: {total_embedded:,}")
    print(f"  Files saved:           {len(embedded_keys)}")
    print(f"  Model:                 {EMBEDDING_MODEL}")
    print(f"  Dimensions:            {EMBEDDING_DIMS}")
    print("=" * 60)
    for key in embedded_keys:
        print(f"  ✅ s3://{PROCESSED_BUCKET}/{key}")


if __name__ == "__main__":
    main()