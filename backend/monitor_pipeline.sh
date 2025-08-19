#!/bin/bash

echo "Monitoring pipeline completion..."

while true; do
    if ! pgrep -f "run_screener_backtest_pipeline.py" > /dev/null; then
        echo "Pipeline completed!"
        break
    fi
    
    # Check progress
    completed=$(grep -c "Completed backtest for" pipeline_test.log 2>/dev/null || echo 0)
    echo "Progress: $completed/47 backtests completed"
    
    sleep 10
done

echo "Final pipeline results:"
tail -100 pipeline_test.log | grep -E "(Pipeline completed|SUMMARY|Total execution time|ERROR|successful|failed)" | tail -20