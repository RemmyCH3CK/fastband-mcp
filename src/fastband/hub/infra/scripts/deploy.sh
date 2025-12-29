#!/bin/bash
# Fastband AI Hub - Deployment Script
# Usage: ./deploy.sh <environment> [action]
# Example: ./deploy.sh production apply

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

# Validate environment
ENVIRONMENT="${1:-}"
ACTION="${2:-plan}"

if [[ -z "$ENVIRONMENT" ]]; then
    echo -e "${RED}Error: Environment required${NC}"
    echo "Usage: $0 <environment> [action]"
    echo "Environments: dev, staging, production"
    echo "Actions: plan, apply, destroy"
    exit 1
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|production)$ ]]; then
    echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'${NC}"
    echo "Valid environments: dev, staging, production"
    exit 1
fi

if [[ ! "$ACTION" =~ ^(plan|apply|destroy)$ ]]; then
    echo -e "${RED}Error: Invalid action '$ACTION'${NC}"
    echo "Valid actions: plan, apply, destroy"
    exit 1
fi

# Configuration
TFVARS_FILE="${TERRAFORM_DIR}/environments/${ENVIRONMENT}.tfvars"

if [[ ! -f "$TFVARS_FILE" ]]; then
    echo -e "${RED}Error: tfvars file not found: $TFVARS_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}=== Fastband AI Hub Deployment ===${NC}"
echo -e "Environment: ${YELLOW}$ENVIRONMENT${NC}"
echo -e "Action: ${YELLOW}$ACTION${NC}"
echo ""

# Change to Terraform directory
cd "$TERRAFORM_DIR"

# Initialize Terraform
echo -e "${GREEN}Initializing Terraform...${NC}"
terraform init -backend-config="key=hub/${ENVIRONMENT}/terraform.tfstate"

# Validate configuration
echo -e "${GREEN}Validating Terraform configuration...${NC}"
terraform validate

# Execute action
case "$ACTION" in
    plan)
        echo -e "${GREEN}Creating execution plan...${NC}"
        terraform plan -var-file="$TFVARS_FILE" -out="${ENVIRONMENT}.tfplan"
        echo -e "${GREEN}Plan saved to ${ENVIRONMENT}.tfplan${NC}"
        echo "Run './deploy.sh $ENVIRONMENT apply' to apply changes"
        ;;
    apply)
        if [[ -f "${ENVIRONMENT}.tfplan" ]]; then
            echo -e "${YELLOW}Applying saved plan...${NC}"
            terraform apply "${ENVIRONMENT}.tfplan"
            rm "${ENVIRONMENT}.tfplan"
        else
            echo -e "${YELLOW}No saved plan found. Creating and applying...${NC}"
            terraform apply -var-file="$TFVARS_FILE" -auto-approve
        fi
        echo -e "${GREEN}Deployment complete!${NC}"
        ;;
    destroy)
        echo -e "${RED}WARNING: This will destroy all resources in $ENVIRONMENT!${NC}"
        read -p "Are you sure? (type 'yes' to confirm): " confirm
        if [[ "$confirm" == "yes" ]]; then
            terraform destroy -var-file="$TFVARS_FILE" -auto-approve
            echo -e "${GREEN}Resources destroyed.${NC}"
        else
            echo "Cancelled."
            exit 0
        fi
        ;;
esac

# Show outputs if apply was successful
if [[ "$ACTION" == "apply" ]]; then
    echo ""
    echo -e "${GREEN}=== Deployment Outputs ===${NC}"
    terraform output
fi

echo ""
echo -e "${GREEN}Done!${NC}"
