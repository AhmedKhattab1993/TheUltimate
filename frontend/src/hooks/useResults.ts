import { useCallback } from 'react'
import { format } from 'date-fns'
import { useResultsContext } from '@/contexts/ResultsContext'
import { getApiUrl } from '@/services/api'

const API_BASE_URL = getApiUrl()

export function useResults() {
  const { state, dispatch } = useResultsContext()

  // Fetch screener results
  const fetchScreenerResults = useCallback(async () => {
    dispatch({ type: 'SET_SCREENER_LOADING', loading: true })

    try {
      const params = new URLSearchParams({
        page: state.screenerResults.page.toString(),
        page_size: state.screenerResults.pageSize.toString()
      })

      // Add date filters if set
      if (state.dateFilter.startDate) {
        params.append('start_date', format(state.dateFilter.startDate, 'yyyy-MM-dd'))
      }
      if (state.dateFilter.endDate) {
        params.append('end_date', format(state.dateFilter.endDate, 'yyyy-MM-dd'))
      }

      const response = await fetch(
        `${API_BASE_URL}/api/v2/screener/results?${params.toString()}`
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch screener results: ${response.statusText}`)
      }

      const data = await response.json()
      dispatch({
        type: 'SET_SCREENER_RESULTS',
        data: data.results,
        totalCount: data.total_count
      })
    } catch (error) {
      dispatch({
        type: 'SET_SCREENER_ERROR',
        error: error instanceof Error ? error.message : 'Failed to fetch screener results'
      })
    }
  }, [state.screenerResults.page, state.screenerResults.pageSize, state.dateFilter, dispatch])

  // Fetch backtest results
  const fetchBacktestResults = useCallback(async () => {
    dispatch({ type: 'SET_BACKTEST_LOADING', loading: true })

    try {
      const params = new URLSearchParams({
        page: state.backtestResults.page.toString(),
        page_size: state.backtestResults.pageSize.toString()
      })

      // Add date filters if set
      if (state.dateFilter.startDate) {
        params.append('start_date', format(state.dateFilter.startDate, 'yyyy-MM-dd'))
      }
      if (state.dateFilter.endDate) {
        params.append('end_date', format(state.dateFilter.endDate, 'yyyy-MM-dd'))
      }

      const response = await fetch(
        `${API_BASE_URL}/api/v2/backtest/db/results?${params.toString()}`
      )

      if (!response.ok) {
        throw new Error(`Failed to fetch backtest results: ${response.statusText}`)
      }

      const data = await response.json()
      
      // The API already returns camelCase, no transformation needed
      const transformedResults = data.results.map((result: any) => ({
        backtestId: result.backtestId,
        symbol: result.symbol,
        strategyName: result.strategyName,
        startDate: result.startDate,
        endDate: result.endDate,
        initialCash: result.initialCash,
        finalValue: result.finalValue,
        // Include pivotBars and lowerTimeframe
        pivotBars: result.pivotBars,
        lowerTimeframe: result.lowerTimeframe,
        // Include other useful fields for completeness
        resolution: result.resolution,
        status: result.status,
        executionTimeMs: result.executionTimeMs,
        cacheHit: result.cacheHit,
        statistics: {
          totalReturn: result.statistics?.totalReturn || 0,
          sharpeRatio: result.statistics?.sharpeRatio || 0,
          maxDrawdown: result.statistics?.maxDrawdown || 0,
          winRate: result.statistics?.winRate || 0,
          totalTrades: result.statistics?.totalTrades || 0,
          endEquity: result.statistics?.endEquity
        },
        createdAt: result.createdAt
      }))

      dispatch({
        type: 'SET_BACKTEST_RESULTS',
        data: transformedResults,
        totalCount: data.total_count
      })
    } catch (error) {
      dispatch({
        type: 'SET_BACKTEST_ERROR',
        error: error instanceof Error ? error.message : 'Failed to fetch backtest results'
      })
    }
  }, [state.backtestResults.page, state.backtestResults.pageSize, state.dateFilter, dispatch])

  // Get screener result details
  const getScreenerResultDetails = useCallback(async (resultId: string) => {
    const response = await fetch(`${API_BASE_URL}/api/v2/screener/results/${resultId}`)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch screener result details: ${response.statusText}`)
    }

    return response.json()
  }, [])

  // Get backtest result details
  const getBacktestResultDetails = useCallback(async (backtestId: string) => {
    const response = await fetch(`${API_BASE_URL}/api/v2/backtest/db/results/${backtestId}`)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch backtest result details: ${response.statusText}`)
    }

    return response.json()
  }, [])

  // Delete screener result
  const deleteScreenerResult = useCallback(async (resultId: string) => {
    const response = await fetch(`${API_BASE_URL}/api/v2/screener/results/${resultId}`, {
      method: 'DELETE'
    })
    
    if (!response.ok) {
      throw new Error(`Failed to delete screener result: ${response.statusText}`)
    }

    // Refresh the list
    await fetchScreenerResults()
  }, [fetchScreenerResults])

  // Delete backtest result
  const deleteBacktestResult = useCallback(async (backtestId: string) => {
    const response = await fetch(`${API_BASE_URL}/api/v2/backtest/db/results/${backtestId}`, {
      method: 'DELETE'
    })
    
    if (!response.ok) {
      throw new Error(`Failed to delete backtest result: ${response.statusText}`)
    }

    // Refresh the list
    await fetchBacktestResults()
  }, [fetchBacktestResults])

  return {
    fetchScreenerResults,
    fetchBacktestResults,
    getScreenerResultDetails,
    getBacktestResultDetails,
    deleteScreenerResult,
    deleteBacktestResult
  }
}