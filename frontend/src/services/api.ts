import axios from 'axios'
import type { ScreenerRequest, ScreenerResponse } from '@/types/api'
import type { EnhancedScreenerRequest, EnhancedScreenerResponse } from '@/types/screener'

// Determine API URL based on where the frontend is accessed from
export const getApiUrl = () => {
  const hostname = window.location.hostname
  
  // If accessing from localhost, use localhost API
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000'
  }
  
  // If accessing from public IP, use the same IP for API with port 8000
  return `http://${hostname}:8000`
}

const API_BASE_URL = getApiUrl()

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add version query parameter to all requests to help with caching
api.interceptors.request.use((config) => {
  const version = new Date().getTime()
  if (config.params) {
    config.params._v = version
  } else {
    config.params = { _v: version }
  }
  return config
})

// Simple Screener API Interface
interface SimpleScreenerRequest {
  start_date: string
  end_date: string
  use_all_us_stocks?: boolean
  enable_db_prefiltering?: boolean
  filters: {
    price_range?: {
      min_price: number
      max_price: number
    }
    price_vs_ma?: {
      ma_period: 20 | 50 | 200
      condition: 'above' | 'below'
    }
    rsi?: {
      rsi_period: number
      condition: 'above' | 'below'
      threshold: number
    }
    gap?: {
      gap_threshold: number
      direction: 'up' | 'down' | 'both'
    }
    prev_day_dollar_volume?: {
      min_dollar_volume: number
    }
    relative_volume?: {
      recent_days: number
      lookback_days: number
      min_ratio: number
    }
  }
}

interface SimpleScreenerResponse {
  request: SimpleScreenerRequest
  execution_time_ms: number
  total_symbols_screened: number
  total_qualifying_stocks: number
  db_prefiltering_used: boolean
  symbols_filtered_by_db?: number
  results: Array<{
    symbol: string
    qualifying_dates: string[]
    total_days_analyzed: number
    qualifying_days_count: number
    qualifying_percentage: number
    metrics: {
      avg_open_price?: number
      ma_20_mean?: number
      ma_50_mean?: number
      ma_200_mean?: number
      rsi_mean?: number
      days_meeting_condition?: number
    }
  }>
}

export const stockScreenerApi = {
  screen: async (request: ScreenerRequest): Promise<ScreenerResponse> => {
    const response = await api.post<ScreenerResponse>('/api/v1/screen', request)
    return response.data
  },
  
  screenDatabase: async (request: ScreenerRequest): Promise<ScreenerResponse> => {
    const response = await api.post<ScreenerResponse>('/api/v1/screen/database', request)
    return response.data
  },
  
  screenEnhanced: async (request: EnhancedScreenerRequest): Promise<EnhancedScreenerResponse> => {
    // Transform the request to match the simple screener API format
    const simpleRequest: SimpleScreenerRequest = {
      start_date: request.start_date,
      end_date: request.end_date,
      use_all_us_stocks: request.use_all_us_stocks,
      enable_db_prefiltering: true,
      filters: {
        price_range: request.filters.simple_price_range && {
          min_price: request.filters.simple_price_range.min_price,
          max_price: request.filters.simple_price_range.max_price
        },
        price_vs_ma: request.filters.price_vs_ma && {
          ma_period: request.filters.price_vs_ma.period,
          condition: request.filters.price_vs_ma.condition
        },
        rsi: request.filters.rsi && {
          rsi_period: request.filters.rsi.period,
          condition: request.filters.rsi.condition,
          threshold: request.filters.rsi.threshold
        },
        gap: request.filters.gap && {
          gap_threshold: request.filters.gap.gap_threshold,
          direction: request.filters.gap.direction
        },
        prev_day_dollar_volume: request.filters.prev_day_dollar_volume && {
          min_dollar_volume: request.filters.prev_day_dollar_volume.min_dollar_volume
        },
        relative_volume: request.filters.relative_volume && {
          recent_days: request.filters.relative_volume.recent_days,
          lookback_days: request.filters.relative_volume.lookback_days,
          min_ratio: request.filters.relative_volume.min_ratio
        }
      }
    }
    
    const response = await api.post<SimpleScreenerResponse>('/api/v2/simple-screener/screen', simpleRequest)
    
    // Transform the response to match the expected format
    const enhancedResponse: EnhancedScreenerResponse = {
      request_date: new Date().toISOString(),
      total_symbols_screened: response.data.total_symbols_screened,
      total_qualifying_stocks: response.data.total_qualifying_stocks,
      execution_time_ms: response.data.execution_time_ms,
      results: response.data.results.map(result => ({
        symbol: result.symbol,
        qualifying_dates: result.qualifying_dates,
        metrics: {
          latest_price: result.metrics.avg_open_price,
          latest_volume: 0, // Not provided by simple screener
          simple_price_range: true, // Simplified
          price_vs_ma: result.metrics.ma_20_mean || result.metrics.ma_50_mean || result.metrics.ma_200_mean,
          rsi: result.metrics.rsi_mean
        }
      })),
      performance_metrics: {
        data_fetch_time_ms: 0,
        screening_time_ms: response.data.execution_time_ms,
        total_execution_time_ms: response.data.execution_time_ms,
        used_bulk_endpoint: false,
        symbols_fetched: response.data.total_symbols_screened,
        symbols_failed: 0
      }
    }
    
    return enhancedResponse
  },
  
  // Additional simple screener specific methods
  getFilterInfo: async () => {
    const response = await api.get('/api/v2/simple-screener/filters/info')
    return response.data
  },
  
  getExamples: async () => {
    const response = await api.get('/api/v2/simple-screener/examples')
    return response.data
  }
}
