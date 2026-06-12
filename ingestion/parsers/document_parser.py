"""
Document Parser — Fixed Version
Properly handles SEC EDGAR HTML filings
Strips XBRL, scripts, and machine code
Extracts only human-readable text
"""

import os
import re
import json
import boto3
from datetime import datetime
from bs4 import BeautifulSoup

S3_CLIENT        = boto3.client("s3", region_name="ca-central-1")
RAW_BUCKET       = "banking-rag-raw-docs-418272768931"
PROCESSED_BUCKET = "banking-rag-processed-docs-418272768931"


def download_from_s3(bucket: str, key: str) -> bytes:
    """Download a file from S3 and return its content."""
    print(f"  Downloading from S3: s3://{bucket}/{key}")
    response = S3_CLIENT.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def is_xbrl_line(line: str) -> bool:
    """
    Detect XBRL/machine code lines that should be filtered out.
    XBRL lines look like: us-gaap:SomeMember 2024-12-31
    """
    xbrl_patterns = [
        r"us-gaap:[A-Za-z]+",
        r"[a-z]{2,6}:[A-Za-z]{5,}Member",
        r"\d{4}-\d{2}-\d{2}\s+[a-z]{2,6}:[A-Za-z]",
        r"^[a-z]{2,6}:[A-Za-z]{5,}\s+\d{4}",
        r"xmlns:",
        r"xbrl",
        r"<ix:",
        r"contextRef=",
        r"unitRef=",
    ]
    for pattern in xbrl_patterns:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def clean_text(text: str) -> str:
    """
    Clean extracted text:
    - Remove XBRL machine code lines
    - Remove excessive whitespace
    - Remove page numbers
    - Keep only human readable content
    """
    lines        = text.split("\n")
    clean_lines  = []

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip XBRL machine code
        if is_xbrl_line(line):
            continue

        # Skip lines that are just numbers or dates
        if re.match(r"^[\d\s\-\.\,\$\%]+$", line):
            continue

        # Skip very short meaningless lines
        if len(line) < 10:
            continue

        # Skip lines with too many special characters
        special_char_ratio = len(re.findall(r"[^a-zA-Z0-9\s\.\,\!\?\-\:\;\'\"]", line)) / max(len(line), 1)
        if special_char_ratio > 0.3:
            continue

        clean_lines.append(line)

    # Join and clean whitespace
    text = "\n".join(clean_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def extract_tables(soup: BeautifulSoup) -> list:
    """Extract meaningful tables — skip XBRL data tables."""
    tables = []

    for i, table in enumerate(soup.find_all("table")):
        rows = []
        for row in table.find_all("tr"):
            cells = [
                cell.get_text(strip=True)
                for cell in row.find_all(["td", "th"])
                if cell.get_text(strip=True)
            ]

            # Skip rows that look like XBRL
            if cells and not any(is_xbrl_line(c) for c in cells):
                # Skip rows with only numbers
                non_numeric = [
                    c for c in cells
                    if not re.match(r"^[\d\s\.\,\$\%\(\)]+$", c)
                ]
                if non_numeric:
                    rows.append(cells)

        if len(rows) > 2:  # only keep tables with real content
            tables.append({
                "table_index": i,
                "rows":        rows[:50],  # max 50 rows
                "row_count":   len(rows)
            })

    return tables


def extract_sections(text: str) -> dict:
    """Extract key sections from cleaned text."""
    sections = {}
    text_lower = text.lower()

    section_markers = {
        "business_overview": [
            "item 1.", "item 1 ", "our business",
            "business overview", "company overview"
        ],
        "risk_factors": [
            "item 1a.", "risk factors",
            "principal risks", "key risks"
        ],
        "capital_adequacy": [
            "capital adequacy", "capital ratios",
            "cet1", "tier 1 capital",
            "regulatory capital", "capital requirements",
            "basel iii", "capital conservation"
        ],
        "liquidity": [
            "liquidity coverage", "liquidity risk",
            "funding and liquidity", "liquidity position",
            "lcr", "nsfr"
        ],
        "financial_highlights": [
            "financial highlights", "financial summary",
            "selected financial data",
            "consolidated statements of income"
        ],
        "management_discussion": [
            "item 7.", "management's discussion",
            "management discussion",
            "results of operations"
        ]
    }

    for section_name, markers in section_markers.items():
        for marker in markers:
            idx = text_lower.find(marker)
            if idx != -1:
                # Get surrounding context — 3000 chars
                start = max(0, idx - 100)
                end   = min(len(text), idx + 3000)
                section_text = text[start:end].strip()

                # Only keep if it looks like real content
                words = section_text.split()
                if len(words) > 50:
                    sections[section_name] = section_text
                    break

    return sections


def parse_document(key: str) -> dict:
    """
    Main parsing function.
    Downloads HTML from S3, strips XBRL noise,
    extracts clean human-readable content.
    """
    print(f"\nParsing: {key}")

    # Download from S3
    content = download_from_s3(RAW_BUCKET, key)

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(content, "lxml")

    # Remove all non-content tags
    for tag in soup([
        "script", "style", "meta", "link",
        "head", "ix:header", "ix:hidden",
        "xbrli:xbrl", "xbrl"
    ]):
        tag.decompose()

    # Also remove hidden divs (XBRL data often hidden)
    for tag in soup.find_all(style=re.compile(r"display:\s*none")):
        tag.decompose()

    # Extract text
    raw_text = soup.get_text(separator="\n")
    clean    = clean_text(raw_text)

    # Extract tables
    tables   = extract_tables(soup)

    # Extract sections from clean text
    sections = extract_sections(clean)

    # Build metadata
    parts    = key.split("/")
    company  = parts[1] if len(parts) > 2 else "unknown"

    document = {
        "source_key":  key,
        "company":     company.replace("_", " "),
        "source_type": parts[0],
        "filename":    parts[-1],
        "parsed_at":   datetime.utcnow().isoformat(),
        "full_text":   clean,
        "text_length": len(clean),
        "word_count":  len(clean.split()),
        "tables":      tables[:20],
        "table_count": len(tables),
        "sections":    sections
    }

    print(f"  Extracted {document['word_count']:,} words (clean)")
    print(f"  Found {document['table_count']} tables")
    print(f"  Found sections: {list(sections.keys())}")

    return document


def save_parsed_document(document: dict) -> str:
    """Save parsed document to S3 processed-docs bucket."""
    original_key = document["source_key"]
    output_key   = original_key.replace(
        ".htm", "_parsed.json"
    ).replace(".html", "_parsed.json")

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

    print(f"  Saved: s3://{PROCESSED_BUCKET}/{output_key}")
    return output_key


def list_raw_documents() -> list:
    """List all documents in raw-docs bucket."""
    response = S3_CLIENT.list_objects_v2(Bucket=RAW_BUCKET)
    return [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].endswith((".htm", ".html"))
    ]


def main():
    print("=" * 60)
    print("Banking RAG — Document Parser (Fixed)")
    print("=" * 60)

    keys = list_raw_documents()
    print(f"\nFound {len(keys)} documents to parse:")
    for key in keys:
        print(f"  {key}")

    parsed_keys = []
    failed      = []

    for key in keys:
        try:
            document   = parse_document(key)
            output_key = save_parsed_document(document)
            parsed_keys.append(output_key)
        except Exception as e:
            print(f"  ERROR parsing {key}: {e}")
            failed.append(key)

    print("\n" + "=" * 60)
    print(f"Parsing complete!")
    print(f"  Succeeded: {len(parsed_keys)}")
    print(f"  Failed:    {len(failed)}")
    print("=" * 60)
    for key in parsed_keys:
        print(f"  ✅ s3://{PROCESSED_BUCKET}/{key}")


if __name__ == "__main__":
    main()