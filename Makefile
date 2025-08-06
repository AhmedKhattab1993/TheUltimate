.PHONY: help install start stop backend frontend test clean

# Default target
help:
	@echo "Stock Screener - Available Commands:"
	@echo "  make install  - Install all dependencies"
	@echo "  make start    - Start both backend and frontend"
	@echo "  make stop     - Stop all services"
	@echo "  make backend  - Start only backend"
	@echo "  make frontend - Start only frontend"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Clean cache and temp files"

# Install all dependencies
install:
	@echo "Installing backend dependencies..."
	cd backend && python3 -m pip install --user --break-system-packages -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "✅ All dependencies installed!"

# Start everything
start:
	@python3 start.py

# Stop all services
stop:
	@echo "Stopping all services..."
	@pkill -f "python3 run.py" || true
	@pkill -f "npm run dev" || true
	@pkill -f "vite" || true
	@echo "✅ All services stopped"

# Start only backend
backend:
	cd backend && python3 run.py

# Start only frontend
frontend:
	cd frontend && npm run dev

# Run tests
test:
	@echo "Running backend tests..."
	cd backend && python3 -m pytest
	@echo "Testing API endpoints..."
	python3 test_screener.py

# Clean cache and temp files
clean:
	@echo "Cleaning Python cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleaned!"