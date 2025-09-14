# Testing Mode for Grid Analysis

Testing mode allows you to run grid analysis on a limited set of symbols for faster testing and development.

## Features

- Limits processing to 10 major symbols (AAPL, TSLA, AMZN, NVDA, MSFT, GOOGL, META, SPY, QQQ, AMD)
- Significantly reduces processing time for testing
- Same functionality as full mode but with fewer symbols

## How to Enable/Disable

### Method 1: Environment Variable

```bash
# Enable testing mode
export TESTING_MODE=true

# Disable testing mode
unset TESTING_MODE
```

### Method 2: Using the toggle script

```bash
# Enable testing mode
./toggle_testing_mode.sh on

# Disable testing mode
./toggle_testing_mode.sh off

# Check current status
./toggle_testing_mode.sh
```

### Method 3: In Python scripts

```python
import os
os.environ['TESTING_MODE'] = 'true'
```

### Method 4: Using .env file

Create a `.env` file in the backend directory:
```
TESTING_MODE=true
```

## Testing Symbols

The default testing symbols are:
- **AAPL** - Apple Inc.
- **TSLA** - Tesla Inc.
- **AMZN** - Amazon.com Inc.
- **NVDA** - NVIDIA Corporation
- **MSFT** - Microsoft Corporation
- **GOOGL** - Alphabet Inc.
- **META** - Meta Platforms Inc.
- **SPY** - SPDR S&P 500 ETF
- **QQQ** - Invesco QQQ Trust
- **AMD** - Advanced Micro Devices Inc.

## Example Usage

```bash
# Run grid analysis in testing mode
TESTING_MODE=true python scripts/run_grid_analysis.py --date 2025-09-10

# Or source the testing environment
source .env.testing
python scripts/run_grid_analysis.py --date 2025-09-10
```

When testing mode is enabled, you'll see a banner at the start:
```
************************************************************
TESTING MODE ENABLED
Limited to symbols: AAPL, TSLA, AMZN, NVDA, MSFT, GOOGL, META, SPY, QQQ, AMD
************************************************************
```

## Performance Comparison

- **Full Mode**: ~11,000+ symbols → ~1100 minutes for full grid analysis
- **Testing Mode**: 10 symbols → ~10 minutes for full grid analysis

## Notes

- Testing mode affects both screening and backtesting phases
- Results are stored in the same database tables as full mode
- Perfect for development, debugging, and quick testing of new features