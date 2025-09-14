-- Grid Analysis Tables Migration
-- Creates tables for storing screening values and backtest results

-- Grid Screening Table
CREATE TABLE IF NOT EXISTS grid_screening (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    
    -- Price data
    price DECIMAL(10, 2),  -- Close price
    
    -- Moving averages
    ma_20 DECIMAL(10, 2),
    ma_50 DECIMAL(10, 2),
    ma_200 DECIMAL(10, 2),
    
    -- Technical indicators
    rsi_14 DECIMAL(5, 2),  -- RSI value (0-100)
    gap_percent DECIMAL(10, 2),  -- Gap % from previous close
    
    -- Volume metrics
    prev_day_dollar_volume DECIMAL(20, 2),
    relative_volume DECIMAL(10, 2),  -- 2-day / 20-day ratio
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicates
    CONSTRAINT unique_grid_screening_symbol_date UNIQUE(symbol, date)
);

-- Indexes for efficient querying
CREATE INDEX idx_grid_screening_date ON grid_screening(date);
CREATE INDEX idx_grid_screening_symbol ON grid_screening(symbol);
CREATE INDEX idx_grid_screening_symbol_date ON grid_screening(symbol, date);

-- Grid Market Structure Table
CREATE TABLE IF NOT EXISTS grid_market_structure (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    backtest_date DATE NOT NULL,
    
    -- Strategy parameters
    strategy VARCHAR(50) DEFAULT 'market_structure',
    lower_timeframe INTEGER DEFAULT 1,  -- in minutes
    pivot_bars INTEGER NOT NULL,
    
    -- Key performance metrics
    total_return DECIMAL(10, 2),
    sharpe_ratio DECIMAL(10, 2),
    max_drawdown DECIMAL(10, 2),
    win_rate DECIMAL(5, 2),
    profit_factor DECIMAL(10, 2),
    total_trades INTEGER,
    
    -- Full statistics JSON for detailed analysis
    statistics JSONB,
    
    -- Execution metadata
    execution_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicate runs
    CONSTRAINT unique_grid_ms_symbol_date_params UNIQUE(symbol, backtest_date, pivot_bars)
);

-- Indexes for analysis
CREATE INDEX idx_grid_ms_symbol_date ON grid_market_structure(symbol, backtest_date);
CREATE INDEX idx_grid_ms_pivot_bars ON grid_market_structure(pivot_bars);
CREATE INDEX idx_grid_ms_total_return ON grid_market_structure(total_return DESC);
CREATE INDEX idx_grid_ms_sharpe_ratio ON grid_market_structure(sharpe_ratio DESC);

-- Combined view for frontend
CREATE VIEW grid_analysis_combined AS
SELECT 
    gs.symbol,
    gs.date,
    -- Screening values
    gs.price,
    gs.ma_20,
    gs.ma_50,
    gs.ma_200,
    gs.rsi_14,
    gs.gap_percent,
    gs.prev_day_dollar_volume,
    gs.relative_volume,
    -- Backtest results
    gms.pivot_bars,
    gms.total_return,
    gms.sharpe_ratio,
    gms.max_drawdown,
    gms.win_rate,
    gms.profit_factor,
    gms.total_trades,
    gms.execution_time_ms
FROM grid_screening gs
LEFT JOIN grid_market_structure gms 
    ON gs.symbol = gms.symbol 
    AND gs.date = gms.backtest_date
ORDER BY gs.date DESC, gs.symbol, gms.pivot_bars;