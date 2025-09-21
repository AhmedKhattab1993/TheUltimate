import { useCallback } from 'react'
import { format } from 'date-fns'
import { useScreenerContext } from '@/contexts/ScreenerContext'
import type {
  EnhancedScreenerRequest,
  PriceVsMAFilterConfig,
  RSIFilterConfig,
  SimpleFilters,
} from '@/types/screener'
import { stockScreenerApi } from '@/services/api'
import { parseApiError } from '@/utils/error-handling'
import type { EnhancedScreenerResponse } from '@/types/screener'

interface OverrideFilters {
  ma?: PriceVsMAFilterConfig
  rsi?: RSIFilterConfig
}

const intersectResponses = (
  base: EnhancedScreenerResponse,
  next: EnhancedScreenerResponse,
): EnhancedScreenerResponse => {
  const nextBySymbol = new Map(next.results.map((row) => [row.symbol, row]))
  const filtered = base.results
    .filter((row) => nextBySymbol.has(row.symbol))
    .map((row) => {
      const counterpart = nextBySymbol.get(row.symbol)!
      const counterpartDates = new Set(counterpart.qualifying_dates)
      const qualifyingDates = row.qualifying_dates.filter((date) => counterpartDates.has(date))
      return {
        ...row,
        qualifying_dates: qualifyingDates,
        metrics: {
          ...row.metrics,
          ...counterpart.metrics,
        },
      }
    })

  return {
    ...base,
    execution_time_ms: base.execution_time_ms + next.execution_time_ms,
    total_symbols_screened: Math.min(base.total_symbols_screened, next.total_symbols_screened),
    total_qualifying_stocks: filtered.length,
    results: filtered,
  }
}

export function useScreener() {
  const { state, dispatch } = useScreenerContext()

  const buildRequestFromState = useCallback((currentState: typeof state, overrides?: OverrideFilters): EnhancedScreenerRequest => {
    const filters: SimpleFilters = {}

    const asNumber = (value: string) => {
      const parsed = parseFloat(value)
      return Number.isNaN(parsed) ? undefined : parsed
    }

    if (currentState.filters.simplePriceRange.enabled) {
      const minPrice = asNumber(currentState.filters.simplePriceRange.minPrice)
      const maxPrice = asNumber(currentState.filters.simplePriceRange.maxPrice)

      if (minPrice !== undefined || maxPrice !== undefined) {
        filters.simple_price_range = {
          min_price: minPrice,
          max_price: maxPrice,
        }
      }
    }

    const enabledMaSetups: PriceVsMAFilterConfig[] = Object.entries(currentState.filters.priceVsMA.setups)
      .filter(([, config]) => config.enabled)
      .map(([period, config]) => {
        const minRatio = asNumber(config.minRatio)
        const maxRatio = asNumber(config.maxRatio)
        return {
          ma_period: Number(period) as 20 | 50 | 200,
          min_ratio: minRatio,
          max_ratio: maxRatio,
        }
      })

    const selectedMa = overrides?.ma ?? enabledMaSetups[0]
    if (selectedMa) {
      filters.price_vs_ma = selectedMa
    }

    const enabledRsiSetups: RSIFilterConfig[] = Object.entries(currentState.filters.rsi.periods)
      .filter(([, config]) => config.enabled)
      .map(([period, config]) => {
        const minValue = asNumber(config.minValue)
        const maxValue = asNumber(config.maxValue)
        return {
          rsi_period: Number(period),
          min_value: minValue,
          max_value: maxValue,
        }
      })

    const selectedRsi = overrides?.rsi ?? enabledRsiSetups[0]
    if (selectedRsi) {
      filters.rsi = selectedRsi
    }

    if (currentState.filters.gap.enabled) {
      const minGap = asNumber(currentState.filters.gap.minGapPercent)
      const maxGap = asNumber(currentState.filters.gap.maxGapPercent)
      filters.gap = {
        min_gap_percent: minGap,
        max_gap_percent: maxGap,
        direction: currentState.filters.gap.direction,
      }
    }

    if (currentState.filters.prevDayDollarVolume.enabled) {
      const minVolume = asNumber(currentState.filters.prevDayDollarVolume.minDollarVolume)
      const maxVolume = asNumber(currentState.filters.prevDayDollarVolume.maxDollarVolume)
      if (minVolume !== undefined || maxVolume !== undefined) {
        filters.prev_day_dollar_volume = {
          min_dollar_volume: minVolume,
          max_dollar_volume: maxVolume,
        }
      }
    }

    if (currentState.filters.relativeVolume.enabled) {
      const recentDays = parseInt(currentState.filters.relativeVolume.recentDays)
      const lookbackDays = parseInt(currentState.filters.relativeVolume.lookbackDays)
      const minRatio = asNumber(currentState.filters.relativeVolume.minRatio)
      const maxRatio = asNumber(currentState.filters.relativeVolume.maxRatio)

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

    const enabledMaSetups: PriceVsMAFilterConfig[] = Object.entries(state.filters.priceVsMA.setups)
      .filter(([, config]) => config.enabled)
      .map(([period, config]) => {
        const minRatio = parseFloat(config.minRatio)
        const maxRatio = parseFloat(config.maxRatio)
        return {
          ma_period: Number(period) as 20 | 50 | 200,
          min_ratio: Number.isNaN(minRatio) ? undefined : minRatio,
          max_ratio: Number.isNaN(maxRatio) ? undefined : maxRatio,
        }
      })

    const enabledRsiSetups: RSIFilterConfig[] = Object.entries(state.filters.rsi.periods)
      .filter(([, config]) => config.enabled)
      .map(([period, config]) => {
        const minValue = parseFloat(config.minValue)
        const maxValue = parseFloat(config.maxValue)
        return {
          rsi_period: Number(period),
          min_value: Number.isNaN(minValue) ? undefined : minValue,
          max_value: Number.isNaN(maxValue) ? undefined : maxValue,
        }
      })

    const requestSpecs: OverrideFilters[] = []
    const primaryMa = enabledMaSetups[0]
    const primaryRsi = enabledRsiSetups[0]

    requestSpecs.push({ ma: primaryMa, rsi: primaryRsi })

    for (let i = 1; i < enabledMaSetups.length; i += 1) {
      requestSpecs.push({ ma: enabledMaSetups[i], rsi: primaryRsi })
    }

    for (let i = 1; i < enabledRsiSetups.length; i += 1) {
      requestSpecs.push({ ma: primaryMa, rsi: enabledRsiSetups[i] })
    }

    if (!primaryMa && !primaryRsi) {
      requestSpecs.splice(0, requestSpecs.length, {})
    }

    try {
      let aggregateResponse: EnhancedScreenerResponse | null = null

      for (const spec of requestSpecs) {
        const request = buildRequestFromState(state, spec)
        const response = await stockScreenerApi.screenEnhanced(request)

        aggregateResponse = aggregateResponse
          ? intersectResponses(aggregateResponse, response)
          : response

        if (aggregateResponse.results.length === 0) {
          break
        }
      }

      dispatch({ type: 'SET_RESULTS', data: aggregateResponse })
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
