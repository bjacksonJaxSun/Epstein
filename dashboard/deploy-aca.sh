#!/bin/bash
# Azure Container Apps Deployment Script
# This script deploys the Epstein Dashboard to Azure Container Apps
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Docker installed and running
#   - Access to Azure Container Registry
#
# Usage:
#   ./deploy-aca.sh [environment] [action]
#
#   environment: prod (default), staging
#   action: deploy (default), build, infrastructure, all

set -e

# Configuration
ENVIRONMENT="${1:-prod}"
ACTION="${2:-deploy}"
RESOURCE_GROUP="epstein-rg"
LOCATION="eastus"
ACR_NAME="epsteinacr"
ACR_LOGIN_SERVER="${ACR_NAME}.azurecr.io"

# Derived names
BASE_NAME="epstein-${ENVIRONMENT}"
CONTAINER_ENV="${BASE_NAME}-env"
API_APP="${BASE_NAME}-api"
FRONTEND_APP="${BASE_NAME}-frontend"
POSTGRES_SERVER="${BASE_NAME}-db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Install from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Install from https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Run 'az login' first."
        exit 1
    fi

    log_info "Prerequisites OK"
}

# Deploy infrastructure using Bicep
deploy_infrastructure() {
    log_info "Deploying infrastructure with Bicep..."

    # Create resource group if it doesn't exist
    if ! az group show -n "$RESOURCE_GROUP" &> /dev/null; then
        log_info "Creating resource group: $RESOURCE_GROUP"
        az group create -n "$RESOURCE_GROUP" -l "$LOCATION"
    fi

    # Create ACR if it doesn't exist
    if ! az acr show -n "$ACR_NAME" -g "$RESOURCE_GROUP" &> /dev/null; then
        log_info "Creating Azure Container Registry: $ACR_NAME"
        az acr create -n "$ACR_NAME" -g "$RESOURCE_GROUP" --sku Basic --admin-enabled true
    fi

    # Get ACR credentials
    ACR_PASSWORD=$(az acr credential show -n "$ACR_NAME" --query "passwords[0].value" -o tsv)

    # Prompt for secrets if not set
    if [ -z "$POSTGRES_PASSWORD" ]; then
        read -sp "Enter PostgreSQL admin password: " POSTGRES_PASSWORD
        echo
    fi

    if [ -z "$JWT_SECRET" ]; then
        read -sp "Enter JWT secret (min 32 chars): " JWT_SECRET
        echo
    fi

    # Deploy Bicep template
    log_info "Deploying Bicep template..."
    az deployment group create \
        -g "$RESOURCE_GROUP" \
        -f "$(dirname "$0")/infra/main.bicep" \
        --parameters \
            environment="$ENVIRONMENT" \
            postgresAdminUser="epstein_admin" \
            postgresAdminPassword="$POSTGRES_PASSWORD" \
            jwtSecret="$JWT_SECRET" \
            containerRegistryLoginServer="$ACR_LOGIN_SERVER" \
            containerRegistryUsername="$ACR_NAME" \
            containerRegistryPassword="$ACR_PASSWORD"

    log_info "Infrastructure deployed successfully"
}

# Build and push Docker images
build_images() {
    log_info "Building Docker images..."

    # Login to ACR
    az acr login -n "$ACR_NAME"

    # Get script directory
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

    # Build API
    log_info "Building API image..."
    docker build \
        -t "${ACR_LOGIN_SERVER}/epstein-api:latest" \
        -t "${ACR_LOGIN_SERVER}/epstein-api:$(date +%Y%m%d-%H%M%S)" \
        -f "$SCRIPT_DIR/backend/Dockerfile" \
        "$SCRIPT_DIR/backend"

    # Build Frontend
    log_info "Building Frontend image..."
    docker build \
        -t "${ACR_LOGIN_SERVER}/epstein-frontend:latest" \
        -t "${ACR_LOGIN_SERVER}/epstein-frontend:$(date +%Y%m%d-%H%M%S)" \
        --build-arg REACT_APP_API_URL="https://${API_APP}.azurecontainerapps.io" \
        -f "$SCRIPT_DIR/frontend/Dockerfile" \
        "$SCRIPT_DIR/frontend"

    # Push images
    log_info "Pushing images to ACR..."
    docker push "${ACR_LOGIN_SERVER}/epstein-api:latest"
    docker push "${ACR_LOGIN_SERVER}/epstein-frontend:latest"

    log_info "Images built and pushed successfully"
}

