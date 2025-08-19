#!/bin/bash
# Simple database initialization script
# Creates tables needed by the current screener implementation

set -e

echo "=== Database Initialization Script ==="
echo "This script creates the tables needed by the stock screener"
echo ""

# Check if PostgreSQL is accessible
if ! command -v psql > /dev/null 2>&1; then
    echo "Error: psql command not found. Please install PostgreSQL:"
    echo "  Run: ./install_postgres_host.sh"
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "Error: PostgreSQL is not running on localhost:5432"
    echo "  Start it with: sudo systemctl start postgresql"
    exit 1
fi

# Database connection parameters
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_NAME="${DATABASE_NAME:-stock_screener}"
DB_USER="${DATABASE_USER:-postgres}"
DB_PASS="${DATABASE_PASSWORD:-postgres}"

export PGPASSWORD=$DB_PASS

echo "Connecting to database: $DB_NAME at $DB_HOST:$DB_PORT"
echo "(Using host PostgreSQL, not Docker)"

# Create database if it doesn't exist
echo "Creating database if it doesn't exist..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "CREATE DATABASE $DB_NAME"

# Create tables
echo "Creating tables..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << 'EOF'

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- Create daily_bars table (main table for stock data)
CREATE TABLE IF NOT EXISTS daily_bars (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open NUMERIC(10, 2) NOT NULL,
    high NUMERIC(10, 2) NOT NULL,
    low NUMERIC(10, 2) NOT NULL,
    close NUMERIC(10, 2) NOT NULL,
    volume BIGINT NOT NULL,
    vwap NUMERIC(10, 4),
    transactions INTEGER,
    adjusted BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT daily_bars_symbol_time_key UNIQUE (symbol, time)
);

-- Convert to hypertable if not already
SELECT create_hypertable('daily_bars', 'time', 
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_daily_bars_symbol_time ON daily_bars(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_daily_bars_time ON daily_bars(time DESC);
CREATE INDEX IF NOT EXISTS idx_daily_bars_symbol ON daily_bars(symbol);

-- Create screener_results table for saving screening results
CREATE TABLE IF NOT EXISTS screener_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbols TEXT[],
    filters JSONB,
    result_count INTEGER,
    processing_time FLOAT
);

-- Create symbols table for symbol metadata (optional but useful)
CREATE TABLE IF NOT EXISTS symbols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    exchange VARCHAR(50),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for symbols
CREATE INDEX IF NOT EXISTS idx_symbols_symbol ON symbols(symbol);
CREATE INDEX IF NOT EXISTS idx_symbols_active ON symbols(active);

-- Show created tables
\dt

EOF

echo ""
echo "=== Database initialization complete! ==="
echo ""
echo "Tables created:"
echo "  - daily_bars: Stores daily stock price data (TimescaleDB hypertable)"
echo "  - screener_results: Stores screening results"
echo "  - symbols: Stores stock symbols metadata"
echo ""
echo "Your database is ready!"
echo ""
echo "Next steps:"
echo "1. Run symbol discovery: cd /home/ahmed/TheUltimate/backend && ./venv/bin/python scripts/universe_data_loader.py --discover"
echo "2. Load historical data: ./venv/bin/python scripts/universe_data_loader.py --daily --start YYYY-MM-DD --end YYYY-MM-DD"