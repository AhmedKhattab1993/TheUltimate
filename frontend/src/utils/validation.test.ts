import { describe, it, expect } from 'vitest'
import { validateFilters } from './validation'
import type { ScreenerState } from '@/contexts/ScreenerContext'

describe('validateFilters', () => {
  type FilterOverrides = Partial<ScreenerState['filters']>
  type StateOverrides = Partial<Omit<ScreenerState, 'filters'>> & { filters?: FilterOverrides }

  const createMockState = (overrides?: StateOverrides): ScreenerState => {
    const baseFilters: ScreenerState['filters'] = {
      simplePriceRange: {
        enabled: false,
        minPrice: '1.00',
        maxPrice: '100.00'
      },
      priceVsMA: {
        enabled: false,
        period: 50,
        condition: 'above'
      },
      rsi: {
        enabled: false,
        period: '14',
        threshold: '30',
        condition: 'below'
      },
      gap: {
        enabled: false,
        threshold: '2.0',
        direction: 'both'
      },
      prevDayDollarVolume: {
        enabled: false,
        minDollarVolume: '10000000'
      },
      relativeVolume: {
        enabled: false,
        recentDays: '2',
        lookbackDays: '20',
        minRatio: '1.5'
      }
    }

    const baseState: ScreenerState = {
      filters: baseFilters,
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
    }

    return {
      ...baseState,
      ...overrides,
      filters: {
        ...baseFilters,
        ...(overrides?.filters ?? {})
      }
    }
  }

  describe('Simple Price Range Validation', () => {
    it('should pass validation when price range is disabled', () => {
      const state = createMockState()
      const result = validateFilters(state)
      
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('should pass validation with valid price range', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: true,
            minPrice: '10.00',
            maxPrice: '50.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: false,
            period: '14',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('should fail validation with negative min price', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: true,
            minPrice: '-10',
            maxPrice: '50.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: false,
            period: '14',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual({
        field: 'simplePriceRange.minPrice',
        message: 'Minimum price must be a positive number'
      })
    })

    it('should fail validation with invalid min price format', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: true,
            minPrice: 'abc',
            maxPrice: '50.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: false,
            period: '14',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual({
        field: 'simplePriceRange.minPrice',
        message: 'Minimum price must be a positive number'
      })
    })

    it('should fail validation when min price >= max price', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: true,
            minPrice: '100.00',
            maxPrice: '50.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: false,
            period: '14',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual({
        field: 'simplePriceRange',
        message: 'Maximum price must be greater than minimum price'
      })
    })

    it('should handle multiple price range errors', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: true,
            minPrice: '-10',
            maxPrice: '-5'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: false,
            period: '14',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toHaveLength(2)
    })
  })

  describe('RSI Validation', () => {
    it('should pass validation when RSI is disabled', () => {
      const state = createMockState()
      const result = validateFilters(state)
      
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('should pass validation with valid RSI settings', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: false,
            minPrice: '1.00',
            maxPrice: '100.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: true,
            period: '14',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('should fail validation with RSI period < 2', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: false,
            minPrice: '1.00',
            maxPrice: '100.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: true,
            period: '1',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual({
        field: 'rsi.period',
        message: 'RSI period must be between 2 and 50'
      })
    })

    it('should fail validation with RSI period > 50', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: false,
            minPrice: '1.00',
            maxPrice: '100.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: true,
            period: '51',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual({
        field: 'rsi.period',
        message: 'RSI period must be between 2 and 50'
      })
    })

    it('should fail validation with invalid RSI threshold', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: false,
            minPrice: '1.00',
            maxPrice: '100.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: true,
            period: '14',
            threshold: '101',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual({
        field: 'rsi.threshold',
        message: 'RSI threshold must be between 0 and 100'
      })
    })

    it('should handle non-numeric RSI values', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: false,
            minPrice: '1.00',
            maxPrice: '100.00'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: true,
            period: 'abc',
            threshold: 'xyz',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toHaveLength(2)
    })
  })

  describe('Date Range Validation', () => {
    it('should pass validation with valid date range', () => {
      const state = createMockState({
        dateRange: {
          startDate: new Date('2024-01-01'),
          endDate: new Date('2024-01-31')
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('should pass validation with null dates', () => {
      const state = createMockState({
        dateRange: {
          startDate: null,
          endDate: null
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })

    it('should fail validation when end date is before start date', () => {
      const state = createMockState({
        dateRange: {
          startDate: new Date('2024-01-31'),
          endDate: new Date('2024-01-01')
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toContainEqual({
        field: 'dateRange',
        message: 'End date must be after start date'
      })
    })

    it('should pass validation when dates are equal', () => {
      const date = new Date('2024-01-15')
      const state = createMockState({
        dateRange: {
          startDate: date,
          endDate: date
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })
  })

  describe('Multiple Filter Validation', () => {
    it('should validate all enabled filters', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: true,
            minPrice: '100',
            maxPrice: '50'
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: true,
            period: '60',
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(false)
      expect(result.errors).toHaveLength(2)
      expect(result.errors.map(e => e.field)).toContain('simplePriceRange')
      expect(result.errors.map(e => e.field)).toContain('rsi.period')
    })

    it('should not validate disabled filters', () => {
      const state = createMockState({
        filters: {
          simplePriceRange: {
            enabled: false,
            minPrice: '100',
            maxPrice: '50' // Invalid but disabled
          },
          priceVsMA: {
            enabled: false,
            period: 50,
            condition: 'above'
          },
          rsi: {
            enabled: false,
            period: '60', // Invalid but disabled
            threshold: '30',
            condition: 'below'
          }
        }
      })
      
      const result = validateFilters(state)
      expect(result.isValid).toBe(true)
      expect(result.errors).toHaveLength(0)
    })
  })
})
