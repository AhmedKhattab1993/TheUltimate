import { useCallback } from 'react'
import { format } from 'date-fns'
import { useScreenerContext } from '@/contexts/ScreenerContext'
import type { EnhancedScreenerRequest, PriceVsMAFilterConfig, RSIFilterConfig, SimpleFilters } from '@/types/screener'
import { stockScreenerApi } from '@/services/api'
import { parseApiError } from '@/utils/error-handling'

const toNumber = (value: string) => {
  const parsed = parseFloat(value)
  return Number.isNaN(parsed) ? undefined : parsed
}

export function useScreener() {
  const { state, dispatch } = useScreenerContext()

  const buildRequestFromState = useCallback((currentState: typeof state): EnhancedScreenerRequest => {
    const filters: SimpleFilters = {}

    if (currentState.filters.simplePriceRange.enabled) {
      const minPrice = toNumber(currentState.filters.simplePriceRange.minPrice)
      const maxPrice = toNumber(currentState.filters.simplePriceRange.maxPrice)

      if (minPrice !== undefined || maxPrice !== undefined) {
        filters.simple_price_range = {
          min_price: minPrice,
          max_price: maxPrice,
        }
      }
    }

    const enabledMaSetups: PriceVsMAFilterConfig[] = Object.entries(currentState.filters.priceVsMA.setups)
      .filter(([, config]) => config.enabled)
      .map(([period, config]) => ({
        ma_period: Number(period) as 20 | 50 | 200,
        min_ratio: toNumber(config.minRatio),
        max_ratio: toNumber(config.maxRatio),
      }))

    if (enabledMaSetups.length > 0) {
      filters.price_vs_ma = enabledMaSetups
    }

    const enabledRsiSetups: RSIFilterConfig[] = Object.entries(currentState.filters.rsi.periods)
      .filter(([, config]) => config.enabled)
      .map(([period, config]) => ({
        rsi_period: Number(period),
        min_value: toNumber(config.minValue),
        max_value: toNumber(config.maxValue),
      }))

    if (enabledRsiSetups.length > 0) {
      filters.rsi = enabledRsiSetups
    }

    if (currentState.filters.gap.enabled) {
      const minGap = toNumber(currentState.filters.gap.minGapPercent)
      const maxGap = toNumber(currentState.filters.gap.maxGapPercent)

      filters.gap = {
        min_gap_percent: minGap,
        max_gap_percent: maxGap,
        direction: currentState.filters.gap.direction,
      }
    }

    if (currentState.filters.prevDayDollarVolume.enabled) {
      const minVolume = toNumber(currentState.filters.prevDayDollarVolume.minDollarVolume)
      const maxVolume = toNumber(currentState.filters.prevDayDollarVolume.maxDollarVolume)

      if (minVolume !== undefined || maxVolume !== undefined) {
        filters.prev_day_dollar_volume = {
          min_dollar_volume: minVolume,
          max_dollar_volume: maxVolume,
        }
      }
    }

    if (currentState.filters.relativeVolume.enabled) {
      const recentDays = parseInt(currentState.filters.relativeVolume.recentDays, 10)
      const lookbackDays = parseInt(currentState.filters.relativeVolume.lookbackDays, 10)
      const minRatio = toNumber(currentState.filters.relativeVolume.minRatio)
      const maxRatio = toNumber(currentState.filters.relativeVolume.maxRatio)

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
      start_date: format(currentState.dateRange.startDate!, 'yyyy-MM-dd'),
      end_date: format(currentState.dateRange.endDate!, 'yyyy-MM-dd'),
      filters,
      use_all_us_stocks: true,
    }
  }, [])

  const runScreener = useCallback(async () => {
    if (!state.dateRange.startDate || !state.dateRange.endDate) {
      dispatch({ type: 'SET_ERROR', error: 'Please select both start and end dates' })
      dispatch({ type: 'SET_LOADING', loading: false })
      return
    }

    dispatch({ type: 'SET_LOADING', loading: true })
    dispatch({ type: 'SET_ERROR', error: null })

    await new Promise((resolve) => setTimeout(resolve, 100))

    try {
      const request = buildRequestFromState(state)
      const response = await stockScreenerApi.screenEnhanced(request)
      dispatch({ type: 'SET_RESULTS', data: response })
    } catch (error) {
      const errorMessage = parseApiError(error)
      dispatch({ type: 'SET_ERROR', error: errorMessage })
    } finally {
      dispatch({ type: 'SET_LOADING', loading: false })
    }
  }, [state, dispatch, buildRequestFromState])

  return {
    runScreener,
    isLoading: state.results.loading,
    error: state.results.error,
    data: state.results.data,
  }
}
