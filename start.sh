#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Stock Screener Application...${NC}\n"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${RED}Shutting down...${NC}"
    # Kill all child processes
    pkill -P $$
    exit
}

# Set trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Check if backend dependencies are installed
echo -e "${BLUE}Checking backend dependencies...${NC}"
cd backend
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${RED}Backend dependencies not installed. Installing...${NC}"
    python3 -m pip install --user --break-system-packages -r requirements.txt
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: backend/.env file not found!${NC}"
    echo "Please create it from .env.example and add your Polygon API key"
    exit 1
fi

# Start backend
echo -e "${GREEN}Starting backend server on http://localhost:8000...${NC}"
python3 run.py &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
echo -e "${BLUE}Waiting for backend to start...${NC}"
sleep 5

# Check if frontend dependencies are installed
echo -e "${BLUE}Checking frontend dependencies...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    echo -e "${RED}Frontend dependencies not installed. Installing...${NC}"
    npm install
fi

# Start frontend
echo -e "${GREEN}Starting frontend on http://localhost:5173...${NC}"
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "\n${GREEN}✨ Stock Screener is running!${NC}"
echo -e "${GREEN}📊 Frontend:${NC}"
echo -e "${GREEN}   - Local: http://localhost:5173${NC}"
echo -e "${GREEN}   - Public: http://34.125.88.131:5173${NC}"
echo -e "${GREEN}🔧 Backend API:${NC}"
echo -e "${GREEN}   - Local: http://localhost:8000${NC}"
echo -e "${GREEN}   - Public: http://34.125.88.131:8000${NC}"
echo -e "${GREEN}📚 API Docs: http://34.125.88.131:8000/docs${NC}"
echo -e "\n${BLUE}Press Ctrl+C to stop all services${NC}\n"

# Wait for user to stop
wait