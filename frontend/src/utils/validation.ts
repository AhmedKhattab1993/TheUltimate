import type { ScreenerState } from '@/contexts/ScreenerContext'
import type { ValidationResult, ValidationError } from '@/types/screener'

export function validateFilters(state: ScreenerState): ValidationResult {
  const errors: ValidationError[] = []

  // Validate Simple Price Range
  if (state.filters.simplePriceRange.enabled) {
    const minPrice = parseFloat(state.filters.simplePriceRange.minPrice)
    const maxPrice = parseFloat(state.filters.simplePriceRange.maxPrice)

    if (!Number.isNaN(minPrice) && minPrice < 0) {
      errors.push({
        field: 'simplePriceRange.minPrice',
        message: 'Minimum price must be a positive number'
      })
    }

    if (!Number.isNaN(maxPrice) && maxPrice < 0) {
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
    const minValue = parseFloat(state.filters.rsi.minValue)
    const maxValue = parseFloat(state.filters.rsi.maxValue)

    if (isNaN(period) || period < 2 || period > 50) {
      errors.push({
        field: 'rsi.period',
        message: 'RSI period must be between 2 and 50'
      })
    }

    if (!isNaN(minValue) && (minValue < 0 || minValue > 100)) {
      errors.push({
        field: 'rsi.minValue',
        message: 'Minimum RSI must be between 0 and 100'
      })
    }

    if (!isNaN(maxValue) && (maxValue < 0 || maxValue > 100)) {
      errors.push({
        field: 'rsi.maxValue',
        message: 'Maximum RSI must be between 0 and 100'
      })
    }

    if (!isNaN(minValue) && !isNaN(maxValue) && minValue > maxValue) {
      errors.push({
        field: 'rsi',
        message: 'Minimum RSI must be less than or equal to maximum RSI'
      })
    }
  }

  // Validate Gap Filter
  if (state.filters.gap.enabled) {
    const minGap = parseFloat(state.filters.gap.minGapPercent)
    const maxGap = parseFloat(state.filters.gap.maxGapPercent)

    if (!isNaN(minGap) && minGap < 0) {
      errors.push({
        field: 'gap.minGapPercent',
        message: 'Minimum gap must be zero or greater'
      })
    }

    if (!isNaN(maxGap) && maxGap < 0) {
      errors.push({
        field: 'gap.maxGapPercent',
        message: 'Maximum gap must be zero or greater'
      })
    }

    if (!isNaN(minGap) && !isNaN(maxGap) && minGap > maxGap) {
      errors.push({
        field: 'gap',
        message: 'Minimum gap must be less than or equal to maximum gap'
      })
    }
  }

  // Validate Previous Day Dollar Volume
  if (state.filters.prevDayDollarVolume.enabled) {
    const minVolume = parseFloat(state.filters.prevDayDollarVolume.minDollarVolume)
    const maxVolume = parseFloat(state.filters.prevDayDollarVolume.maxDollarVolume)

    if (!isNaN(minVolume) && minVolume < 0) {
      errors.push({
        field: 'prevDayDollarVolume.minDollarVolume',
        message: 'Minimum dollar volume must be zero or greater'
      })
    }

    if (!isNaN(maxVolume) && maxVolume < 0) {
      errors.push({
        field: 'prevDayDollarVolume.maxDollarVolume',
        message: 'Maximum dollar volume must be zero or greater'
      })
    }

    if (!isNaN(minVolume) && !isNaN(maxVolume) && minVolume > maxVolume) {
      errors.push({
        field: 'prevDayDollarVolume',
        message: 'Minimum dollar volume must be less than or equal to maximum dollar volume'
      })
    }
  }

  // Validate Relative Volume
  if (state.filters.relativeVolume.enabled) {
    const recentDays = parseInt(state.filters.relativeVolume.recentDays)
    const lookbackDays = parseInt(state.filters.relativeVolume.lookbackDays)
    const minRatio = parseFloat(state.filters.relativeVolume.minRatio)
    const maxRatio = parseFloat(state.filters.relativeVolume.maxRatio)

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

    if (!isNaN(maxRatio) && (maxRatio <= 0 || maxRatio > 10)) {
      errors.push({
        field: 'relativeVolume.maxRatio',
        message: 'Maximum ratio must be between 0.1 and 10'
      })
    }

    if (!isNaN(minRatio) && !isNaN(maxRatio) && minRatio > maxRatio) {
      errors.push({
        field: 'relativeVolume',
        message: 'Minimum ratio must be less than or equal to maximum ratio'
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
