CREATE TABLE run_sessions (
    id UUID PRIMARY KEY,
    job_type TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL,
    result_path TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_run_sessions_created_at ON run_sessions (created_at DESC);
CREATE INDEX idx_run_sessions_strategy ON run_sessions (strategy_name, created_at DESC);

CREATE TABLE run_targets (
    id UUID PRIMARY KEY,
    run_id UUID REFERENCES run_sessions(id) ON DELETE CASCADE,
    symbol TEXT,
    parameters JSONB DEFAULT '{}'::jsonb,
    UNIQUE (run_id, symbol)
);

CREATE INDEX idx_run_targets_run ON run_targets (run_id);

CREATE TABLE run_metrics (
    id UUID PRIMARY KEY,
    run_id UUID REFERENCES run_sessions(id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL,
    metric_value DOUBLE PRECISION,
    metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE (run_id, metric_key)
);

CREATE INDEX idx_run_metrics_run ON run_metrics (run_id);

CREATE TABLE screener_runs (
    id UUID PRIMARY KEY,
    session_id UUID,
    run_id UUID REFERENCES run_sessions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filters JSONB NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    symbol_count INTEGER DEFAULT 0
);

CREATE INDEX idx_screener_runs_created_at ON screener_runs (created_at DESC);
CREATE INDEX idx_screener_runs_session ON screener_runs (session_id);

CREATE TABLE screener_results (
    id UUID PRIMARY KEY,
    screener_run_id UUID REFERENCES screener_runs(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    metrics JSONB DEFAULT '{}'::jsonb,
    rank INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_screener_results_unique ON screener_results (screener_run_id, symbol);

CREATE TABLE backtest_results (
    id UUID PRIMARY KEY,
    run_id UUID REFERENCES run_sessions(id) ON DELETE CASCADE,
    symbol TEXT,
    parameters JSONB DEFAULT '{}'::jsonb,
    metrics JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_backtest_results_run ON backtest_results (run_id);

CREATE VIEW combined_screener_backtest AS
SELECT
    sr.id AS screener_result_id,
    sr.symbol,
    sr.metrics,
    br.metrics AS backtest_metrics,
    sr.created_at,
    br.created_at AS backtest_created_at,
    sr.screener_run_id
FROM screener_results sr
LEFT JOIN backtest_results br ON br.run_id = sr.screener_run_id;
