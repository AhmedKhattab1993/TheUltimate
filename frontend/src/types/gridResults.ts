export interface GridScreeningResult {
  symbol: string
  price: number
  ma_20: number
  ma_50: number
  ma_200: number
  rsi_14: number
  gap_percent: number
  prev_day_dollar_volume: number
  relative_volume: number
}

export interface GridMarketStructureResult {
  symbol: string
  pivot_bars: number
  status: string
  total_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  backtest_id: string | null
}

export interface GridResultSummary {
  date: string
  screening_symbols: number
  backtest_count: number
  backtest_completed: number
  backtest_failed: number
  screening_time_ms: number | null
  backtest_time_ms: number | null
}

export interface GridResultDetail {
  date: string
  screening_results: GridScreeningResult[]
  backtest_results: GridMarketStructureResult[]
  total_screening_symbols: number
  total_backtests: number
}

export interface GridResultsListResponse {
  results: GridResultSummary[]
  total_count: number
  page: number
  page_size: number
}