# Development Environment Configuration

environment = "dev"
aws_region  = "us-west-2"

# VPC
vpc_cidr = "10.0.0.0/16"

# ECS
container_image   = "fastband/hub:dev"
ecs_desired_count = 1
ecs_cpu           = 256
ecs_memory        = 512

# Database
db_min_capacity = 0.5
db_max_capacity = 2

# Cache
redis_node_type = "cache.t4g.micro"

# External Services (replace with actual values)
supabase_url           = "https://your-project.supabase.co"
supabase_key_arn       = "arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:fastband/dev/supabase-key"
stripe_secret_key      = "sk_test_..."
stripe_webhook_key_arn = "arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:fastband/dev/stripe-webhook"
anthropic_api_key_arn  = "arn:aws:secretsmanager:us-west-2:ACCOUNT:secret:fastband/dev/anthropic"

# Monitoring
alarm_email = "dev-alerts@fastband.io"
