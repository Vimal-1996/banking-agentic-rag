import os
import re
import json
import boto3
from datetime import datetime
from bs4 import BeautifulSoup

S3_CLIENT = boto3.client("s3", region_name="ca-central-1")

RAW_BUCKET       = "banking-rag-raw-docs-418272768931"
PROCESSED_BUCKET = "banking-rag-processed-docs-418272768931"


def download_from_s3(bucket: str, key: str) -> bytes:
    """Download a file from S3 and return its content."""
    print(f"  Downloading from S3: s3://{bucket}/{key}")
    response = S3_CLIENT.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def clean_text(text: str) -> str:
    """Remove excessive whitespace and clean up text."""
    # Remove multiple spaces
    text = re.sub(r" +", " ", text)
    # Remove multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove page numbers and headers (common in 10-K)
    text = re.sub(r"\n\d+\n", "\n", text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def extract_tables(soup: BeautifulSoup) -> list:
    """Extract tables from HTML document."""
    tables = []
    for i, table in enumerate(soup.find_all("table")):
        rows = []
        for row in table.find_all("tr"):
            cells = [
                cell.get_text(strip=True)
                for cell in row.find_all(["td", "th"])
            ]
            if any(cells):  # skip empty rows
                rows.append(cells)

        if rows:
            tables.append({
                "table_index": i,
                "rows":        rows,
                "row_count":   len(rows)
            })

    return tables


def extract_sections(soup: BeautifulSoup, text: str) -> dict:
    """
    Extract key sections from a 10-K/40-F document.
    These section names are standard across all bank filings.
    """
    sections = {}

    # Common 10-K section markers
    section_markers = {
        "business_overview": [
            "item 1", "business", "overview"
        ],
        "risk_factors": [
            "item 1a", "risk factors", "principal risks"
        ],
        "financial_statements": [
            "item 8", "financial statements",
            "consolidated balance", "consolidated statements"
        ],
        "capital_adequacy": [
            "capital adequacy", "capital ratios",
            "capital requirements", "tier 1", "cet1",
            "basel", "regulatory capital"
        ],
        "liquidity": [
            "liquidity", "funding", "liquidity risk",
            "liquidity coverage"
        ],
        "management_discussion": [
            "item 7", "management", "discussion and analysis",
            "md&a"
        ]
    }

    text_lower = text.lower()

    for section_name, markers in section_markers.items():
        for marker in markers:
            idx = text_lower.find(marker)
            if idx != -1:
                # Extract ~2000 chars from where section starts
                sections[section_name] = text[idx:idx + 2000].strip()
                break

    return sections


def parse_document(key: str) -> dict:
    """
    Main parsing function.
    Downloads from S3, parses HTML, extracts text and tables,
    returns structured document object.
    """
    print(f"\nParsing: {key}")

    # Download from S3
    content = download_from_s3(RAW_BUCKET, key)

    # Parse HTML
    soup = BeautifulSoup(content, "lxml")

    # Remove script and style tags
    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()

    # Extract full text
    raw_text    = soup.get_text(separator="\n")
    clean       = clean_text(raw_text)

    # Extract tables
    tables      = extract_tables(soup)

    # Extract key sections
    sections    = extract_sections(soup, clean)

    # Build metadata from S3 key
    parts       = key.split("/")
    source_type = parts[0]  # sec-filings or regulatory
    company     = parts[1] if len(parts) > 2 else "unknown"
    filename    = parts[-1]

    document = {
        "source_key":   key,
        "company":      company.replace("_", " "),
        "source_type":  source_type,
        "filename":     filename,
        "parsed_at":    datetime.utcnow().isoformat(),
        "full_text":    clean,
        "text_length":  len(clean),
        "word_count":   len(clean.split()),
        "tables":       tables[:20],  # keep first 20 tables
        "table_count":  len(tables),
        "sections":     sections
    }

    print(f"  Extracted {document['word_count']:,} words")
    print(f"  Found {document['table_count']} tables")
    print(f"  Found {len(sections)} sections: {list(sections.keys())}")

    return document


def save_parsed_document(document: dict) -> str:
    """Save parsed document to S3 processed-docs bucket."""
    # Build output key
    original_key = document["source_key"]
    output_key   = original_key.replace(
        ".htm", "_parsed.json"
    ).replace(".html", "_parsed.json")

    # Upload to S3
    S3_CLIENT.put_object(
        Bucket      = PROCESSED_BUCKET,
        Key         = output_key,
        Body        = json.dumps(document, ensure_ascii=False, indent=2),
        ContentType = "application/json",
        Metadata    = {
            "company":    document["company"],
            "word-count": str(document["word_count"]),
            "parsed-at":  document["parsed_at"]
        }
    )

    print(f"  Saved to S3: s3://{PROCESSED_BUCKET}/{output_key}")
    return output_key


def list_raw_documents() -> list:
    """List all documents in the raw-docs S3 bucket."""
    response = S3_CLIENT.list_objects_v2(Bucket=RAW_BUCKET)
    keys = [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].endswith((".htm", ".html", ".pdf"))
    ]
    return keys


def main():
    print("=" * 60)
    print("Banking RAG — Document Parser")
    print("=" * 60)

    # List all raw documents
    keys = list_raw_documents()
    print(f"\nFound {len(keys)} documents to parse:")
    for key in keys:
        print(f"  {key}")

    # Parse each document
    parsed_keys = []
    failed      = []

    for key in keys:
        try:
            document    = parse_document(key)
            output_key  = save_parsed_document(document)
            parsed_keys.append(output_key)
        except Exception as e:
            print(f"  ERROR parsing {key}: {e}")
            failed.append(key)

    # Summary
    print("\n" + "=" * 60)
    print(f"Parsing complete!")
    print(f"  Succeeded: {len(parsed_keys)}")
    print(f"  Failed:    {len(failed)}")
    print("=" * 60)

    for key in parsed_keys:
        print(f"  ✅ s3://{PROCESSED_BUCKET}/{key}")

    if failed:
        for key in failed:
            print(f"  ❌ {key}")


if __name__ == "__main__":
    main()