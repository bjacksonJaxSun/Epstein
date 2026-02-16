# Azure Container Apps Migration Guide

## Overview

This guide walks through migrating the Epstein Dashboard from the current Azure VM (20.25.96.123) to Azure Container Apps with auto-scaling support for up to 2,000 concurrent users.

**Current Architecture:** Single Azure VM with Docker Compose (nginx, API, frontend, PostgreSQL)

**Target Architecture:** Azure Container Apps with managed PostgreSQL Flexible Server

---

## Prerequisites

Before starting, ensure you have:

- [ ] Azure CLI installed (`az --version`)
- [ ] Docker installed and running
- [ ] Azure subscription with Owner/Contributor access
- [ ] Access to the current VM (BOBBYHOMEEP / 20.25.96.123)

### Install Azure CLI (if needed)

```powershell
# Windows
winget install Microsoft.AzureCLI

# Or download from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
```

### Login to Azure

```bash
az login
az account set --subscription "<your-subscription-id>"
```

---

## Phase 1: Create Azure Infrastructure

### Step 1.1: Create Resource Group and Container Registry

```bash
# Set variables
RESOURCE_GROUP="epstein-rg"
LOCATION="eastus"
ACR_NAME="epsteinacr"

# Create resource group
az group create -n $RESOURCE_GROUP -l $LOCATION

# Create Azure Container Registry
az acr create -n $ACR_NAME -g $RESOURCE_GROUP --sku Basic --admin-enabled true

# Get ACR credentials (save these)
az acr credential show -n $ACR_NAME
```

### Step 1.2: Deploy Infrastructure with Bicep

```bash
cd /path/to/EpsteinDownloader/dashboard

# Deploy infrastructure (will prompt for passwords)
./deploy-aca.sh prod infrastructure
```

Or manually:

```bash
# Generate secure passwords
POSTGRES_PASSWORD=$(openssl rand -base64 24)
JWT_SECRET=$(openssl rand -base64 32)

echo "PostgreSQL Password: $POSTGRES_PASSWORD"
echo "JWT Secret: $JWT_SECRET"
# SAVE THESE SECURELY!

# Deploy Bicep template
az deployment group create \
    -g epstein-rg \
    -f infra/main.bicep \
    --parameters \
        environment=prod \
        postgresAdminUser=epstein_admin \
        postgresAdminPassword="$POSTGRES_PASSWORD" \
        jwtSecret="$JWT_SECRET" \
        containerRegistryLoginServer=epsteinacr.azurecr.io \
        containerRegistryUsername=epsteinacr \
        containerRegistryPassword="$(az acr credential show -n epsteinacr --query 'passwords[0].value' -o tsv)"
```

### Step 1.3: Verify Infrastructure

```bash
# Check resources created
az resource list -g epstein-rg -o table

# Get PostgreSQL server FQDN
az postgres flexible-server show -n epstein-prod-db -g epstein-rg --query "fullyQualifiedDomainName" -o tsv
```

---

## Phase 2: Migrate Database

### Step 2.1: Export from Current VM

SSH into the current VM or run from a machine with network access:

```bash
# Export database (run on BOBBYHOMEEP or machine with access)
pg_dump -h BOBBYHOMEEP -U epstein_user -d epstein_documents -F c -f epstein_backup.dump

# Or plain SQL format
pg_dump -h BOBBYHOMEEP -U epstein_user -d epstein_documents > epstein_backup.sql
```

### Step 2.2: Import to Azure PostgreSQL

```bash
# Get Azure PostgreSQL FQDN
POSTGRES_HOST=$(az postgres flexible-server show -n epstein-prod-db -g epstein-rg --query "fullyQualifiedDomainName" -o tsv)

# Import database
pg_restore -h $POSTGRES_HOST -U epstein_admin -d epstein_documents epstein_backup.dump

# Or for SQL format
psql -h $POSTGRES_HOST -U epstein_admin -d epstein_documents < epstein_backup.sql
```

### Step 2.3: Verify Data

```bash
# Connect and verify
psql -h $POSTGRES_HOST -U epstein_admin -d epstein_documents

# Check record counts
SELECT 'documents' as table_name, COUNT(*) FROM documents
UNION ALL
SELECT 'entities', COUNT(*) FROM entities
UNION ALL
SELECT 'media_files', COUNT(*) FROM media_files;
```

---

## Phase 3: Build and Deploy Containers

### Step 3.1: Build Docker Images

```bash
cd /path/to/EpsteinDownloader/dashboard

# Login to ACR
az acr login -n epsteinacr

# Build and push images
./deploy-aca.sh prod build
```

Or manually:

```bash
# Build API
docker build -t epsteinacr.azurecr.io/epstein-api:latest -f backend/Dockerfile backend/
docker push epsteinacr.azurecr.io/epstein-api:latest

# Build Frontend
docker build -t epsteinacr.azurecr.io/epstein-frontend:latest \
    --build-arg REACT_APP_API_URL=https://epstein-prod-api.azurecontainerapps.io \
    -f frontend/Dockerfile frontend/
docker push epsteinacr.azurecr.io/epstein-frontend:latest
```

### Step 3.2: Deploy to Container Apps

```bash
./deploy-aca.sh prod deploy
```

### Step 3.3: Verify Deployment

