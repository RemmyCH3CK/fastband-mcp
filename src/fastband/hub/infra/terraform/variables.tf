# Fastband AI Hub - Terraform Variables

# General
variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

# VPC
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# ECS
variable "container_image" {
  description = "Docker image for the Fastband Hub service"
  type        = string
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_cpu" {
  description = "CPU units for ECS task (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 512
}

variable "ecs_memory" {
  description = "Memory in MB for ECS task"
  type        = number
  default     = 1024
}

# Database
variable "db_min_capacity" {
  description = "Minimum Aurora Serverless v2 ACU capacity"
  type        = number
  default     = 0.5
}

variable "db_max_capacity" {
  description = "Maximum Aurora Serverless v2 ACU capacity"
  type        = number
  default     = 16
}

variable "db_master_username" {
  description = "Master username for database"
  type        = string
  default     = "fastband_admin"
}

# Cache
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}

# External Services (Secrets Manager ARNs)
variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
}

variable "supabase_key_arn" {
  description = "ARN of Secrets Manager secret containing Supabase key"
  type        = string
}

variable "stripe_secret_key" {
  description = "Stripe secret key (for non-sensitive config)"
  type        = string
  sensitive   = true
}

variable "stripe_webhook_key_arn" {
  description = "ARN of Secrets Manager secret containing Stripe webhook key"
  type        = string
}

variable "anthropic_api_key_arn" {
  description = "ARN of Secrets Manager secret containing Anthropic API key"
  type        = string
}

# Monitoring
variable "alarm_email" {
  description = "Email address for CloudWatch alarms"
  type        = string
}
