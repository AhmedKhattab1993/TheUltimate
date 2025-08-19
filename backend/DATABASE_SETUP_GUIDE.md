# Database Setup Guide - Permanent Data Storage Solution

## Problem Summary

We were experiencing repeated data loss due to:
1. Database running in Docker containers (ephemeral by nature)
2. Docker volumes being accidentally deleted
3. Confusion between database names and table names
4. Multiple configuration files with different settings

## Solution: Host-Based PostgreSQL/TimescaleDB

We're moving the database to run directly on the host system for:
- **Permanent data storage** - Data persists across reboots
- **Better performance** - No Docker overhead
- **Easier backup/restore** - Standard PostgreSQL tools
- **No accidental data loss** - No Docker volumes to delete

## Setup Instructions

### 1. Backup Existing Data (if any)
```bash
./backup_docker_data.sh
```

### 2. Install PostgreSQL/TimescaleDB on Host
```bash
./setup_host_database.sh
```

This script will:
- Install PostgreSQL 14 and TimescaleDB
- Configure authentication
- Create the `stock_screener` database
- Set up proper permissions
- Update the .env file

### 3. Run Database Migrations
```bash
./run_migrations.sh
```

This creates all necessary tables:
- `daily_bars` - Daily stock data
- `minute_bars` - Minute-level stock data
- `symbols` - Stock symbols metadata
- `market_calendar` - Trading calendar
- And more...

### 4. Update start.sh
The start.sh script should be updated to:
- NOT start Docker containers for the database
- Check that PostgreSQL is running on the host
- Start only the application services

## Database Configuration

All database configuration is now centralized in `.env`:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/stock_screener
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=stock_screener
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
```

## Data Location

Your data is now stored at:
- **Ubuntu/Debian**: `/var/lib/postgresql/14/main/`
- **RHEL/CentOS**: `/var/lib/pgsql/14/data/`

This location is managed by the system and will persist across reboots.

## Maintenance Commands

### Check Database Status
```bash
sudo systemctl status postgresql
```

### Start/Stop Database
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
pg_dump -h localhost -U postgres stock_screener > backup_$(date +%Y%m%d).sql
```

### Restore Database
```bash
psql -h localhost -U postgres stock_screener < backup_20240810.sql
```

## Important Notes

1. **No More Docker for Database**: The database runs directly on your system
2. **Automatic Start**: PostgreSQL starts automatically when your system boots
3. **Data Persistence**: Your data is safe even if you delete all Docker containers
4. **Performance**: Direct host access is faster than Docker networking

## Troubleshooting

### Port Already in Use
If port 5432 is already in use:
1. Check what's using it: `sudo lsof -i :5432`
2. Stop the Docker container: `docker stop timescaledb`
3. Remove it: `docker rm timescaledb`

### Permission Denied
If you get permission errors:
1. Check PostgreSQL user: `sudo -u postgres psql`
2. Grant permissions: `GRANT ALL ON DATABASE stock_screener TO postgres;`

### Connection Refused
If connection is refused:
1. Check PostgreSQL is running: `sudo systemctl status postgresql`
2. Check pg_hba.conf allows local connections
3. Restart PostgreSQL: `sudo systemctl restart postgresql`