```bash
# Check status
./deploy-aca.sh prod status

# Test health endpoints
API_URL=$(az containerapp show -n epstein-prod-api -g epstein-rg --query "properties.configuration.ingress.fqdn" -o tsv)
curl https://$API_URL/health
curl https://$API_URL/ready

# Get frontend URL
FRONTEND_URL=$(az containerapp show -n epstein-prod-frontend -g epstein-rg --query "properties.configuration.ingress.fqdn" -o tsv)
echo "Frontend: https://$FRONTEND_URL"
```

---

## Phase 4: DNS and SSL (Optional)

### Step 4.1: Add Custom Domain

```bash
# Add custom domain to frontend
az containerapp hostname add \
    -n epstein-prod-frontend \
    -g epstein-rg \
    --hostname yourdomain.com

# Configure DNS (add CNAME record pointing to Container Apps URL)
```

### Step 4.2: Configure SSL Certificate

Azure Container Apps provides automatic SSL for the default domain. For custom domains:

```bash
az containerapp hostname bind \
    -n epstein-prod-frontend \
    -g epstein-rg \
    --hostname yourdomain.com \
    --certificate-type ManagedCertificate
```

---

## Phase 5: Cutover and Cleanup

### Step 5.1: Update DNS / Load Balancer

Point your domain or load balancer to the new Container Apps URLs.

### Step 5.2: Monitor for Issues

```bash
# Stream logs
./deploy-aca.sh prod logs

# Check metrics in Azure Portal
# Navigate to: Container Apps > epstein-prod-api > Metrics
```

### Step 5.3: Decommission Old VM (After Validation)

Only after confirming the new deployment is stable:

```bash
# Stop the old VM (don't delete yet)
az vm stop -n epstein-vm -g old-resource-group

# After 1-2 weeks of stable operation, delete
# az vm delete -n epstein-vm -g old-resource-group
```

---

## Rollback Procedure

If issues occur, rollback is simple:

### Option 1: Rollback Container Apps to Previous Revision

```bash
# List revisions
az containerapp revision list -n epstein-prod-api -g epstein-rg -o table

# Activate previous revision
az containerapp revision activate -n epstein-prod-api -g epstein-rg --revision <previous-revision-name>
```

### Option 2: Point Back to Old VM

Simply update DNS or load balancer to point back to 20.25.96.123.

---

## Scaling Commands

```bash
# Scale to handle load (min 1 replica always running)
./deploy-aca.sh prod scale 1 10

# Scale to zero when idle (cost savings)
./deploy-aca.sh prod scale 0 10

# Manual scale for expected traffic
az containerapp update -n epstein-prod-api -g epstein-rg --min-replicas 3 --max-replicas 15
```

---

## Cost Monitoring

```bash
# View current costs
az consumption usage list -g epstein-rg --query "[].{Resource:instanceName, Cost:pretaxCost}" -o table

# Set budget alert
az consumption budget create \
    -g epstein-rg \
    --budget-name epstein-monthly \
    --amount 300 \
    --time-grain Monthly \
    --category Cost
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
az containerapp logs show -n epstein-prod-api -g epstein-rg --tail 100

# Check environment variables
az containerapp show -n epstein-prod-api -g epstein-rg --query "properties.template.containers[0].env"
```

### Database connection issues

```bash
# Verify PostgreSQL firewall allows Azure services
az postgres flexible-server firewall-rule list -g epstein-rg -s epstein-prod-db

# Test connection from local machine
psql -h epstein-prod-db.postgres.database.azure.com -U epstein_admin -d epstein_documents
```

### High latency

```bash
# Check replica count
az containerapp replica list -n epstein-prod-api -g epstein-rg

# Increase minimum replicas
az containerapp update -n epstein-prod-api -g epstein-rg --min-replicas 2
```

---

## GitHub Actions Setup (CI/CD)

To enable automatic deployments on push to main:

1. Create Azure Service Principal:
```bash
az ad sp create-for-rbac --name "epstein-deploy" --role contributor \
    --scopes /subscriptions/<subscription-id>/resourceGroups/epstein-rg \
    --sdk-auth
```

2. Add GitHub Secrets:
   - `AZURE_CREDENTIALS`: Output from above command
   - `ACR_LOGIN_SERVER`: epsteinacr.azurecr.io
   - `ACR_USERNAME`: epsteinacr
   - `ACR_PASSWORD`: (from `az acr credential show`)

3. Push to main branch to trigger deployment.

---

## Estimated Timeline

| Phase | Duration |
|-------|----------|
| Phase 1: Infrastructure | 30-60 min |
| Phase 2: Database Migration | 1-2 hours (depends on data size) |
| Phase 3: Container Deployment | 15-30 min |
| Phase 4: DNS/SSL | 15-30 min |
| Phase 5: Validation | 1-2 days |

**Total: 1 day for deployment + 1-2 days validation before decommissioning old VM**

---

## Support Contacts

- Azure Support: https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade
- Container Apps Docs: https://learn.microsoft.com/en-us/azure/container-apps/

---

## Quick Reference

| Resource | Command |
|----------|---------|
| Deploy all | `./deploy-aca.sh prod all` |
| Check status | `./deploy-aca.sh prod status` |
| View logs | `./deploy-aca.sh prod logs` |
| Scale replicas | `./deploy-aca.sh prod scale 1 10` |
| Get API URL | `az containerapp show -n epstein-prod-api -g epstein-rg --query "properties.configuration.ingress.fqdn" -o tsv` |
