import os
import time
import boto3
import requests
from datetime import datetime

HEADERS = {
    "User-Agent": "Banking RAG Project admin@bankingrag.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

S3_CLIENT = boto3.client('s3', region_name="ca-central-1")


def get_company_filings(cik: str, form_type: str = "10-K", count: int = 1):
    """
    Fetch filing metadata from SEC EDGAR for a given company.
    CIK = Central Index Key (unique company identifier on SEC)
    """
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    data        = response.json()
    filings     = data["filings"]["recent"]
    forms       = filings["form"]
    accessions  = filings["accessionNumber"]
    filing_dates = filings["filingDate"]
    primary_docs = filings["primaryDocument"]

    results = []
    for i, form in enumerate(forms):
        if form == form_type and len(results) < count:
            results.append({
                "cik":          cik,
                "company":      data["name"],
                "form":         form,
                "date":         filing_dates[i],
                "accession":    accessions[i].replace("-", ""),
                "primary_doc":  primary_docs[i]
            })

    return results

def download_filing(filing: dict) -> str:
    """Download the actual filing document and save locally."""
    cik       = filing["cik"].zfill(10)
    accession = filing["accession"]
    doc       = filing["primary_doc"]

    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{doc}"
    print(f"  Downloading: {filing['company']} {filing['form']} ({filing['date']})")
    print(f"  URL: {url}")

    response = requests.get(url, headers={
        "User-Agent": "Banking RAG Project admin@bankingrag.com"
    })
    response.raise_for_status()

    # Save locally
    os.makedirs("../../data/raw", exist_ok=True)
    filename = f"../../data/raw/{filing['company'].replace(' ', '_')}_{filing['form']}_{filing['date']}.htm"
    with open(filename, "wb") as f:
        f.write(response.content)

    print(f"  Saved locally: {filename}")
    return filename

def upload_to_s3(local_path: str, bucket: str, filing: dict) -> str:
    """Upload downloaded document to S3 raw-docs bucket."""
    key = (
        f"sec-filings/"
        f"{filing['company'].replace(' ', '_')}/"
        f"{filing['form']}_{filing['date']}.htm"
    )

    metadata = {
        "company":    filing["company"],
        "form-type":  filing["form"],
        "filing-date": filing["date"],
        "source":     "SEC-EDGAR",
        "ingested-at": datetime.utcnow().isoformat()
    }

    S3_CLIENT.upload_file(
        local_path,
        bucket,
        key,
        ExtraArgs={"Metadata": metadata}
    )

    print(f"  Uploaded to S3: s3://{bucket}/{key}")
    return key

def download_basel_guidelines(bucket: str):
    """
    Download Basel III summary document from BIS.
    Using the Basel III overview document (publicly available).
    """
    print("\nDownloading Basel III Guidelines...")

    url = "https://www.bis.org/publ/bcbsca.htm"
    response = requests.get(url, headers={
        "User-Agent": "Banking RAG Project admin@bankingrag.com"
    })

    os.makedirs("../../data/raw", exist_ok=True)
    filename = "../../data/raw/Basel_III_Guidelines.htm"
    with open(filename, "wb") as f:
        f.write(response.content)

    key = "regulatory/Basel_III_Guidelines.htm"
    S3_CLIENT.upload_file(
        filename, bucket, key,
        ExtraArgs={
            "Metadata": {
                "source":      "BIS",
                "document":    "Basel-III-Guidelines",
                "ingested-at": datetime.utcnow().isoformat()
            }
        }
    )
    print(f"  Uploaded to S3: s3://{bucket}/{key}")
    return key

def main():
    bucket = "banking-rag-raw-docs-418272768931"

    print("=" * 60)
    print("Banking RAG — Document Downloader")
    print("=" * 60)

    # ── US Banks ───────────────────────────────────────────
    us_banks = [
        {
            "cik":     "0000019617",
            "name":    "JPMorgan Chase",
            "country": "US"
        },
        {
            "cik":     "0000886982",
            "name":    "Goldman Sachs",
            "country": "US"
        },
    ]

    # ── Canadian Banks (all file with SEC as foreign filers)
    canadian_banks = [
        {
            "cik":     "0000947263",
            "name":    "Toronto-Dominion Bank",
            "country": "Canada"
        },
        {
            "cik":     "0000009631",
            "name":    "Bank of Nova Scotia",
            "country": "Canada"
        },
        {
            "cik":     "0000927971",
            "name":    "Bank of Montreal",
            "country": "Canada"
        },
        {
            "cik":     "0000926171",
            "name":    "National Bank of Canada",
            "country": "Canada"
        },
    ]

    all_banks   = us_banks + canadian_banks
    uploaded_keys = []

    # ── Download all bank filings ──────────────────────────
    for bank in all_banks:
        print(f"\n[{bank['country']}] Fetching {bank['name']} 10-K...")
        try:
            filings = get_company_filings(
                bank["cik"], "10-K", count=1
            )

            if not filings:
                # Canadian banks sometimes file as 40-F
                print(f"  No 10-K found, trying 40-F...")
                filings = get_company_filings(
                    bank["cik"], "40-F", count=1
                )

            for filing in filings:
                local_path = download_filing(filing)
                key        = upload_to_s3(local_path, bucket, filing)
                uploaded_keys.append(key)
                time.sleep(1)  # be polite to SEC servers

        except Exception as e:
            print(f"  Error downloading {bank['name']}: {e}")
            continue

    # ── Download Basel III ─────────────────────────────────
    try:
        key = download_basel_guidelines(bucket)
        uploaded_keys.append(key)
    except Exception as e:
        print(f"  Error downloading Basel III: {e}")

    # ── Summary ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Complete! {len(uploaded_keys)} documents uploaded to S3")
    print("=" * 60)
    for key in uploaded_keys:
        print(f"  s3://{bucket}/{key}")

if __name__ == "__main__":
    main()