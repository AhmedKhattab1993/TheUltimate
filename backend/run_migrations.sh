#!/bin/bash
# Script to run database migrations

set -e

echo "Running database migrations..."

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "Error: PostgreSQL is not running on localhost:5432"
    echo "Please run ./setup_host_database.sh first"
    exit 1
fi

# Run the initial schema
echo "Creating database schema..."
psql -h localhost -U postgres -d stock_screener -f migrations/001_initial_schema.sql

echo ""
echo "=== Migrations Complete ==="
echo "Database schema has been created successfully."
echo ""
echo "Tables created:"
psql -h localhost -U postgres -d stock_screener -c "\dt" | grep -E "daily_bars|minute_bars|symbols|market_calendar"
