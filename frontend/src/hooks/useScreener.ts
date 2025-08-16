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

    // Add enabled filters
    if (state.filters.simplePriceRange.enabled) {
      const minPrice = parseFloat(state.filters.simplePriceRange.minPrice)
      const maxPrice = parseFloat(state.filters.simplePriceRange.maxPrice)
      
      if (!isNaN(minPrice) && !isNaN(maxPrice)) {
        filters.simple_price_range = {
          min_price: minPrice,
          max_price: maxPrice
        }
      }
    }

    if (state.filters.priceVsMA.enabled) {
      filters.price_vs_ma = {
        period: state.filters.priceVsMA.period,
        condition: state.filters.priceVsMA.condition
      }
    }

    if (state.filters.rsi.enabled) {
      const period = parseInt(state.filters.rsi.period)
      const threshold = parseFloat(state.filters.rsi.threshold)
      
      if (!isNaN(period) && !isNaN(threshold)) {
        filters.rsi = {
          period,
          threshold,
          condition: state.filters.rsi.condition
        }
      }
    }

    if (state.filters.gap.enabled) {
      const threshold = parseFloat(state.filters.gap.threshold)
      
      if (!isNaN(threshold)) {
        filters.gap = {
          gap_threshold: threshold,
          direction: state.filters.gap.direction
        }
      }
    }

    if (state.filters.prevDayDollarVolume.enabled) {
      const minVolume = parseFloat(state.filters.prevDayDollarVolume.minDollarVolume)
      
      if (!isNaN(minVolume)) {
        filters.prev_day_dollar_volume = {
          min_dollar_volume: minVolume
        }
      }
    }

    if (state.filters.relativeVolume.enabled) {
      const recentDays = parseInt(state.filters.relativeVolume.recentDays)
      const lookbackDays = parseInt(state.filters.relativeVolume.lookbackDays)
      const minRatio = parseFloat(state.filters.relativeVolume.minRatio)
      
      if (!isNaN(recentDays) && !isNaN(lookbackDays) && !isNaN(minRatio)) {
        filters.relative_volume = {
          recent_days: recentDays,
          lookback_days: lookbackDays,
          min_ratio: minRatio
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