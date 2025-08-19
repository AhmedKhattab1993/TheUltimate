#!/bin/bash
# Quick fix script to resolve database issues once and for all

echo "========================================="
echo "FIXING DATABASE ISSUES - PERMANENT SOLUTION"
echo "========================================="
echo ""
echo "This script will:"
echo "1. Backup any existing data from Docker"
echo "2. Install PostgreSQL on your host system"
echo "3. Migrate all data"
echo "4. Update configuration"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

cd backend

# Step 1: Backup existing data
echo ""
echo "Step 1: Backing up existing data..."
./backup_docker_data.sh || echo "No existing data to backup"

# Step 2: Stop Docker containers
echo ""
echo "Step 2: Stopping Docker containers..."
docker stop timescaledb 2>/dev/null || true
docker rm timescaledb 2>/dev/null || true

# Step 3: Install host PostgreSQL
echo ""
echo "Step 3: Installing PostgreSQL on host..."
./setup_host_database.sh

# Step 4: Run migrations
echo ""
echo "Step 4: Running migrations..."
./run_migrations.sh

# Step 5: Test connection
echo ""
echo "Step 5: Testing connection..."
if psql -h localhost -U postgres -d stock_screener -c "SELECT COUNT(*) FROM daily_bars;" > /dev/null 2>&1; then
    echo "✓ Database connection successful!"
else
    echo "✗ Database connection failed"
    exit 1
fi

echo ""
echo "========================================="
echo "✓ DATABASE FIXED SUCCESSFULLY!"
echo "========================================="
echo ""
echo "Your database is now:"
echo "- Running on the host (not in Docker)"
echo "- Data stored permanently at /var/lib/postgresql/"
echo "- Will survive reboots and container deletions"
echo ""
echo "Next steps:"
echo "1. Run: cd .. && ./start.sh"
echo "2. Your application will use the host database"
echo "3. No more data loss!"