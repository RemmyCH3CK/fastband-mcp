# Production Environment Configuration

environment = "production"
aws_region  = "us-west-2"

# VPC
vpc_cidr = "10.1.0.0/16"

# ECS
container_image   = "fastband/hub:latest"
ecs_desired_count = 3
ecs_cpu           = 1024
ecs_memory        = 2048

# Database
db_min_capacity = 2
db_max_capacity = 32

# Cache
redis_node_type = "cache.r7g.large"

# External Services (replace with actual values)
supabase_url           = "https://your-project.supabase.co"
supabase_key_arn       = "arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:fastband/prod/supabase-key"
stripe_secret_key      = "sk_live_..."
stripe_webhook_key_arn = "arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:fastband/prod/stripe-webhook"
anthropic_api_key_arn  = "arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:fastband/prod/anthropic"

# Monitoring
alarm_email = "ops-alerts@fastband.io"
