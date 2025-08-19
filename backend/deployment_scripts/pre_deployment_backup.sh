#!/bin/bash

# Pre-Deployment Backup Script for Enhanced Backtest Schema
# This script creates comprehensive backups before production deployment

set -e  # Exit on any error

# Configuration
BACKUP_DIR="/home/ahmed/TheUltimate/backend/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_URL=${DATABASE_URL:-"postgresql://postgres:postgres@localhost:5432/stock_screener"}

# Parse database URL
DB_HOST=$(echo $DB_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo $DB_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=$(echo $DB_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
DB_USER=$(echo $DB_URL | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')

echo "=== PRE-DEPLOYMENT BACKUP SCRIPT ==="
echo "Timestamp: $TIMESTAMP"
echo "Database: $DB_NAME on $DB_HOST:$DB_PORT"
echo "Backup Directory: $BACKUP_DIR"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo ""
echo "1. Creating full database backup..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -f "$BACKUP_DIR/full_database_backup_$TIMESTAMP.sql" \
    --clean --if-exists --verbose

echo ""
echo "2. Creating backtest results table backup..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -t market_structure_results \
    -f "$BACKUP_DIR/market_structure_results_backup_$TIMESTAMP.sql" \
    --data-only --verbose

echo ""
echo "3. Creating schema-only backup..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -s -f "$BACKUP_DIR/schema_only_backup_$TIMESTAMP.sql" \
    --verbose

echo ""
echo "4. Creating migrations backup..."
cp -r migrations "$BACKUP_DIR/migrations_backup_$TIMESTAMP"

echo ""
echo "5. Creating application code backup..."
tar -czf "$BACKUP_DIR/application_backup_$TIMESTAMP.tar.gz" \
    app/models/backtest.py \
    app/api/backtest.py \
    app/services/backtest_storage.py \
    app/services/backtest_manager.py \
    app/services/backtest_queue_manager.py \
    migrations/ \
    PRODUCTION_DEPLOYMENT_PLAN.md

echo ""
echo "6. Creating database state report..."
python3 << EOF > "$BACKUP_DIR/pre_deployment_state_$TIMESTAMP.txt"
import asyncio
import asyncpg
import os
from datetime import datetime

async def create_state_report():
    db_url = os.getenv('DATABASE_URL', '$DB_URL')
    conn = await asyncpg.connect(db_url)
    
    print(f"=== PRE-DEPLOYMENT DATABASE STATE REPORT ===")
    print(f"Generated: {datetime.now()}")
    print(f"Database: $DB_NAME")
    print("")
    
    # Migration status
    print("MIGRATION STATUS:")
    try:
        migrations = await conn.fetch('SELECT version, filename FROM schema_migrations ORDER BY version')
        for m in migrations:
            print(f"  Version {m['version']}: {m['filename']}")
    except:
        print("  No migrations table found")
    print("")
    
    # Table counts
    print("TABLE RECORD COUNTS:")
    tables = ['market_structure_results', 'screener_results', 'screener_cache']
    for table in tables:
        try:
            count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
            print(f"  {table}: {count} records")
        except:
            print(f"  {table}: Table not found")
    print("")
    
    # Schema details
    print("MARKET_STRUCTURE_RESULTS SCHEMA:")
    columns = await conn.fetch('''
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'market_structure_results'
        ORDER BY ordinal_position
    ''')
    for col in columns:
        print(f"  {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
    print("")
    
    # Index status
    print("INDEXES:")
    indexes = await conn.fetch('''
        SELECT indexname, indexdef FROM pg_indexes 
        WHERE tablename = 'market_structure_results'
        ORDER BY indexname
    ''')
    for idx in indexes:
        print(f"  {idx['indexname']}")
    
    await conn.close()

asyncio.run(create_state_report())
EOF

echo ""
echo "7. Verifying backup integrity..."
# Check that backup files exist and are not empty
for backup_file in "$BACKUP_DIR"/full_database_backup_$TIMESTAMP.sql \
                   "$BACKUP_DIR"/market_structure_results_backup_$TIMESTAMP.sql \
                   "$BACKUP_DIR"/schema_only_backup_$TIMESTAMP.sql; do
    if [[ -f "$backup_file" && -s "$backup_file" ]]; then
        echo "   ✅ $(basename "$backup_file") - $(du -h "$backup_file" | cut -f1)"
    else
        echo "   ❌ $(basename "$backup_file") - FAILED"
        exit 1
    fi
done

echo ""
echo "=== BACKUP COMPLETED SUCCESSFULLY ==="
echo "Backup location: $BACKUP_DIR"
echo "Files created:"
ls -la "$BACKUP_DIR"/*$TIMESTAMP*

echo ""
echo "✅ All backups verified and ready for deployment"
echo "🚀 Proceed with production deployment"