import { http, HttpResponse } from 'msw'

const API_BASE_URL = 'http://localhost:8000'

export const handlers = [
  // Simple screener endpoint
  http.post(`${API_BASE_URL}/api/v2/simple-screener/screen`, async ({ request }) => {
    const body = await request.json()
    
    // Mock successful response
    return HttpResponse.json({
      request: body,
      execution_time_ms: 150,
      total_symbols_screened: 100,
      total_qualifying_stocks: 5,
      db_prefiltering_used: true,
      symbols_filtered_by_db: 20,
      results: [
        {
          symbol: 'AAPL',
          qualifying_dates: ['2024-01-15', '2024-01-16', '2024-01-17'],
          total_days_analyzed: 20,
          qualifying_days_count: 3,
          qualifying_percentage: 15.0,
          metrics: {
            avg_open_price: 175.50,
            ma_50_mean: 172.30,
            rsi_mean: 45.2,
            days_meeting_condition: 3
          }
        },
        {
          symbol: 'MSFT',
          qualifying_dates: ['2024-01-15', '2024-01-18'],
          total_days_analyzed: 20,
          qualifying_days_count: 2,
          qualifying_percentage: 10.0,
          metrics: {
            avg_open_price: 380.25,
            ma_50_mean: 375.10,
            rsi_mean: 52.8,
            days_meeting_condition: 2
          }
        },
        {
          symbol: 'GOOGL',
          qualifying_dates: ['2024-01-16', '2024-01-17', '2024-01-18', '2024-01-19'],
          total_days_analyzed: 20,
          qualifying_days_count: 4,
          qualifying_percentage: 20.0,
          metrics: {
            avg_open_price: 142.75,
            ma_50_mean: 140.20,
            rsi_mean: 48.5,
            days_meeting_condition: 4
          }
        },
        {
          symbol: 'AMZN',
          qualifying_dates: ['2024-01-15'],
          total_days_analyzed: 20,
          qualifying_days_count: 1,
          qualifying_percentage: 5.0,
          metrics: {
            avg_open_price: 155.90,
            ma_50_mean: 152.40,
            rsi_mean: 55.1,
            days_meeting_condition: 1
          }
        },
        {
          symbol: 'TSLA',
          qualifying_dates: ['2024-01-17', '2024-01-18', '2024-01-19'],
          total_days_analyzed: 20,
          qualifying_days_count: 3,
          qualifying_percentage: 15.0,
          metrics: {
            avg_open_price: 195.60,
            ma_50_mean: 190.80,
            rsi_mean: 42.3,
            days_meeting_condition: 3
          }
        }
      ]
    })
  }),

  // Error response handler
  http.post(`${API_BASE_URL}/api/v2/simple-screener/screen`, async ({ request }) => {
    const body = await request.json()
    
    // Return error for specific test cases
    if (body.filters?.simple_price_range?.min_price === 999999) {
      return HttpResponse.json(
        {
          detail: 'Invalid price range: minimum price too high'
        },
        { status: 400 }
      )
    }
    
    // Return server error for specific test case
    if (body.use_all_us_stocks && body.start_date === 'ERROR') {
      return HttpResponse.json(
        {
          detail: 'Internal server error'
        },
        { status: 500 }
      )
    }
  }, { once: false }),

  // Filter info endpoint
  http.get(`${API_BASE_URL}/api/v2/simple-screener/filters/info`, () => {
    return HttpResponse.json({
      filters: {
        simple_price_range: {
          name: 'Simple Price Range',
          description: 'Filter stocks by price range',
          parameters: {
            min_price: { type: 'number', required: true, min: 0 },
            max_price: { type: 'number', required: true, min: 0 }
          }
        },
        price_vs_ma: {
          name: 'Price vs Moving Average',
          description: 'Filter stocks based on price relative to moving average',
          parameters: {
            period: { type: 'number', enum: [20, 50, 200] },
            condition: { type: 'string', enum: ['above', 'below'] }
          }
        },
        rsi: {
          name: 'RSI Filter',
          description: 'Filter stocks by RSI indicator',
          parameters: {
            period: { type: 'number', min: 2, max: 50 },
            threshold: { type: 'number', min: 0, max: 100 },
            condition: { type: 'string', enum: ['above', 'below'] }
          }
        }
      }
    })
  }),

  // Examples endpoint
  http.get(`${API_BASE_URL}/api/v2/simple-screener/examples`, () => {
    return HttpResponse.json({
      examples: [
        {
          name: 'Oversold Stocks',
          description: 'Find stocks with RSI below 30',
          request: {
            filters: {
              rsi: {
                rsi_period: 14,
                condition: 'below',
                threshold: 30
              }
            }
          }
        },
        {
          name: 'Value Stocks',
          description: 'Find stocks priced between $10-$50',
          request: {
            filters: {
              price_range: {
                min_price: 10,
                max_price: 50
              }
            }
          }
        }
      ]
    })
  })
]