#!/bin/bash
# Run optimization for multiple symbols individually

SYMBOLS=("AAPL" "MSFT" "GOOGL" "AMZN" "META" "TSLA" "NVDA")
PROJECT_DIR="/home/ahmed/TheUltimate/backend/lean/MarketStructure"
CONFIG_FILE="$PROJECT_DIR/config.json"

# Backup original config
cp "$CONFIG_FILE" "$CONFIG_FILE.bak"

for symbol in "${SYMBOLS[@]}"; do
    echo "========================================="
    echo "Optimizing for symbol: $symbol"
    echo "========================================="
    
    # Update config with current symbol
    jq --arg symbol "$symbol" '.parameters.symbols = $symbol' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
    
    # Run optimization for this symbol
    cd /home/ahmed/TheUltimate/backend/lean
    /home/ahmed/TheUltimate/backend/lean_venv/bin/lean optimize MarketStructure \
        --strategy "grid search" \
        --target "TotalPerformance.PortfolioStatistics.SharpeRatio" \
        --target-direction "max" \
        --parameter pivot_bars 1 9 1 \
        --max-concurrent-backtests 10 \
        --output "MarketStructure/optimizations/${symbol}_$(date +%Y%m%d_%H%M%S)"
    
    echo "Completed optimization for $symbol"
    echo ""
done

# Restore original config
mv "$CONFIG_FILE.bak" "$CONFIG_FILE"

echo "All optimizations complete!"