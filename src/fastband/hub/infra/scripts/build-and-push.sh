#!/bin/bash
# Fastband AI Hub - Build and Push Docker Image
# Usage: ./build-and-push.sh <environment> [version]
# Example: ./build-and-push.sh production v1.0.0

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUB_DIR="${SCRIPT_DIR}/../.."
AWS_REGION="${AWS_REGION:-us-west-2}"
ECR_REPOSITORY="fastband/hub"

# Get environment
ENVIRONMENT="${1:-dev}"
VERSION="${2:-$(git rev-parse --short HEAD)}"

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|production)$ ]]; then
    echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'${NC}"
    exit 1
fi

# Set image tag based on environment
if [[ "$ENVIRONMENT" == "production" ]]; then
    IMAGE_TAG="latest"
else
    IMAGE_TAG="$ENVIRONMENT"
fi

# Also tag with version
VERSION_TAG="$VERSION"

echo -e "${GREEN}=== Fastband AI Hub - Docker Build ===${NC}"
echo -e "Environment: ${YELLOW}$ENVIRONMENT${NC}"
echo -e "Version: ${YELLOW}$VERSION${NC}"
echo -e "Image Tag: ${YELLOW}$IMAGE_TAG${NC}"
echo ""

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo -e "${GREEN}ECR URI: ${ECR_URI}${NC}"

# Login to ECR
echo -e "${GREEN}Logging in to ECR...${NC}"
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Build the image
echo -e "${GREEN}Building Docker image...${NC}"
cd "$HUB_DIR"

docker build \
    --platform linux/amd64 \
    --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --build-arg VERSION="$VERSION" \
    --build-arg ENVIRONMENT="$ENVIRONMENT" \
    -t "${ECR_URI}:${IMAGE_TAG}" \
    -t "${ECR_URI}:${VERSION_TAG}" \
    -f Dockerfile \
    .

# Push the images
echo -e "${GREEN}Pushing images to ECR...${NC}"
docker push "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:${VERSION_TAG}"

echo ""
echo -e "${GREEN}=== Build Complete ===${NC}"
echo -e "Images pushed:"
echo -e "  - ${ECR_URI}:${IMAGE_TAG}"
echo -e "  - ${ECR_URI}:${VERSION_TAG}"
echo ""
echo "To deploy, run:"
echo -e "  ${YELLOW}./deploy.sh $ENVIRONMENT apply${NC}"
