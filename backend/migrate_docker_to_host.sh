#!/bin/bash
# Script to migrate data from Docker PostgreSQL to host PostgreSQL

set -e

echo "=== Migrate Data from Docker to Host PostgreSQL ==="
echo ""

# Check if Docker container exists
if ! docker ps -a | grep -q timescaledb; then
    echo "No Docker timescaledb container found. Nothing to migrate."
    exit 0
fi

# Check if host PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "Error: Host PostgreSQL is not running."
    echo "Please run: ./install_postgres_host.sh"
    echo "Then: sudo systemctl start postgresql"
    exit 1
fi

# Create backup directory
BACKUP_DIR="./migration_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Backup directory: $BACKUP_DIR"
echo ""

# Start Docker container if not running
if ! docker ps | grep -q timescaledb; then
    echo "Starting Docker container temporarily..."
    docker start timescaledb 2>/dev/null || echo "Could not start container"
    sleep 5
fi

# Backup data from Docker
echo "Step 1: Backing up data from Docker container..."

# Try to backup daily_bars
echo "  - Backing up daily_bars table..."
docker exec timescaledb psql -U postgres -d stock_screener -c "\copy daily_bars TO STDOUT WITH CSV HEADER" > "$BACKUP_DIR/daily_bars.csv" 2>/dev/null || {
    docker exec timescaledb psql -U postgres -d postgres -c "\copy daily_bars TO STDOUT WITH CSV HEADER" > "$BACKUP_DIR/daily_bars.csv" 2>/dev/null || {
        echo "    No daily_bars data found"
    }
}

# Try to backup symbols
echo "  - Backing up symbols table..."
docker exec timescaledb psql -U postgres -d stock_screener -c "\copy symbols TO STDOUT WITH CSV HEADER" > "$BACKUP_DIR/symbols.csv" 2>/dev/null || {
    docker exec timescaledb psql -U postgres -d postgres -c "\copy symbols TO STDOUT WITH CSV HEADER" > "$BACKUP_DIR/symbols.csv" 2>/dev/null || {
        echo "    No symbols data found"
    }
}

# Count backed up data
if [ -f "$BACKUP_DIR/daily_bars.csv" ]; then
    DAILY_COUNT=$(wc -l < "$BACKUP_DIR/daily_bars.csv")
    echo "  - Backed up $((DAILY_COUNT-1)) daily bars records"
fi

if [ -f "$BACKUP_DIR/symbols.csv" ]; then
    SYMBOL_COUNT=$(wc -l < "$BACKUP_DIR/symbols.csv")
    echo "  - Backed up $((SYMBOL_COUNT-1)) symbol records"
fi

# Initialize host database
echo ""
echo "Step 2: Initializing host database..."
./init_database.sh

# Import data to host
echo ""
echo "Step 3: Importing data to host PostgreSQL..."

if [ -f "$BACKUP_DIR/daily_bars.csv" ] && [ $(wc -l < "$BACKUP_DIR/daily_bars.csv") -gt 1 ]; then
    echo "  - Importing daily_bars..."
    PGPASSWORD=postgres psql -h localhost -U postgres -d stock_screener -c "\copy daily_bars FROM '$BACKUP_DIR/daily_bars.csv' WITH CSV HEADER"
    echo "  ✓ Daily bars imported"
fi

if [ -f "$BACKUP_DIR/symbols.csv" ] && [ $(wc -l < "$BACKUP_DIR/symbols.csv") -gt 1 ]; then
    echo "  - Importing symbols..."
    PGPASSWORD=postgres psql -h localhost -U postgres -d stock_screener -c "\copy symbols FROM '$BACKUP_DIR/symbols.csv' WITH CSV HEADER ON CONFLICT (symbol) DO NOTHING"
    echo "  ✓ Symbols imported"
fi

# Verify migration
echo ""
echo "Step 4: Verifying migration..."
MIGRATED_BARS=$(PGPASSWORD=postgres psql -h localhost -U postgres -d stock_screener -t -c "SELECT COUNT(*) FROM daily_bars" | tr -d ' ')
MIGRATED_SYMBOLS=$(PGPASSWORD=postgres psql -h localhost -U postgres -d stock_screener -t -c "SELECT COUNT(*) FROM symbols" | tr -d ' ')

echo "  - Daily bars in host DB: $MIGRATED_BARS"
echo "  - Symbols in host DB: $MIGRATED_SYMBOLS"

# Ask about Docker cleanup
echo ""
echo "=== Migration Complete ==="
echo ""
echo "Your data has been migrated to host PostgreSQL."
echo "Backup files are saved in: $BACKUP_DIR"
echo ""
read -p "Do you want to remove the Docker container and volume? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker stop timescaledb 2>/dev/null || true
    docker rm timescaledb 2>/dev/null || true
    docker volume rm screener_timescale_data 2>/dev/null || true
    echo "✓ Docker container and volume removed"
else
    echo "Docker container kept. You can remove it later with:"
    echo "  docker stop timescaledb && docker rm timescaledb"
    echo "  docker volume rm screener_timescale_data"
fi

echo ""
echo "Next steps:"
echo "1. Update start.sh and stop.sh to use host PostgreSQL (already done)"
echo "2. Run: cd .. && ./start.sh"