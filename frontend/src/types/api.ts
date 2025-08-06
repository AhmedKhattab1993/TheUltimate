export interface ScreenerRequest {
  start_date: string
  end_date: string
  symbols?: string[]
  use_all_us_stocks?: boolean
  filters: Filters
}

export interface Filters {
  volume?: VolumeFilter
  price_change?: PriceChangeFilter
  moving_average?: MovingAverageFilter
  gap?: GapFilter
  price_range?: PriceRangeFilter
  float?: FloatFilter
  relative_volume?: RelativeVolumeFilter
  market_cap?: MarketCapFilter
}

export interface VolumeFilter {
  min_average?: number
  max_average?: number
  lookback_days?: number
}

export interface PriceChangeFilter {
  min_change?: number
  max_change?: number
  period_days?: number
}

export interface MovingAverageFilter {
  period: number
  condition: "above" | "below" | "crosses_above" | "crosses_below"
}

export interface GapFilter {
  min_gap_percent?: number
  max_gap_percent?: number
}

export interface PriceRangeFilter {
  min_price?: number
  max_price?: number
}

export interface FloatFilter {
  max_float?: number
}

export interface RelativeVolumeFilter {
  min_relative_volume?: number
  lookback_days?: number
}

export interface MarketCapFilter {
  max_market_cap?: number
  min_market_cap?: number
}

export interface ScreenResult {
  symbol: string
  qualifying_dates: string[]
  metrics: {
    avg_volume?: number
    avg_price_change?: number
    [key: string]: any
  }
}

export interface ScreenerResponse {
  request_date: string
  total_symbols_screened: number
  total_qualifying_stocks: number
  results: ScreenResult[]
  execution_time_ms: number
}