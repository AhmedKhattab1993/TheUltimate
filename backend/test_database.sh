#!/bin/bash
# Test database connection and tables

set -e

# Database connection parameters
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_NAME="${DATABASE_NAME:-stock_screener}"
DB_USER="${DATABASE_USER:-postgres}"
DB_PASS="${DATABASE_PASSWORD:-postgres}"

export PGPASSWORD=$DB_PASS

echo "=== Testing Database Connection ==="
echo ""

# Test connection
echo "1. Testing connection to $DB_NAME at $DB_HOST:$DB_PORT..."
if psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT 1" > /dev/null 2>&1; then
    echo "   ✓ Connection successful"
else
    echo "   ✗ Connection failed"
    exit 1
fi

# Check tables
echo ""
echo "2. Checking tables..."
TABLES=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "\dt" | grep -E "daily_bars|screener_results|symbols" | wc -l)
if [ "$TABLES" -ge "3" ]; then
    echo "   ✓ All required tables exist"
else
    echo "   ✗ Some tables are missing"
    echo "   Run ./init_database.sh to create them"
    exit 1
fi

# Check TimescaleDB
echo ""
echo "3. Checking TimescaleDB..."
HYPERTABLE=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM timescaledb_information.hypertables WHERE hypertable_name = 'daily_bars'" | tr -d ' ')
if [ "$HYPERTABLE" = "1" ]; then
    echo "   ✓ TimescaleDB hypertable configured"
else
    echo "   ✗ TimescaleDB hypertable not found"
fi

# Show table structure
echo ""
echo "4. Table structures:"
echo ""
echo "daily_bars columns:"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\d daily_bars" | grep -E "^ [a-z]" | head -10

# Check data
echo ""
echo "5. Data check:"
ROW_COUNT=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM daily_bars" | tr -d ' ')
echo "   - daily_bars rows: $ROW_COUNT"

SYMBOL_COUNT=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(DISTINCT symbol) FROM daily_bars" | tr -d ' ')
echo "   - unique symbols: $SYMBOL_COUNT"

if [ "$ROW_COUNT" -gt "0" ]; then
    echo ""
    echo "   Latest data:"
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT symbol, time, close, volume FROM daily_bars ORDER BY time DESC LIMIT 5"
fi

echo ""
echo "=== Database test complete ==="
echo ""
echo "Your database is ready for:"
echo "1. Loading data with universe_data_loader.py"
echo "2. Running the screener application"