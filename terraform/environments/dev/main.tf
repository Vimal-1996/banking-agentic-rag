terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "banking-agentic-rag"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

module "vpc" {
  source             = "../../modules/vpc"
  project_name       = var.project_name
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  public_subnets     = var.public_subnets
  private_subnets    = var.private_subnets
  aws_region         = var.aws_region
}

module "iam" {
  source       = "../../modules/iam"
  project_name = var.project_name
}

module "s3" {
  source       = "../../modules/s3"
  project_name = var.project_name
  account_id   = data.aws_caller_identity.current.account_id
}

module "sqs" {
  source       = "../../modules/sqs"
  project_name = var.project_name
}

module "rds" {
  source             = "../../modules/rds"
  project_name       = var.project_name
  private_subnet_ids = module.vpc.private_subnet_ids
  rds_sg_id          = module.vpc.rds_sg_id
  db_username        = var.db_username
  db_password        = var.db_password
}

module "secrets" {
  source         = "../../modules/secrets"
  project_name   = var.project_name
  db_username    = var.db_username
  db_password    = var.db_password
  db_endpoint    = module.rds.db_endpoint
  openai_api_key = var.openai_api_key
  jwt_secret     = var.jwt_secret
}

module "ecs" {
  source                     = "../../modules/ecs"
  project_name               = var.project_name
  aws_region                 = var.aws_region
  vpc_id                     = module.vpc.vpc_id
  public_subnet_ids          = module.vpc.public_subnet_ids
  alb_sg_id                  = module.vpc.alb_sg_id
  ecs_sg_id                  = module.vpc.ecs_sg_id
  ecs_task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  ecs_task_role_arn           = module.iam.ecs_task_role_arn
  db_credentials_arn          = module.secrets.db_credentials_arn
  openai_key_arn              = module.secrets.openai_key_arn
}
