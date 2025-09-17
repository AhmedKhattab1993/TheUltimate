#!/bin/bash
# Wrapper script to run LEAN optimization with custom symbols

# Check if symbols are provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 \"SYMBOL1,SYMBOL2,SYMBOL3\""
    echo "Example: $0 \"AAPL,MSFT,GOOGL\""
    exit 1
fi

SYMBOLS=$1
PROJECT_DIR="/home/ahmed/TheUltimate/backend/lean/MarketStructure"
CONFIG_FILE="$PROJECT_DIR/config.json"

# Backup original config
cp "$CONFIG_FILE" "$CONFIG_FILE.bak"

# Update config with provided symbols
jq --arg symbols "$SYMBOLS" '.parameters.symbols = $symbols' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"

echo "Running optimization with symbols: $SYMBOLS"

# Run the optimization
cd /home/ahmed/TheUltimate/backend/lean
/home/ahmed/TheUltimate/backend/lean_venv/bin/lean optimize MarketStructure \
  --strategy "grid search" \
  --target "TotalPerformance.PortfolioStatistics.SharpeRatio" \
  --target-direction "max" \
  --parameter pivot_bars 1 9 1 \
  --max-concurrent-backtests 10

# Restore original config
mv "$CONFIG_FILE.bak" "$CONFIG_FILE"

echo "Optimization complete. Original config restored."