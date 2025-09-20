ALTER TABLE backtest_results
ADD CONSTRAINT backtest_results_run_symbol_unique UNIQUE (run_id, symbol);