# Deploy to Container Apps
deploy_apps() {
    log_info "Deploying to Container Apps..."

    # Update API container app
    log_info "Updating API container app..."
    az containerapp update \
        -n "$API_APP" \
        -g "$RESOURCE_GROUP" \
        --image "${ACR_LOGIN_SERVER}/epstein-api:latest"

    # Update Frontend container app
    log_info "Updating Frontend container app..."
    az containerapp update \
        -n "$FRONTEND_APP" \
        -g "$RESOURCE_GROUP" \
        --image "${ACR_LOGIN_SERVER}/epstein-frontend:latest"

    # Wait for deployment
    log_info "Waiting for deployment to complete..."
    sleep 30

    # Verify health
    API_URL=$(az containerapp show -n "$API_APP" -g "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)
    if curl -sf "https://${API_URL}/health" > /dev/null; then
        log_info "API health check passed"
    else
        log_warn "API health check failed - check logs"
    fi

    FRONTEND_URL=$(az containerapp show -n "$FRONTEND_APP" -g "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)

    echo ""
    log_info "Deployment complete!"
    echo "  API:      https://${API_URL}"
    echo "  Frontend: https://${FRONTEND_URL}"
}

# Show logs
show_logs() {
    log_info "Streaming API logs (Ctrl+C to stop)..."
    az containerapp logs show -n "$API_APP" -g "$RESOURCE_GROUP" --follow
}

# Get status
show_status() {
    log_info "Container Apps Status:"
    echo ""
    echo "API:"
    az containerapp show -n "$API_APP" -g "$RESOURCE_GROUP" \
        --query "{name:name, status:properties.runningStatus, replicas:properties.template.scale, url:properties.configuration.ingress.fqdn}" \
        -o table 2>/dev/null || echo "  Not deployed"
    echo ""
    echo "Frontend:"
    az containerapp show -n "$FRONTEND_APP" -g "$RESOURCE_GROUP" \
        --query "{name:name, status:properties.runningStatus, replicas:properties.template.scale, url:properties.configuration.ingress.fqdn}" \
        -o table 2>/dev/null || echo "  Not deployed"
}

# Scale apps
scale_apps() {
    MIN_REPLICAS="${1:-0}"
    MAX_REPLICAS="${2:-10}"

    log_info "Scaling apps to min=$MIN_REPLICAS, max=$MAX_REPLICAS..."

    az containerapp update -n "$API_APP" -g "$RESOURCE_GROUP" \
        --min-replicas "$MIN_REPLICAS" --max-replicas "$MAX_REPLICAS"

    az containerapp update -n "$FRONTEND_APP" -g "$RESOURCE_GROUP" \
        --min-replicas "$MIN_REPLICAS" --max-replicas "$((MAX_REPLICAS / 2))"

    log_info "Scaling complete"
}

# Main
check_prerequisites

case "$ACTION" in
    infrastructure|infra)
        deploy_infrastructure
        ;;
    build)
        build_images
        ;;
    deploy)
        deploy_apps
        ;;
    all)
        deploy_infrastructure
        build_images
        deploy_apps
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    scale)
        scale_apps "${3:-0}" "${4:-10}"
        ;;
    *)
        echo "Usage: $0 [environment] [action]"
        echo ""
        echo "Environments: prod, staging"
        echo ""
        echo "Actions:"
        echo "  infrastructure  Deploy Azure infrastructure (Bicep)"
        echo "  build           Build and push Docker images"
        echo "  deploy          Deploy containers to Container Apps"
        echo "  all             Run infrastructure + build + deploy"
        echo "  logs            Stream API container logs"
        echo "  status          Show deployment status"
        echo "  scale [min] [max]  Scale container replicas"
        echo ""
        echo "Examples:"
        echo "  $0 prod all              # Full deployment to production"
        echo "  $0 staging deploy        # Deploy to staging"
        echo "  $0 prod scale 1 10       # Scale prod to 1-10 replicas"
        ;;
esac
