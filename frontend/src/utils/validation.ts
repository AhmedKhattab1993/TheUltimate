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

  // Validate Gap Filter
  if (state.filters.gap.enabled) {
    const threshold = parseFloat(state.filters.gap.threshold)

    if (isNaN(threshold) || threshold < 0) {
      errors.push({
        field: 'gap.threshold',
        message: 'Gap threshold must be a positive number'
      })
    }
  }

  // Validate Previous Day Dollar Volume
  if (state.filters.prevDayDollarVolume.enabled) {
    const minVolume = parseFloat(state.filters.prevDayDollarVolume.minDollarVolume)

    if (isNaN(minVolume) || minVolume < 0) {
      errors.push({
        field: 'prevDayDollarVolume.minDollarVolume',
        message: 'Minimum dollar volume must be a positive number'
      })
    }
  }

  // Validate Relative Volume
  if (state.filters.relativeVolume.enabled) {
    const recentDays = parseInt(state.filters.relativeVolume.recentDays)
    const lookbackDays = parseInt(state.filters.relativeVolume.lookbackDays)
    const minRatio = parseFloat(state.filters.relativeVolume.minRatio)

    if (isNaN(recentDays) || recentDays < 1 || recentDays > 10) {
      errors.push({
        field: 'relativeVolume.recentDays',
        message: 'Recent days must be between 1 and 10'
      })
    }

    if (isNaN(lookbackDays) || lookbackDays < 5 || lookbackDays > 200) {
      errors.push({
        field: 'relativeVolume.lookbackDays',
        message: 'Lookback days must be between 5 and 200'
      })
    }

    if (!isNaN(recentDays) && !isNaN(lookbackDays) && recentDays >= lookbackDays) {
      errors.push({
        field: 'relativeVolume',
        message: 'Lookback days must be greater than recent days'
      })
    }

    if (isNaN(minRatio) || minRatio <= 0 || minRatio > 10) {
      errors.push({
        field: 'relativeVolume.minRatio',
        message: 'Minimum ratio must be between 0.1 and 10'
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