#!/bin/bash

# Stock Screener Shutdown Script
# Stops frontend, backend, and TimescaleDB container

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
PID_DIR="$PROJECT_ROOT/.pids"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Stock Screener Shutdown"
echo "========================================="
echo ""

# Function to stop a process safely
stop_process() {
    local name=$1
    local pid_file=$2
    
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Stopping $name (PID: $PID)..."
            kill $PID 2>/dev/null || true
            
            # Wait for process to stop
            RETRIES=10
            while ps -p $PID > /dev/null 2>&1 && [ $RETRIES -gt 0 ]; do
                sleep 1
                RETRIES=$((RETRIES - 1))
            done
            
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "${YELLOW}Process didn't stop gracefully, forcing kill...${NC}"
                kill -9 $PID 2>/dev/null || true
            fi
            
            echo -e "${GREEN}✓ $name stopped${NC}"
        else
            echo -e "${YELLOW}$name was not running (PID: $PID)${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}No PID file found for $name${NC}"
    fi
}

# Stop Frontend
echo "Stopping frontend..."
stop_process "Frontend" "$PID_DIR/frontend.pid"

# Stop Backend
echo ""
echo "Stopping backend..."
stop_process "Backend" "$PID_DIR/backend.pid"

# Check for any remaining python/node processes
echo ""
echo "Checking for orphaned processes..."

# Find uvicorn processes
UVICORN_PIDS=$(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
if [ -n "$UVICORN_PIDS" ]; then
    echo "Found orphaned backend processes, stopping..."
    echo "$UVICORN_PIDS" | xargs kill 2>/dev/null || true
    echo -e "${GREEN}✓ Orphaned backend processes stopped${NC}"
fi

# Find npm/node processes for the frontend
NODE_PIDS=$(pgrep -f "npm run dev" 2>/dev/null || true)
if [ -n "$NODE_PIDS" ]; then
    echo "Found orphaned frontend processes, stopping..."
    echo "$NODE_PIDS" | xargs kill 2>/dev/null || true
    echo -e "${GREEN}✓ Orphaned frontend processes stopped${NC}"
fi

# Find vite processes
VITE_PIDS=$(pgrep -f "node.*vite" 2>/dev/null || true)
if [ -n "$VITE_PIDS" ]; then
    echo "Found orphaned vite processes, stopping..."
    echo "$VITE_PIDS" | xargs kill 2>/dev/null || true
    echo -e "${GREEN}✓ Orphaned vite processes stopped${NC}"
fi

# PostgreSQL runs on host - we don't stop it
echo ""
echo "Note: PostgreSQL is running on the host system."
echo "It will continue running to preserve your data."
echo "To stop PostgreSQL manually: sudo systemctl stop postgresql"

# Clean up PID files and directory
echo ""
echo "Cleaning up PID files..."
rm -f "$PID_DIR"/*.pid
rm -f "$PID_DIR"/services.env
rmdir "$PID_DIR" 2>/dev/null || true

# Clean up log files (optional)
read -p "Do you want to remove log files? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$PROJECT_ROOT/backend.log"
    rm -f "$PROJECT_ROOT/frontend.log"
    echo -e "${GREEN}✓ Log files removed${NC}"
fi

# Summary
echo ""
echo "========================================="
echo -e "${GREEN}Stock Screener Stopped Successfully!${NC}"
echo "========================================="
echo ""
echo "All services have been stopped."
echo ""
echo "To restart the services, run: ./start.sh"
echo ""

# Show PostgreSQL status
if command -v pg_isready >/dev/null 2>&1; then
    echo "PostgreSQL status:"
    if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
        echo "  PostgreSQL is running on localhost:5432"
        echo "  Your data is safely stored on the host filesystem"
    else
        echo "  PostgreSQL is not running"
    fi
fi