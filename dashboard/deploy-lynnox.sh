#!/bin/bash
#===============================================================================
# Epstein Dashboard - Full Deployment Script for Lynnox VM (Azure)
#===============================================================================
# This script performs a complete deployment:
#   1. Builds the React frontend (npm install + npm run build)
#   2. Publishes the .NET backend (dotnet publish)
#   3. Copies frontend assets to backend wwwroot
#   4. Runs database migrations (auto on startup)
#   5. Restarts the application service
#
# Usage:
#   ./deploy-lynnox.sh              # Full build and deploy
#   ./deploy-lynnox.sh --restart    # Just restart service (no build)
#   ./deploy-lynnox.sh --frontend   # Rebuild frontend only
#   ./deploy-lynnox.sh --backend    # Rebuild backend only
#===============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
PUBLISH_DIR="$BACKEND_DIR/publish"
WWWROOT_DIR="$PUBLISH_DIR/wwwroot"
LOG_FILE="/var/log/epstein-dashboard.log"
SERVICE_NAME="epstein-dashboard"
APP_PORT=5000

# Database configuration
DB_HOST="localhost"
DB_NAME="epstein_documents"
DB_USER="epstein_user"
DB_PASSWORD="epstein_secure_pw_2024"

# Parse arguments
BUILD_FRONTEND=true
BUILD_BACKEND=true
RESTART_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --restart)
            RESTART_ONLY=true
            BUILD_FRONTEND=false
            BUILD_BACKEND=false
            shift
            ;;
        --frontend)
            BUILD_BACKEND=false
            shift
            ;;
        --backend)
            BUILD_FRONTEND=false
            shift
            ;;
        --help|-h)
            echo "Epstein Dashboard Deployment Script"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --restart     Just restart the service (no build)"
            echo "  --frontend    Rebuild frontend only"
            echo "  --backend     Rebuild backend only"
            echo "  --help, -h    Show this help"
            echo ""
            echo "Default: Full build (frontend + backend) and restart"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Epstein Dashboard - Full Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "  Host: $(hostname)"
echo -e "  Date: $(date)"
echo -e "${BLUE}========================================${NC}"
echo ""

#-------------------------------------------------------------------------------
# Step 1: Build Frontend
#-------------------------------------------------------------------------------
if [ "$BUILD_FRONTEND" = true ]; then
    echo -e "${YELLOW}[1/6] Building Frontend...${NC}"
    cd "$FRONTEND_DIR"

    echo "  Installing dependencies..."
    npm install --silent 2>/dev/null || npm install

    echo "  Running build..."
    npm run build

    # Verify build output
    if [ ! -d "$FRONTEND_DIR/dist" ] || [ -z "$(ls -A $FRONTEND_DIR/dist 2>/dev/null)" ]; then
        echo -e "${RED}  ERROR: Frontend build produced no output${NC}"
        exit 1
    fi

    FILE_COUNT=$(find "$FRONTEND_DIR/dist" -type f | wc -l)
    echo -e "${GREEN}  Frontend build complete ($FILE_COUNT files)${NC}"
else
    echo -e "${BLUE}[1/6] Skipping frontend build${NC}"
fi

#-------------------------------------------------------------------------------
# Step 2: Publish Backend
#-------------------------------------------------------------------------------
if [ "$BUILD_BACKEND" = true ]; then
    echo -e "${YELLOW}[2/6] Publishing Backend...${NC}"
    cd "$BACKEND_DIR"

    # Clean previous publish
    if [ -d "$PUBLISH_DIR" ]; then
        echo "  Cleaning previous publish..."
        rm -rf "$PUBLISH_DIR"
    fi

    echo "  Running dotnet publish..."
    dotnet restore --verbosity quiet
    dotnet publish src/EpsteinDashboard.Api -c Release -o "$PUBLISH_DIR" --verbosity minimal

    # Verify publish output
    if [ ! -f "$PUBLISH_DIR/EpsteinDashboard.Api.dll" ]; then
        echo -e "${RED}  ERROR: Backend publish failed${NC}"
        exit 1
    fi

    echo -e "${GREEN}  Backend publish complete${NC}"
else
    echo -e "${BLUE}[2/6] Skipping backend build${NC}"
fi

