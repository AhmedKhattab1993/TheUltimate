# Database Quick Start Guide

## Simple Setup - Just 3 Steps

### 1. Initialize the Database
```bash
cd backend
./init_database.sh
```

This creates:
- `daily_bars` table for stock data
- `screener_results` table for screening results  
- `symbols` table for metadata
- All necessary indexes and TimescaleDB configuration

### 2. Test the Database
```bash
./test_database.sh
```

This verifies:
- Database connection is working
- All tables are created
- TimescaleDB is configured

### 3. Load Data
Use your existing data loader:
```bash
cd scripts
python universe_data_loader.py
```

## That's it!

Your database is ready and will work with:
- The existing screener implementation
- The data loading scripts
- All the current code

## Database Details

- **Host**: localhost
- **Port**: 5432
- **Database**: stock_screener
- **User**: postgres
- **Password**: postgres

## Tables Created

1. **daily_bars** - Main table for stock price data
   - time, symbol, open, high, low, close, volume, vwap
   - Configured as TimescaleDB hypertable

2. **screener_results** - Stores screening results
   - Used by the screener to save results

3. **symbols** - Stock symbols metadata
   - symbol, name, exchange, active status

## No Docker, No Data Loss

The database runs on your host system, so:
- Data persists across reboots
- No Docker volumes to lose
- Standard PostgreSQL tools work
- Better performance