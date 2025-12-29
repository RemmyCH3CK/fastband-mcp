# Fastband AI Hub - AWS Infrastructure
# This Terraform configuration creates the complete infrastructure for
# running the Fastband AI Hub SaaS platform.

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "fastband-terraform-state"
    key            = "hub/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "fastband-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "fastband-hub"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Local values
locals {
  name_prefix = "fastband-${var.environment}"
  az_count    = min(length(data.aws_availability_zones.available.names), 3)

  common_tags = {
    Project     = "fastband-hub"
    Environment = var.environment
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  name_prefix        = local.name_prefix
  vpc_cidr           = var.vpc_cidr
  availability_zones = slice(data.aws_availability_zones.available.names, 0, local.az_count)

  tags = local.common_tags
}

# ECS Cluster Module
module "ecs" {
  source = "./modules/ecs"

  name_prefix        = local.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  public_subnet_ids  = module.vpc.public_subnet_ids

  container_image    = var.container_image
  container_port     = 8000
  desired_count      = var.ecs_desired_count
  cpu                = var.ecs_cpu
  memory             = var.ecs_memory

  environment_variables = {
    ENVIRONMENT       = var.environment
    SUPABASE_URL      = var.supabase_url
    STRIPE_SECRET_KEY = var.stripe_secret_key
    DATABASE_URL      = module.database.connection_string
    REDIS_URL         = module.cache.endpoint
    S3_BUCKET         = module.storage.bucket_name
  }

  secrets = {
    SUPABASE_KEY       = var.supabase_key_arn
    STRIPE_WEBHOOK_KEY = var.stripe_webhook_key_arn
    ANTHROPIC_API_KEY  = var.anthropic_api_key_arn
  }

  tags = local.common_tags

  depends_on = [module.vpc, module.database, module.cache]
}

# Database Module (Aurora Serverless v2)
module "database" {
  source = "./modules/database"

  name_prefix        = local.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  engine_version     = "15.4"
  min_capacity       = var.db_min_capacity
  max_capacity       = var.db_max_capacity

  master_username    = var.db_master_username

  tags = local.common_tags

  depends_on = [module.vpc]
}

# Redis Cache Module
module "cache" {
  source = "./modules/cache"

  name_prefix        = local.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  node_type          = var.redis_node_type
  num_cache_nodes    = var.environment == "production" ? 2 : 1

  tags = local.common_tags

  depends_on = [module.vpc]
}

# S3 Storage Module
module "storage" {
  source = "./modules/storage"

  name_prefix = local.name_prefix
  environment = var.environment

  tags = local.common_tags
}

# CloudWatch Monitoring Module
module "monitoring" {
  source = "./modules/monitoring"

  name_prefix        = local.name_prefix
  ecs_cluster_name   = module.ecs.cluster_name
  ecs_service_name   = module.ecs.service_name
  alb_arn_suffix     = module.ecs.alb_arn_suffix

  alarm_email        = var.alarm_email

  tags = local.common_tags

  depends_on = [module.ecs]
}

# Outputs
output "api_endpoint" {
  description = "The API endpoint URL"
  value       = module.ecs.alb_dns_name
}

output "database_endpoint" {
  description = "The database endpoint"
  value       = module.database.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "The Redis endpoint"
  value       = module.cache.endpoint
  sensitive   = true
}

output "s3_bucket" {
  description = "The S3 bucket name"
  value       = module.storage.bucket_name
}
