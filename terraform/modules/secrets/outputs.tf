output "db_credentials_arn" { value = aws_secretsmanager_secret.db_credentials.arn }
output "openai_key_arn"     { value = aws_secretsmanager_secret.openai_key.arn }
output "app_secrets_arn"    { value = aws_secretsmanager_secret.app_secrets.arn }