#-------------------------------------------------------------------------------
# Step 3: Copy Frontend to wwwroot
#-------------------------------------------------------------------------------
if [ "$BUILD_FRONTEND" = true ]; then
    echo -e "${YELLOW}[3/6] Copying Frontend to wwwroot...${NC}"

    mkdir -p "$WWWROOT_DIR"
    rm -rf "$WWWROOT_DIR"/*
    cp -r "$FRONTEND_DIR/dist"/* "$WWWROOT_DIR/"

    echo -e "${GREEN}  Frontend assets copied to wwwroot${NC}"
else
    echo -e "${BLUE}[3/6] Skipping frontend copy${NC}"
fi

#-------------------------------------------------------------------------------
# Step 4: Stop Running Service
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[4/6] Stopping existing service...${NC}"

# Try systemd first
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "  Stopping via systemd..."
    sudo systemctl stop "$SERVICE_NAME"
    echo -e "${GREEN}  Service stopped${NC}"
# Try pkill
elif pgrep -f "EpsteinDashboard.Api.dll" > /dev/null 2>&1; then
    echo "  Stopping via pkill..."
    sudo pkill -f "EpsteinDashboard.Api.dll" || true
    sleep 2
    echo -e "${GREEN}  Process stopped${NC}"
else
    echo "  No running service found"
fi

#-------------------------------------------------------------------------------
# Step 5: Start Service
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[5/6] Starting service...${NC}"
cd "$PUBLISH_DIR"

# Check if systemd service exists
if systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
    echo "  Starting via systemd..."
    sudo systemctl start "$SERVICE_NAME"
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}  Service started successfully${NC}"
    else
        echo -e "${RED}  Service failed to start. Check: sudo journalctl -u $SERVICE_NAME${NC}"
        exit 1
    fi
else
    # Start manually
    echo "  Starting manually (no systemd service found)..."

    # Ensure log directory exists
    sudo mkdir -p "$(dirname $LOG_FILE)"
    sudo touch "$LOG_FILE"
    sudo chmod 666 "$LOG_FILE"

    # Set environment
    export ASPNETCORE_ENVIRONMENT=Production
    export ASPNETCORE_URLS="http://0.0.0.0:$APP_PORT"

    # Start application
    nohup dotnet EpsteinDashboard.Api.dll >> "$LOG_FILE" 2>&1 &
    APP_PID=$!

    # Wait for startup
    sleep 3

    if ps -p $APP_PID > /dev/null 2>&1; then
        echo -e "${GREEN}  Application started (PID: $APP_PID)${NC}"
    else
        echo -e "${RED}  Application failed to start${NC}"
        echo "  Last 20 lines of log:"
        tail -20 "$LOG_FILE"
        exit 1
    fi
fi

#-------------------------------------------------------------------------------
# Step 6: Health Check
#-------------------------------------------------------------------------------
echo -e "${YELLOW}[6/6] Running health check...${NC}"

# Wait a moment for the app to fully initialize
sleep 2

# Check health endpoint
HEALTH_URL="http://localhost:$APP_PORT/health"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}  Health check passed (HTTP $HTTP_CODE)${NC}"

    # Check database connection via API
    HEALTH_RESPONSE=$(curl -s "$HEALTH_URL" 2>/dev/null || echo "{}")
    echo "  Health response: $HEALTH_RESPONSE"
else
    echo -e "${YELLOW}  Health check returned HTTP $HTTP_CODE (may still be starting)${NC}"
fi

# Check database tables
echo ""
echo "  Checking database..."
export PGPASSWORD="$DB_PASSWORD"
if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" >/dev/null 2>&1; then
    AUTH_TABLES=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT string_agg(tablename, ', ') FROM pg_tables WHERE tablename IN ('users', 'roles', 'user_roles', 'refresh_tokens')" \
        2>/dev/null | tr -d ' ' || echo "none")

    if [ -n "$AUTH_TABLES" ] && [ "$AUTH_TABLES" != "none" ]; then
        echo -e "${GREEN}  Auth tables present: $AUTH_TABLES${NC}"

        # Check for admin user
        ADMIN_EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -t -c \
            "SELECT COUNT(*) FROM users WHERE username = 'admin'" 2>/dev/null | tr -d ' ' || echo "0")
        if [ "$ADMIN_EXISTS" -gt 0 ]; then
            echo -e "${GREEN}  Admin user exists${NC}"
        else
            echo -e "${YELLOW}  Admin user will be created on first request${NC}"
        fi
    else
        echo -e "${YELLOW}  Auth tables will be created on first request${NC}"
    fi
else
    echo -e "${YELLOW}  Could not connect to database${NC}"
fi

#-------------------------------------------------------------------------------
# Summary
#-------------------------------------------------------------------------------
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Application URLs:"
echo "  Dashboard:  http://$(hostname):$APP_PORT"
echo "  Swagger:    http://$(hostname):$APP_PORT/swagger"
echo "  Health:     http://$(hostname):$APP_PORT/health"
echo ""
echo "Default admin credentials:"
echo "  Username: admin"
echo "  Password: ChangeMe123!"
echo ""
echo "Useful commands:"
echo "  View logs:     tail -f $LOG_FILE"
echo "  Service status: systemctl status $SERVICE_NAME"
echo "  Restart:       sudo systemctl restart $SERVICE_NAME"
echo ""
