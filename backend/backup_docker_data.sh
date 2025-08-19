#!/bin/bash
# Script to backup data from Docker container before migration

set -e

BACKUP_DIR="./database_backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "=== Backing up data from Docker container ==="
echo "Backup directory: $BACKUP_DIR"
echo ""

# Check if container is running
if ! docker ps | grep -q timescaledb; then
    echo "Warning: timescaledb container is not running"
    echo "Attempting to start it temporarily for backup..."
    docker start timescaledb 2>/dev/null || echo "Could not start container"
fi

# List databases
echo "Checking available databases..."
docker exec timescaledb psql -U postgres -c "\l" > "$BACKUP_DIR/databases.txt" 2>/dev/null || {
    echo "Could not connect to Docker database"
    exit 1
}

# Try to backup each potential database
for db in stock_screener postgres; do
    echo "Attempting to backup database: $db"
    docker exec timescaledb pg_dump -U postgres -d "$db" > "$BACKUP_DIR/${db}_backup.sql" 2>/dev/null || {
        echo "  - No data found in $db"
    }
done

# Also try to export just the daily_bars table if it exists
echo ""
echo "Attempting to export daily_bars table..."
docker exec timescaledb psql -U postgres -d postgres -c "\copy (SELECT * FROM daily_bars) TO STDOUT WITH CSV HEADER" > "$BACKUP_DIR/daily_bars.csv" 2>/dev/null || {
    echo "  - daily_bars table not found in postgres database"
}

docker exec timescaledb psql -U postgres -d stock_screener -c "\copy (SELECT * FROM daily_bars) TO STDOUT WITH CSV HEADER" > "$BACKUP_DIR/daily_bars_stock_screener.csv" 2>/dev/null || {
    echo "  - daily_bars table not found in stock_screener database"
}

# Check what we backed up
echo ""
echo "=== Backup Summary ==="
echo "Files created:"
ls -la "$BACKUP_DIR"/

echo ""
echo "To restore this data after setting up the host database:"
echo "1. Run: ./setup_host_database.sh"
echo "2. Run: ./run_migrations.sh"
echo "3. Run: psql -h localhost -U postgres -d stock_screener < $BACKUP_DIR/stock_screener_backup.sql"
echo ""
echo "Or to import CSV data:"
echo "psql -h localhost -U postgres -d stock_screener -c \"\\copy daily_bars FROM '$BACKUP_DIR/daily_bars.csv' WITH CSV HEADER\""
