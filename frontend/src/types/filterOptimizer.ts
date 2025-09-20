// Types for filter optimization

export const OptimizationTarget = {
  SHARPE_RATIO: 'sharpe_ratio',
  TOTAL_RETURN: 'total_return',
  WIN_RATE: 'win_rate',
  PROFIT_FACTOR: 'profit_factor',
  MIN_DRAWDOWN: 'min_drawdown',
  CUSTOM: 'custom'
} as const

export type OptimizationTarget = typeof OptimizationTarget[keyof typeof OptimizationTarget]

export interface FilterRange {
  min_value: number
  max_value: number
  step: number
}

export interface FilterSearchSpace {
  price_range?: FilterRange
  rsi_range?: FilterRange
  gap_range?: FilterRange
  volume_range?: FilterRange
  rel_volume_range?: FilterRange
  pivot_bars_range?: FilterRange
  ma_periods?: number[]
  ma_conditions?: string[]
}

export interface OptimizationRequest {
  start_date: string
  end_date: string
  target: OptimizationTarget
  custom_formula?: string
  search_space: FilterSearchSpace
  max_results?: number
  min_symbols_required?: number
  pivot_bars?: number
}

export interface FilterCombination {
  price_range?: { min?: number; max?: number }
  rsi_range?: { min?: number; max?: number }
  gap_range?: { min?: number; max?: number }
  volume_min?: number
  rel_volume_min?: number
  ma_condition?: { period: number; condition: 'above' | 'below' }
}

export interface OptimizationResult {
  rank: number
  filter_combination: FilterCombination
  avg_sharpe_ratio: number
  avg_total_return: number
  avg_win_rate: number
  avg_profit_factor: number
  avg_max_drawdown: number
  total_symbols_matched: number
  total_backtests: number
  target_score: number
  sample_symbols: string[]
}

export interface OptimizationResponse {
  request_summary: any
  results: OptimizationResult[]
  total_combinations_tested: number
  execution_time_ms: number
  date_range_analyzed: { start: string; end: string }
  optimization_target: string
  best_combination?: OptimizationResult
}

export interface SuggestedRanges {
  date_range: { start: string; end: string }
  data_summary: {
    price_range: [number, number]
    rsi_range: [number, number]
    gap_range: [number, number]
    volume_range: [number, number]
    rel_volume_range: [number, number]
  }
  suggested_ranges: {
    price_range: {
      min: { suggested_min: number; suggested_max: number; suggested_step: number }
      max: { suggested_min: number; suggested_max: number; suggested_step: number }
    }
    rsi_range: {
      min: { suggested_min: number; suggested_max: number; suggested_step: number }
      max: { suggested_min: number; suggested_max: number; suggested_step: number }
    }
    gap_range: {
      min: { suggested_min: number; suggested_max: number; suggested_step: number }
      max: { suggested_min: number; suggested_max: number; suggested_step: number }
    }
    volume: {
      min: { suggested_min: number; suggested_max: number; suggested_step: number }
    }
    relative_volume: {
      min: { suggested_min: number; suggested_max: number; suggested_step: number }
    }
  }
}
