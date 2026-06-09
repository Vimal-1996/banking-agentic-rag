output "raw_docs_bucket"       { value = aws_s3_bucket.raw_docs.bucket }
output "processed_docs_bucket" { value = aws_s3_bucket.processed_docs.bucket }
output "audit_logs_bucket"     { value = aws_s3_bucket.audit_logs.bucket }
output "raw_docs_bucket_arn"   { value = aws_s3_bucket.raw_docs.arn }
