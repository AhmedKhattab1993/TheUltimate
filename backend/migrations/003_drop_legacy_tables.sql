-- Drop legacy tables/views that are no longer referenced after repository migration.
DROP VIEW IF EXISTS combined_screener_backtest_results;
DROP TABLE IF EXISTS screener_backtest_links;
DROP TABLE IF EXISTS grid_market_structure;
DROP TABLE IF EXISTS grid_screening;
