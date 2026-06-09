output "ingestion_queue_url"  { value = aws_sqs_queue.ingestion.url }
output "processing_queue_url" { value = aws_sqs_queue.processing.url }
output "dead_letter_queue_url" { value = aws_sqs_queue.dead_letter.url }
output "ingestion_queue_arn"  { value = aws_sqs_queue.ingestion.arn }
