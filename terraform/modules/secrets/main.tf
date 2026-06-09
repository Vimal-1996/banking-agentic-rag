# Database credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.project_name}/db-credentials"
  description             = "RDS PostgreSQL credentials"
  recovery_window_in_days = 0
  tags                    = { Name = "${var.project_name}-db-credentials" }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = var.db_endpoint
    port     = 5432
    dbname   = "bankingrag"
  })
}

# OpenAI API key
resource "aws_secretsmanager_secret" "openai_key" {
  name                    = "${var.project_name}/openai-api-key"
  description             = "OpenAI API key for embeddings and LLM"
  recovery_window_in_days = 0
  tags                    = { Name = "${var.project_name}-openai-key" }
}

resource "aws_secretsmanager_secret_version" "openai_key" {
  secret_id     = aws_secretsmanager_secret.openai_key.id
  secret_string = jsonencode({ api_key = var.openai_api_key })
}

# App secrets (JWT, etc.)
resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.project_name}/app-secrets"
  description             = "Application secrets"
  recovery_window_in_days = 0
  tags                    = { Name = "${var.project_name}-app-secrets" }
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    jwt_secret   = var.jwt_secret
    environment  = "dev"
  })
}
