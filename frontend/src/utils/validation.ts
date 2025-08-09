import type { ScreenerState } from '@/contexts/ScreenerContext'
import type { ValidationResult, ValidationError } from '@/types/screener'

export function validateFilters(state: ScreenerState): ValidationResult {
  const errors: ValidationError[] = []

  // Validate Simple Price Range
  if (state.filters.simplePriceRange.enabled) {
    const minPrice = parseFloat(state.filters.simplePriceRange.minPrice)
    const maxPrice = parseFloat(state.filters.simplePriceRange.maxPrice)

    if (isNaN(minPrice) || minPrice < 0) {
      errors.push({
        field: 'simplePriceRange.minPrice',
        message: 'Minimum price must be a positive number'
      })
    }

    if (isNaN(maxPrice) || maxPrice < 0) {
      errors.push({
        field: 'simplePriceRange.maxPrice',
        message: 'Maximum price must be a positive number'
      })
    }

    if (!isNaN(minPrice) && !isNaN(maxPrice) && minPrice >= maxPrice) {
      errors.push({
        field: 'simplePriceRange',
        message: 'Maximum price must be greater than minimum price'
      })
    }
  }

  // Validate RSI
  if (state.filters.rsi.enabled) {
    const period = parseInt(state.filters.rsi.period)
    const threshold = parseFloat(state.filters.rsi.threshold)

    if (isNaN(period) || period < 2 || period > 50) {
      errors.push({
        field: 'rsi.period',
        message: 'RSI period must be between 2 and 50'
      })
    }

    if (isNaN(threshold) || threshold < 0 || threshold > 100) {
      errors.push({
        field: 'rsi.threshold',
        message: 'RSI threshold must be between 0 and 100'
      })
    }
  }

  // Date validation
  if (state.dateRange.startDate && state.dateRange.endDate) {
    if (state.dateRange.startDate > state.dateRange.endDate) {
      errors.push({
        field: 'dateRange',
        message: 'End date must be after start date'
      })
    }
  }

  return {
    isValid: errors.length === 0,
    errors
  }
}