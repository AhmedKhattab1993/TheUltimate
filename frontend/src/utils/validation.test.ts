import { describe, expect, it } from 'vitest'
import { validateFilters } from './validation'
import type { ScreenerState } from '@/contexts/ScreenerContext'

const makeBaseState = (): ScreenerState => ({
  filters: {
    simplePriceRange: {
      enabled: false,
      minPrice: '1.00',
      maxPrice: '100.00'
    },
    priceVsMA: {
      enabled: false,
      setups: {
        20: { enabled: false, minRatio: '1.00', maxRatio: '' },
        50: { enabled: false, minRatio: '1.00', maxRatio: '' },
        200: { enabled: false, minRatio: '1.00', maxRatio: '' }
      }
    },
    rsi: {
      enabled: false,
      periods: {
        3: { enabled: false, minValue: '', maxValue: '30' },
        14: { enabled: false, minValue: '', maxValue: '30' },
        21: { enabled: false, minValue: '', maxValue: '30' }
      }
    },
    gap: {
      enabled: false,
      minGapPercent: '2.0',
      maxGapPercent: '',
      direction: 'both'
    },
    prevDayDollarVolume: {
      enabled: false,
      minDollarVolume: '10000000',
      maxDollarVolume: ''
    },
    relativeVolume: {
      enabled: false,
      recentDays: '2',
      lookbackDays: '20',
      minRatio: '1.5',
      maxRatio: ''
    }
  },
  dateRange: {
    startDate: new Date('2024-01-01'),
    endDate: new Date('2024-01-31')
  },
  stockSelection: {
    useAllStocks: true
  },
  results: {
    data: null,
    loading: false,
    error: null
  },
  ui: {
    sortColumn: 'symbol',
    sortDirection: 'asc',
    resultsView: 'table'
  }
})

describe('validateFilters', () => {
  it('returns valid result when no filters are enabled', () => {
    const result = validateFilters(makeBaseState())
    expect(result.isValid).toBe(true)
    expect(result.errors).toHaveLength(0)
  })

  it('validates simple price range bounds', () => {
    const state = makeBaseState()
    state.filters.simplePriceRange.enabled = true
    state.filters.simplePriceRange.minPrice = '-1'

    const result = validateFilters(state)

    expect(result.isValid).toBe(false)
    expect(result.errors).toContainEqual({
      field: 'simplePriceRange.minPrice',
      message: 'Minimum price must be a positive number'
    })
  })

  it('validates price vs MA presets individually', () => {
    const state = makeBaseState()
    state.filters.priceVsMA.setups[20] = {
      enabled: true,
      minRatio: '1.5',
      maxRatio: '1.0'
    }
    state.filters.priceVsMA.enabled = true

    const result = validateFilters(state)

    expect(result.isValid).toBe(false)
    expect(result.errors).toContainEqual({
      field: 'priceVsMA.20',
      message: 'Minimum ratio must be less than or equal to maximum ratio'
    })
  })

  it('validates RSI presets individually', () => {
    const state = makeBaseState()
    state.filters.rsi.periods[14] = {
      enabled: true,
      minValue: '80',
      maxValue: '60'
    }
    state.filters.rsi.enabled = true

    const result = validateFilters(state)

    expect(result.isValid).toBe(false)
    expect(result.errors).toContainEqual({
      field: 'rsi.14',
      message: 'Minimum RSI must be less than or equal to maximum RSI'
    })
  })

  it('validates gap bounds', () => {
    const state = makeBaseState()
    state.filters.gap.enabled = true
    state.filters.gap.minGapPercent = '-1'

    const result = validateFilters(state)

    expect(result.isValid).toBe(false)
    expect(result.errors).toContainEqual({
      field: 'gap.minGapPercent',
      message: 'Minimum gap must be zero or greater'
    })
  })

  it('validates previous day dollar volume', () => {
    const state = makeBaseState()
    state.filters.prevDayDollarVolume.enabled = true
    state.filters.prevDayDollarVolume.minDollarVolume = '-1'

    const result = validateFilters(state)

    expect(result.isValid).toBe(false)
    expect(result.errors).toContainEqual({
      field: 'prevDayDollarVolume.minDollarVolume',
      message: 'Minimum dollar volume must be zero or greater'
    })
  })

  it('validates relative volume ratios', () => {
    const state = makeBaseState()
    state.filters.relativeVolume.enabled = true
    state.filters.relativeVolume.minRatio = '-1'

    const result = validateFilters(state)

    expect(result.isValid).toBe(false)
    expect(result.errors).toContainEqual({
      field: 'relativeVolume.minRatio',
      message: 'Minimum ratio must be between 0.1 and 10'
    })
  })

  it('validates date range ordering', () => {
    const state = makeBaseState()
    state.dateRange.startDate = new Date('2024-02-01')
    state.dateRange.endDate = new Date('2024-01-01')

    const result = validateFilters(state)

    expect(result.isValid).toBe(false)
    expect(result.errors).toContainEqual({
      field: 'dateRange',
      message: 'End date must be after start date'
    })
  })
})
