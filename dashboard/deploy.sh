#!/bin/bash
# Epstein Dashboard Deployment Script
# This script builds, publishes, and deploys the dashboard

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
PUBLISH_DIR="$BACKEND_DIR/publish"
MIGRATIONS_DIR="$BACKEND_DIR/migrations"

# Database configuration
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-epstein_documents}"
DB_USER="${DB_USER:-epstein_user}"
DB_PASSWORD="${DB_PASSWORD:-epstein_secure_pw_2024}"

# Options
BUILD_FRONTEND=true
BUILD_BACKEND=true
RUN_MIGRATION=false
RESTART_SERVICE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --run-migration)
            RUN_MIGRATION=true
            shift
            ;;
        --restart-service)
            RESTART_SERVICE=true
            shift
            ;;
        --skip-frontend)
            BUILD_FRONTEND=false
            shift
            ;;
        --skip-backend)
            BUILD_BACKEND=false
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --run-migration    Apply database migrations"
            echo "  --restart-service  Restart the application service"
            echo "  --skip-frontend    Skip frontend build"
            echo "  --skip-backend     Skip backend build"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "========================================"
echo "  Epstein Dashboard Deployment Script"
echo "========================================"
echo ""

# Step 1: Build Frontend
if [ "$BUILD_FRONTEND" = true ]; then
    echo "[1/5] Building Frontend..."
    cd "$FRONTEND_DIR"
    npm install --silent
    npm run build
    echo "  Frontend build successful"
else
    echo "[1/5] Skipping Frontend build"
fi

# Step 2: Build and Publish Backend
if [ "$BUILD_BACKEND" = true ]; then
    echo "[2/5] Building and Publishing Backend..."
    cd "$BACKEND_DIR"

    # Clean previous publish
    rm -rf "$PUBLISH_DIR"

    # Restore and publish
    dotnet restore --verbosity quiet
    dotnet publish src/EpsteinDashboard.Api -c Release -o "$PUBLISH_DIR" --verbosity minimal
    echo "  Backend publish successful"
else
    echo "[2/5] Skipping Backend build"
fi

# Step 3: Run Database Migrations
if [ "$RUN_MIGRATION" = true ]; then
    echo "[3/5] Running Database Migrations..."

    export PGPASSWORD="$DB_PASSWORD"

    for migration in "$MIGRATIONS_DIR"/*.sql; do
        if [ -f "$migration" ]; then
            echo "  Applying: $(basename "$migration")"
            psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$migration" || {
                echo "  Warning: Migration may have already been applied"
            }
        fi
    done
else
    echo "[3/5] Skipping Database Migrations (use --run-migration to apply)"
fi

# Step 4: Copy Frontend dist to Backend wwwroot
echo "[4/5] Copying Frontend to Backend wwwroot..."
FRONTEND_DIST="$FRONTEND_DIR/dist"
BACKEND_WWWROOT="$PUBLISH_DIR/wwwroot"

if [ -d "$FRONTEND_DIST" ]; then
    mkdir -p "$BACKEND_WWWROOT"
    cp -r "$FRONTEND_DIST"/* "$BACKEND_WWWROOT/"
    echo "  Frontend assets copied to wwwroot"
else
    echo "  Warning: Frontend dist folder not found"
fi

# Step 5: Restart Service
if [ "$RESTART_SERVICE" = true ]; then
    echo "[5/5] Restarting Service..."

    # Try systemd service first
    if systemctl is-active --quiet epstein-dashboard 2>/dev/null; then
        sudo systemctl restart epstein-dashboard
        echo "  Service restarted"
    else
        echo "  Service not found. To start manually:"
        echo "    cd $PUBLISH_DIR"
        echo "    dotnet EpsteinDashboard.Api.dll"
    fi
else
    echo "[5/5] Skipping Service Restart (use --restart-service to restart)"
fi

echo ""
echo "========================================"
echo "  Deployment Complete!"
echo "========================================"
echo ""
echo "Published to: $PUBLISH_DIR"
echo ""
echo "To start the application manually:"
echo "  cd $PUBLISH_DIR"
echo "  dotnet EpsteinDashboard.Api.dll"
echo ""
echo "Default admin credentials:"
echo "  Username: admin"
echo "  Password: ChangeMe123! (or ADMIN_INITIAL_PASSWORD env var)"
