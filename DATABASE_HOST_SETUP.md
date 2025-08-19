# Database Setup - Host PostgreSQL Only (No Docker)

## Overview

This project uses PostgreSQL with TimescaleDB running directly on your host system. 
**No Docker containers are used for the database.**

Benefits:
- ✅ Data persists forever (survives reboots, no Docker volume issues)
- ✅ Better performance (no Docker overhead)
- ✅ Simple and reliable
- ✅ Standard PostgreSQL tools work directly

## Quick Setup

### 1. Install PostgreSQL on Your Host

```bash
cd backend
./install_postgres_host.sh
```

This installs:
- PostgreSQL 14
- TimescaleDB extension
- Creates the `stock_screener` database

### 2. Initialize Database Tables

```bash
./init_database.sh
```

This creates:
- `daily_bars` - Stock price data (TimescaleDB hypertable)
- `symbols` - Stock metadata
- `screener_results` - Screening results

### 3. Start the Application

```bash
cd ..
./start.sh
```

The start script will:
- Check PostgreSQL is running
- Create database if needed
- Initialize tables if needed
- Start backend and frontend

## Database Connection

- **Host**: localhost
- **Port**: 5432
- **Database**: stock_screener
- **User**: postgres
- **Password**: postgres

## Data Location

Your data is stored at:
- **Ubuntu/Debian**: `/var/lib/postgresql/14/main/`
- **CentOS/RHEL**: `/var/lib/pgsql/14/data/`

This is permanent storage on your filesystem.

## Common Commands

### Check PostgreSQL Status
```bash
sudo systemctl status postgresql
```

### Start/Stop PostgreSQL
```bash
sudo systemctl start postgresql
sudo systemctl stop postgresql
```

### Connect to Database
```bash
psql -h localhost -U postgres -d stock_screener
```

### Backup Database
```bash
pg_dump -h localhost -U postgres stock_screener > backup.sql
```

### Restore Database
```bash
psql -h localhost -U postgres stock_screener < backup.sql
```

## Loading Data

### 1. Discover Symbols
```bash
cd backend
./venv/bin/python scripts/universe_data_loader.py --discover
```

### 2. Load Historical Data
```bash
./venv/bin/python scripts/universe_data_loader.py --daily --start 2024-01-01 --end 2024-01-31
```

## Important Notes

1. **PostgreSQL runs on your host** - It's not in a Docker container
2. **Data is permanent** - Stored on your filesystem, not in Docker volumes
3. **Don't stop PostgreSQL** - The stop.sh script doesn't stop PostgreSQL (your data stays accessible)
4. **No Docker needed** - Everything runs natively for the database

## Troubleshooting

### PostgreSQL not running?
```bash
sudo systemctl start postgresql
```

### Permission denied?
The install script sets up trust authentication for localhost connections.

### Port 5432 already in use?
Check if you have Docker containers running:
```bash
docker ps | grep postgres
docker stop <container_name>
```

## Migration from Docker

If you were using Docker before:
1. Backup your data from Docker
2. Stop and remove Docker containers
3. Follow the setup above
4. Restore your data to host PostgreSQL