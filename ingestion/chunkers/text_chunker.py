"""
Text Chunker
Splits parsed documents into overlapping chunks
ready for embedding.
512 tokens per chunk, 50 token overlap.
"""

import json
import re
import boto3
import tiktoken
from datetime import datetime

S3_CLIENT        = boto3.client("s3", region_name="ca-central-1")
PROCESSED_BUCKET = "banking-rag-processed-docs-418272768931"
ENCODING         = tiktoken.get_encoding("cl100k_base")

CHUNK_SIZE    = 512   # tokens per chunk
CHUNK_OVERLAP = 50    # overlap between chunks


def count_tokens(text: str) -> int:
    """Count tokens in a text string."""
    return len(ENCODING.encode(text))


def split_into_chunks(text: str, source_info: dict) -> list:
    """
    Split text into overlapping chunks of CHUNK_SIZE tokens.
    Each chunk includes metadata about where it came from.
    """
    # Split into sentences first for cleaner chunks
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks        = []
    current_chunk = []
    current_tokens = 0
    chunk_index   = 0

    for sentence in sentences:
        sentence        = sentence.strip()
        if not sentence:
            continue

        sentence_tokens = count_tokens(sentence)

        # If single sentence exceeds chunk size, split by words
        if sentence_tokens > CHUNK_SIZE:
            words       = sentence.split()
            word_chunk  = []
            word_tokens = 0

            for word in words:
                word_tok = count_tokens(word + " ")
                if word_tokens + word_tok > CHUNK_SIZE and word_chunk:
                    chunk_text = " ".join(word_chunk)
                    chunks.append(
                        build_chunk(
                            chunk_text, chunk_index,
                            source_info, current_tokens
                        )
                    )
                    chunk_index  += 1
                    # Keep overlap
                    overlap_words = word_chunk[-10:]
                    word_chunk    = overlap_words
                    word_tokens   = count_tokens(" ".join(overlap_words))

                word_chunk.append(word)
                word_tokens += word_tok

            if word_chunk:
                current_chunk.append(" ".join(word_chunk))
                current_tokens += word_tokens
            continue

        # Normal sentence — add to current chunk
        if current_tokens + sentence_tokens > CHUNK_SIZE and current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(
                build_chunk(
                    chunk_text, chunk_index,
                    source_info, current_tokens
                )
            )
            chunk_index += 1

            # Keep last few sentences for overlap
            overlap_sentences = current_chunk[-3:]
            current_chunk     = overlap_sentences
            current_tokens    = count_tokens(" ".join(overlap_sentences))

        current_chunk.append(sentence)
        current_tokens += sentence_tokens

    # Don't forget the last chunk
    if current_chunk:
        chunk_text = " ".join(current_chunk)
        chunks.append(
            build_chunk(
                chunk_text, chunk_index,
                source_info, current_tokens
            )
        )

    return chunks


def build_chunk(text: str, index: int,
                source_info: dict, token_count: int) -> dict:
    """Build a chunk object with metadata."""
    return {
        "chunk_id":    f"{source_info['doc_id']}_chunk_{index}",
        "doc_id":      source_info["doc_id"],
        "company":     source_info["company"],
        "source_key":  source_info["source_key"],
        "form_type":   source_info.get("form_type", "unknown"),
        "chunk_index": index,
        "text":        text,
        "token_count": token_count,
        "char_count":  len(text),
        "chunked_at":  datetime.utcnow().isoformat()
    }


def chunk_document(parsed_key: str) -> list:
    """
    Download a parsed document from S3 and chunk it.
    Returns list of chunk objects.
    """
    print(f"\nChunking: {parsed_key}")

    # Download parsed document
    response = S3_CLIENT.get_object(
        Bucket=PROCESSED_BUCKET,
        Key=parsed_key
    )
    doc = json.loads(response["Body"].read())

    # Build source info
    parts     = parsed_key.split("/")
    company   = doc.get("company", "unknown")
    form_type = parts[-1].split("_")[0] if parts else "unknown"
    doc_id    = parsed_key.replace("/", "_").replace(".json", "")

    source_info = {
        "doc_id":     doc_id,
        "company":    company,
        "source_key": parsed_key,
        "form_type":  form_type
    }

    # Get full text
    full_text = doc.get("full_text", "")
    if not full_text:
        print(f"  No text found in document")
        return []

    # Chunk the full text
    chunks = split_into_chunks(full_text, source_info)
    print(f"  {doc['word_count']:,} words → {len(chunks)} chunks")
    print(f"  Avg tokens per chunk: "
          f"{sum(c['token_count'] for c in chunks) // max(len(chunks),1)}")

    # Also chunk key sections separately for better retrieval
    section_chunks = []
    for section_name, section_text in doc.get("sections", {}).items():
        if len(section_text) > 100:
            s_info = {
                **source_info,
                "doc_id":   f"{doc_id}_{section_name}",
                "form_type": section_name
            }
            s_chunks = split_into_chunks(section_text, s_info)
            section_chunks.extend(s_chunks)

    all_chunks = chunks + section_chunks
    print(f"  Total chunks (inc. sections): {len(all_chunks)}")
    return all_chunks


def save_chunks(chunks: list, source_key: str) -> str:
    """Save chunks to S3 processed-docs bucket."""
    output_key = source_key.replace(
        "_parsed.json", "_chunks.json"
    )

    S3_CLIENT.put_object(
        Bucket      = PROCESSED_BUCKET,
        Key         = output_key,
        Body        = json.dumps(chunks, ensure_ascii=False),
        ContentType = "application/json"
    )

    print(f"  Saved {len(chunks)} chunks to: "
          f"s3://{PROCESSED_BUCKET}/{output_key}")
    return output_key


def list_parsed_documents() -> list:
    """List all parsed JSON documents in processed-docs bucket."""
    response = S3_CLIENT.list_objects_v2(
        Bucket=PROCESSED_BUCKET
    )
    return [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].endswith("_parsed.json")
    ]


def main():
    print("=" * 60)
    print("Banking RAG — Text Chunker")
    print("=" * 60)

    parsed_docs = list_parsed_documents()
    print(f"\nFound {len(parsed_docs)} parsed documents")

    all_chunk_keys = []
    total_chunks   = 0

    for parsed_key in parsed_docs:
        try:
            chunks     = chunk_document(parsed_key)
            output_key = save_chunks(chunks, parsed_key)
            all_chunk_keys.append(output_key)
            total_chunks += len(chunks)
        except Exception as e:
            print(f"  ERROR chunking {parsed_key}: {e}")

    print("\n" + "=" * 60)
    print(f"Chunking complete!")
    print(f"  Documents chunked: {len(all_chunk_keys)}")
    print(f"  Total chunks:      {total_chunks:,}")
    print("=" * 60)
    for key in all_chunk_keys:
        print(f"  ✅ s3://{PROCESSED_BUCKET}/{key}")


if __name__ == "__main__":
    main()