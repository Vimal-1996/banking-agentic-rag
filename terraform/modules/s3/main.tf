# Raw documents bucket (uploaded PDFs, filings)
resource "aws_s3_bucket" "raw_docs" {
  bucket        = "${var.project_name}-raw-docs-${var.account_id}"
  force_destroy = true
  tags          = { Name = "${var.project_name}-raw-docs" }
}

resource "aws_s3_bucket_versioning" "raw_docs" {
  bucket = aws_s3_bucket.raw_docs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_docs" {
  bucket = aws_s3_bucket.raw_docs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_docs" {
  bucket                  = aws_s3_bucket.raw_docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Processed documents bucket (chunked, embedded)
resource "aws_s3_bucket" "processed_docs" {
  bucket        = "${var.project_name}-processed-docs-${var.account_id}"
  force_destroy = true
  tags          = { Name = "${var.project_name}-processed-docs" }
}

resource "aws_s3_bucket_versioning" "processed_docs" {
  bucket = aws_s3_bucket.processed_docs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "processed_docs" {
  bucket = aws_s3_bucket.processed_docs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "processed_docs" {
  bucket                  = aws_s3_bucket.processed_docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Audit logs bucket (every agent query logged here)
resource "aws_s3_bucket" "audit_logs" {
  bucket        = "${var.project_name}-audit-logs-${var.account_id}"
  force_destroy = true
  tags          = { Name = "${var.project_name}-audit-logs" }
}

resource "aws_s3_bucket_versioning" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audit_logs" {
  bucket                  = aws_s3_bucket.audit_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rule — move audit logs to cheaper storage after 90 days
resource "aws_s3_bucket_lifecycle_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  rule {
    id     = "archive-old-logs"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }
}
