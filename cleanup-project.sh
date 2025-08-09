#!/bin/bash

# Stock Screener Project Cleanup Script
# Removes old/unused files while preserving simple screener implementation

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

echo "========================================="
echo "Stock Screener Project Cleanup"
echo "========================================="
echo "Project root: $PROJECT_ROOT"
echo ""

# Confirmation prompt
read -p "This will remove old files and keep only the simple screener implementation. Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Starting cleanup..."
echo ""

# Backend cleanup
echo "Cleaning backend files..."
cd "$PROJECT_ROOT/backend"

# Remove old API files
echo "  - Removing old API files..."
rm -f app/api/screener.py
rm -f app/api/screener_simple.py
rm -f app/api/test_screener.py

# Remove backup files
echo "  - Removing backup files..."
find app/core -name "*_backup.py" -type f -delete 2>/dev/null || true

# Remove enhanced filter implementations
echo "  - Removing enhanced filter implementations..."
rm -f app/core/enhanced_filters.py
rm -f app/core/day_trading_filters.py
rm -f app/core/trading_filters.py
rm -f app/core/filters.py
rm -f app/core/filter_analyzer.py
rm -f app/core/day_trading_filters_backup.py
rm -f app/core/filters_backup.py
rm -f app/core/trading_filters_backup.py

# Remove old service files
echo "  - Removing old service files..."
rm -f app/services/test_enhanced_screener.py
rm -f app/services/test_enhanced_screener_comprehensive.py
rm -f app/services/chunked_data_loader.py
rm -f app/services/filter_pipeline.py
rm -f app/services/screen_manager.py
rm -f app/services/test_screener.py
rm -f app/services/test_polygon_client.py

# Remove old model files
echo "  - Removing old request models..."
rm -f app/models/requests.py

# Remove examples directory
echo "  - Removing examples directories..."
rm -rf app/examples
rm -rf examples

# Remove test files
echo "  - Removing test files..."
rm -f test_*.py
rm -f api_*.py
rm -f check_*.py
rm -f comprehensive_*.py
rm -f demo_*.py
rm -f example_*.py
rm -f final_*.py
rm -f gap_*.py
rm -f working_*.py
rm -f simple_test.py
rm -f streaming_*.py
rm -f performance_*.py
rm -f load_*.py
rm -f init_database.py
rm -f test_*.sh
rm -f test_*.json

# Remove documentation files (excluding .claude)
echo "  - Removing documentation files (excluding .claude)..."
find . -maxdepth 1 -name "*.md" -type f -delete 2>/dev/null || true
find app -name "*.md" -type f -delete 2>/dev/null || true
find docs -name "*.md" -type f -delete 2>/dev/null || true
find scripts -name "*.md" -type f -delete 2>/dev/null || true

# Remove log files
echo "  - Removing log files..."
rm -f *.log
rm -f *.txt

# Remove cache directories
echo "  - Removing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Frontend cleanup
echo ""
echo "Cleaning frontend files..."
cd "$PROJECT_ROOT/frontend"

# Remove old components
echo "  - Removing old components..."
rm -f src/components/StockScreener.tsx
rm -f src/components/StockScreenerEnhanced.tsx
rm -f src/components/SimpleStockScreener.test.tsx

# Remove log files
echo "  - Removing log files..."
rm -f *.log

# Remove documentation (excluding .claude)
echo "  - Removing documentation files..."
find . -maxdepth 1 -name "*.md" -type f -delete 2>/dev/null || true

# Remove test files
echo "  - Removing test files..."
rm -f test_*.py
rm -f test_*.cjs
rm -f test_*.md

# Root directory cleanup
echo ""
echo "Cleaning root directory files..."
cd "$PROJECT_ROOT"

# Remove documentation files (excluding .claude and README.md)
echo "  - Removing documentation files (keeping README.md)..."
find . -maxdepth 1 -name "*.md" -type f ! -name "README.md" -delete 2>/dev/null || true

# Remove test files
echo "  - Removing test files..."
rm -f test_*.py
rm -f test_*.sh

# Remove old scripts
echo "  - Removing old scripts..."
rm -f start.py
rm -f start.sh
rm -f ensure_database.sh

# Summary
echo ""
echo "========================================="
echo "Cleanup Complete!"
echo "========================================="
echo ""
echo "Preserved files:"
echo "  - Backend: simple_screener.py, simple_filters.py, simple_requests.py"
echo "  - Frontend: SimpleStockScreener.tsx and related components"
echo "  - Database: TimescaleDB configuration and migrations"
echo "  - .claude directory with all its contents"
echo "  - README.md in root directory"
echo ""
echo "Removed:"
echo "  - Old API implementations (screener.py, screener_simple.py)"
echo "  - Backup files (*_backup.py)"
echo "  - Enhanced filter implementations"
echo "  - Test files and logs"
echo "  - Documentation files (except .claude/* and root README.md)"
echo "  - Examples directories"
echo "  - Python cache directories"
echo ""