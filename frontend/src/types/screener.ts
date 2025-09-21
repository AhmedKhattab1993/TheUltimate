// Enhanced type definitions for the simple screener filters

export interface SimplePriceRangeFilter {
  min_price?: number
  max_price?: number
  step?: number
}

export interface PriceVsMAFilterConfig {
  ma_period: 20 | 50 | 200
  min_ratio?: number
  max_ratio?: number
  step_ratio?: number
  /** legacy field */
  period?: number
  /** legacy field */
  condition?: 'above' | 'below'
}

export type PriceVsMAFilter = PriceVsMAFilterConfig | PriceVsMAFilterConfig[]

export interface RSIFilterConfig {
  rsi_period: number
  min_value?: number
  max_value?: number
  step_value?: number
  /** legacy fields */
  period?: number
  threshold?: number
  condition?: 'above' | 'below'
}

export type RSIFilter = RSIFilterConfig | RSIFilterConfig[]

export interface GapFilter {
  min_gap_percent?: number
  max_gap_percent?: number
  step_gap_percent?: number
  direction: 'up' | 'down' | 'both'
  /** legacy fields */
  gap_threshold?: number
}

export interface PreviousDayDollarVolumeFilter {
  min_dollar_volume?: number
  max_dollar_volume?: number
  step_dollar_volume?: number
  /** legacy field */
  minDollarVolume?: number
}

export interface RelativeVolumeFilter {
  recent_days: number
  lookback_days: number
  min_ratio?: number
  max_ratio?: number
  step_ratio?: number
  /** legacy fields */
  recentDays?: number
  lookbackDays?: number
}

export interface SimpleFilters {
  simple_price_range?: SimplePriceRangeFilter
  price_vs_ma?: PriceVsMAFilter
  rsi?: RSIFilter
  gap?: GapFilter
  prev_day_dollar_volume?: PreviousDayDollarVolumeFilter
  relative_volume?: RelativeVolumeFilter
}

export interface EnhancedScreenerRequest {
  start_date: string
  end_date: string
  use_all_us_stocks: boolean
  filters: SimpleFilters
}

export interface ScreenResult {
  symbol: string
  qualifying_dates: string[]
  metrics: {
    latest_price?: number
    latest_volume?: number
    simple_price_range?: boolean
    price_vs_ma?: number
    rsi?: number
    [key: string]: any
  }
}

export interface PerformanceMetrics {
  data_fetch_time_ms: number
  screening_time_ms: number
  total_execution_time_ms: number
  used_bulk_endpoint: boolean
  symbols_fetched: number
  symbols_failed: number
}

export interface EnhancedScreenerResponse {
  request_date: string
  total_symbols_screened: number
  total_qualifying_stocks: number
  results: ScreenResult[]
  execution_time_ms: number
  performance_metrics?: PerformanceMetrics
}


export interface ValidationError {
  field: string
  message: string
}

export interface ValidationResult {
  isValid: boolean
  errors: ValidationError[]
}
