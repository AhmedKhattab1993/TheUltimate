#!/bin/bash
# Toggle testing mode on/off

if [ "$1" = "on" ]; then
    echo "Enabling testing mode..."
    export TESTING_MODE=true
    echo "Testing mode is now ON"
    echo "Limited to symbols: AAPL, TSLA, AMZN, NVDA, MSFT, GOOGL, META, SPY, QQQ, AMD"
elif [ "$1" = "off" ]; then
    echo "Disabling testing mode..."
    unset TESTING_MODE
    echo "Testing mode is now OFF"
    echo "All symbols will be processed"
else
    echo "Usage: $0 [on|off]"
    echo "Current TESTING_MODE: ${TESTING_MODE:-false}"
fi