# Parallel Backtest Execution Comparison

## Problem: Config File Bottleneck

### Original Approach (test_parallel_backtests.py)
```
/lean/MarketStructure/
    ├── config.json  <-- SHARED FILE (Bottleneck!)
    └── All 5 backtests fight for this file
```

**Timeline:**
1. Backtest 1: Acquire lock → Update config → Wait 2s → Run
2. Backtest 2: Wait for lock... (blocked)
3. Backtest 3: Wait for lock... (blocked)  
4. Backtest 4: Wait for lock... (blocked)
5. Backtest 5: Wait for lock... (blocked)

**Result:** Serial execution disguised as parallel

## Solution: Isolated Project Directories

### New Approach (test_true_parallel_backtests.py)
```
/tmp/lean_parallel_tests/
    ├── MarketStructure_AAPL_abc123/
    │   └── config.json  (isolated)
    ├── MarketStructure_GOOGL_def456/
    │   └── config.json  (isolated)
    ├── MarketStructure_MSFT_ghi789/
    │   └── config.json  (isolated)
    ├── MarketStructure_AMZN_jkl012/
    │   └── config.json  (isolated)
    └── MarketStructure_META_mno345/
        └── config.json  (isolated)
```

**Timeline:**
1. All 5 backtests: Create isolated dirs → Update own config → Run
   (All happening simultaneously!)

**Result:** True parallel execution

## Key Differences

| Aspect | Original | Isolated Directories |
|--------|----------|---------------------|
| Config Files | 1 shared | 5 isolated |
| File Locking | Required | Not needed |
| Execution | Serial | True parallel |
| Scalability | Poor (O(n)) | Excellent (O(1)) |
| Race Conditions | Possible | Impossible |
| Speed | ~5x slower | Maximum speed |

## Performance Impact

For 5 backtests of 30 seconds each:
- **Original**: ~150 seconds (sequential due to locking)
- **Isolated**: ~30 seconds (true parallel)

## Usage

### Original (problematic):
```python
python test_parallel_backtests.py
```

### New (recommended):
```python
python test_true_parallel_backtests.py
```

## Architecture Benefits

1. **Zero Contention**: Each backtest owns its config
2. **Linear Scaling**: 100 backtests = same speed as 5
3. **Fault Isolation**: One crash doesn't affect others
4. **Easier Debugging**: Each run in separate directory
5. **CI/CD Compatible**: Standard pattern for parallel testing