# Dead letter queue (catches failed messages)
resource "aws_sqs_queue" "dead_letter" {
  name                      = "${var.project_name}-dead-letter-queue"
  message_retention_seconds = 1209600
  tags                      = { Name = "${var.project_name}-dlq" }
}

# Ingestion queue (triggered when PDF lands in S3)
resource "aws_sqs_queue" "ingestion" {
  name                       = "${var.project_name}-ingestion-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 86400

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${var.project_name}-ingestion-queue" }
}

# Processing queue (chunking + embedding jobs)
resource "aws_sqs_queue" "processing" {
  name                       = "${var.project_name}-processing-queue"
  visibility_timeout_seconds = 600
  message_retention_seconds  = 86400

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${var.project_name}-processing-queue" }
}

# Allow S3 to send messages to ingestion queue
resource "aws_sqs_queue_policy" "ingestion" {
  queue_url = aws_sqs_queue.ingestion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.ingestion.arn
      Condition = {
        ArnLike = {
          "aws:SourceArn" = "arn:aws:s3:::${var.project_name}-raw-docs-*"
        }
      }
    }]
  })
}
