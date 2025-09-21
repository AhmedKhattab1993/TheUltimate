import { useCallback } from 'react'
import { format } from 'date-fns'
import { useScreenerContext } from '@/contexts/ScreenerContext'
import type { EnhancedScreenerRequest, SimpleFilters } from '@/types/screener'
import { stockScreenerApi } from '@/services/api'
import { parseApiError } from '@/utils/error-handling'

export function useScreener() {
  const { state, dispatch } = useScreenerContext()

  const buildRequestFromState = useCallback((state: any): EnhancedScreenerRequest => {
    const filters: SimpleFilters = {}

    const asNumber = (value: string) => {
      const parsed = parseFloat(value)
      return Number.isNaN(parsed) ? undefined : parsed
    }

    // Add enabled filters
    if (state.filters.simplePriceRange.enabled) {
      const minPrice = asNumber(state.filters.simplePriceRange.minPrice)
      const maxPrice = asNumber(state.filters.simplePriceRange.maxPrice)

      if (minPrice !== undefined || maxPrice !== undefined) {
        filters.simple_price_range = {
          min_price: minPrice,
          max_price: maxPrice,
        }
      }
    }

    if (state.filters.priceVsMA.enabled) {
      const minRatio = asNumber(state.filters.priceVsMA.minRatio)
      const maxRatio = asNumber(state.filters.priceVsMA.maxRatio)
      filters.price_vs_ma = {
        ma_period: state.filters.priceVsMA.period,
        min_ratio: minRatio,
        max_ratio: maxRatio,
      }
    }

    if (state.filters.rsi.enabled) {
      const period = parseInt(state.filters.rsi.period)
      const minValue = asNumber(state.filters.rsi.minValue)
      const maxValue = asNumber(state.filters.rsi.maxValue)

      if (!Number.isNaN(period)) {
        filters.rsi = {
          rsi_period: period,
          min_value: minValue,
          max_value: maxValue,
        }
      }
    }

    if (state.filters.gap.enabled) {
      const minGap = asNumber(state.filters.gap.minGapPercent)
      const maxGap = asNumber(state.filters.gap.maxGapPercent)
      filters.gap = {
        min_gap_percent: minGap,
        max_gap_percent: maxGap,
        direction: state.filters.gap.direction,
      }
    }

    if (state.filters.prevDayDollarVolume.enabled) {
      const minVolume = asNumber(state.filters.prevDayDollarVolume.minDollarVolume)
      const maxVolume = asNumber(state.filters.prevDayDollarVolume.maxDollarVolume)
      if (minVolume !== undefined || maxVolume !== undefined) {
        filters.prev_day_dollar_volume = {
          min_dollar_volume: minVolume,
          max_dollar_volume: maxVolume,
        }
      }
    }

    if (state.filters.relativeVolume.enabled) {
      const recentDays = parseInt(state.filters.relativeVolume.recentDays)
      const lookbackDays = parseInt(state.filters.relativeVolume.lookbackDays)
      const minRatio = asNumber(state.filters.relativeVolume.minRatio)
      const maxRatio = asNumber(state.filters.relativeVolume.maxRatio)

      if (!Number.isNaN(recentDays) && !Number.isNaN(lookbackDays)) {
        filters.relative_volume = {
          recent_days: recentDays,
          lookback_days: lookbackDays,
          min_ratio: minRatio,
          max_ratio: maxRatio,
        }
      }
    }

    return {
      start_date: format(state.dateRange.startDate!, 'yyyy-MM-dd'),
      end_date: format(state.dateRange.endDate!, 'yyyy-MM-dd'),
      filters,
      use_all_us_stocks: true
    }
  }, [])

  const runScreener = useCallback(async () => {
    if (!state.dateRange.startDate || !state.dateRange.endDate) {
      dispatch({ type: 'SET_ERROR', error: 'Please select both start and end dates' })
      dispatch({ type: 'SET_LOADING', loading: false })
      return
    }

    console.log('Setting loading to true')
    dispatch({ type: 'SET_LOADING', loading: true })
    dispatch({ type: 'SET_ERROR', error: null })

    // Force a small delay to ensure loading state is visible
    await new Promise(resolve => setTimeout(resolve, 100))

    try {
      const request = buildRequestFromState(state)
      console.log('Sending screening request:', request)
      const response = await stockScreenerApi.screenEnhanced(request)
      
      dispatch({ type: 'SET_RESULTS', data: response })
    } catch (error) {
      const errorMessage = parseApiError(error)
      dispatch({ type: 'SET_ERROR', error: errorMessage })
    } finally {
      console.log('Setting loading to false')
      dispatch({ type: 'SET_LOADING', loading: false })
    }
  }, [state, dispatch, buildRequestFromState])

  return {
    runScreener,
    isLoading: state.results.loading,
    error: state.results.error,
    data: state.results.data
  }
}
