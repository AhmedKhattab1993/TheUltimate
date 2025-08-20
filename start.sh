#!/bin/bash

# Stock Screener Startup Script
# Starts TimescaleDB, backend API, and frontend dev server

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
echo "Stock Screener Startup"
echo "========================================="
echo ""

# Create PID directory if it doesn't exist
mkdir -p "$PID_DIR"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."

# Check PostgreSQL is installed
if ! command_exists psql; then
    echo -e "${RED}Error: PostgreSQL is not installed${NC}"
    echo "Please run: ./backend/install_postgres_host.sh"
    exit 1
fi

# Check PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo -e "${RED}Error: PostgreSQL is not running${NC}"
    echo "Please start PostgreSQL: sudo systemctl start postgresql"
    exit 1
fi

if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

if ! command_exists npm; then
    echo -e "${RED}Error: npm is not installed${NC}"
    echo "Please install Node.js and npm: https://nodejs.org/"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites installed${NC}"
echo -e "${GREEN}✓ PostgreSQL is running on localhost:5432${NC}"
echo ""

# Check for port conflicts
echo "Checking port availability..."

# Port 5432 check is already done above
echo "PostgreSQL is running on localhost:5432"

if port_in_use 8000; then
    echo -e "${RED}Error: Port 8000 is already in use${NC}"
    echo "Please stop the service using port 8000 or change the backend port"
    exit 1
fi

if port_in_use 5173; then
    echo -e "${RED}Error: Port 5173 is already in use${NC}"
    echo "Please stop the service using port 5173 or change the frontend port"
    exit 1
fi

echo -e "${GREEN}✓ All required ports are available${NC}"
echo ""

# Check database and create if needed
echo "Checking database..."
if ! PGPASSWORD=postgres psql -h localhost -U postgres -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw stock_screener; then
    echo -e "${YELLOW}Creating database stock_screener...${NC}"
    PGPASSWORD=postgres psql -h localhost -U postgres -c "CREATE DATABASE stock_screener" 2>/dev/null || true
fi

# Check if tables exist
TABLE_COUNT=$(PGPASSWORD=postgres psql -h localhost -U postgres -d stock_screener -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('daily_bars', 'symbols')" 2>/dev/null | tr -d ' ' || echo "0")
if [ "$TABLE_COUNT" -lt "2" ]; then
    echo -e "${YELLOW}Database tables not found, initializing...${NC}"
    cd "$PROJECT_ROOT/backend"
    if [ -f "init_database.sh" ]; then
        ./init_database.sh
    else
        echo -e "${RED}Error: init_database.sh not found${NC}"
        exit 1
    fi
    cd "$PROJECT_ROOT"
fi

echo -e "${GREEN}✓ Database is ready${NC}"

# Setup Python virtual environment for backend
echo ""
echo "Setting up backend..."
cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing backend dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: No .env file found in backend directory${NC}"
    echo "Creating default .env file..."
    cat > .env << EOF
# Database configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/stock_screener

# Polygon API configuration
POLYGON_API_KEY=your_polygon_api_key_here

# Application settings
DEBUG=False
LOG_LEVEL=INFO
EOF
    echo -e "${YELLOW}Please update the POLYGON_API_KEY in backend/.env${NC}"
fi

# Start backend
echo ""
echo "Starting backend API server..."
nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_DIR/backend.pid"

# Wait for backend to start
echo "Waiting for backend to be ready..."
RETRIES=30
until curl -s http://localhost:8000/ > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
    echo -n "."
    sleep 1
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    echo -e "\n${RED}Error: Backend failed to start${NC}"
    echo "Check backend.log for details"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo -e "\n${GREEN}✓ Backend API started successfully (PID: $BACKEND_PID)${NC}"

# Setup and start frontend
echo ""
echo "Setting up frontend..."
cd "$PROJECT_ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
else
    echo "Frontend dependencies already installed"
fi

# Start frontend
echo ""
echo "Starting frontend development server..."
nohup npm run dev > "$PROJECT_ROOT/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$PID_DIR/frontend.pid"

# Wait for frontend to start
echo "Waiting for frontend to be ready..."
RETRIES=30
until curl -s http://localhost:5173 > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
    echo -n "."
    sleep 1
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    echo -e "\n${RED}Error: Frontend failed to start${NC}"
    echo "Check frontend.log for details"
    kill $FRONTEND_PID 2>/dev/null
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo -e "\n${GREEN}✓ Frontend dev server started successfully (PID: $FRONTEND_PID)${NC}"

# Summary
echo ""
echo "========================================="
echo -e "${GREEN}Stock Screener Started Successfully!${NC}"
echo "========================================="
echo ""
echo "Services running:"
echo "  • PostgreSQL: localhost:5432 (running on host)"
echo "  • Backend API: http://localhost:8000"
echo "  • Frontend:    http://localhost:5173"
echo ""
echo "API Documentation: http://localhost:8000/docs"
echo ""
echo "Logs:"
echo "  • Backend:  $PROJECT_ROOT/backend.log"
echo "  • Frontend: $PROJECT_ROOT/frontend.log"
echo ""
echo "To stop all services, run: ./stop-screener.sh"
echo ""

# Keep track of services
echo "BACKEND_PID=$BACKEND_PID" > "$PID_DIR/services.env"
echo "FRONTEND_PID=$FRONTEND_PID" >> "$PID_DIR/services.env"