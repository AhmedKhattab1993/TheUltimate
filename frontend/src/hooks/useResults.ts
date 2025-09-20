import { useCallback } from 'react'
import { format } from 'date-fns'
import { useResultsContext } from '@/contexts/ResultsContext'
import { backtestApi, screenerResultsApi } from '@/services/api'
import type { BacktestRunInfo } from '@/types/api'

const toIsoDate = (date: Date | null): string | undefined => {
  return date ? format(date, 'yyyy-MM-dd') : undefined
}

export function useResults() {
  const { state, dispatch } = useResultsContext()

  const buildDateParams = () => ({
    startDate: toIsoDate(state.dateFilter.startDate),
    endDate: toIsoDate(state.dateFilter.endDate),
  })

  const fetchScreenerResults = useCallback(async () => {
    dispatch({ type: 'SET_SCREENER_LOADING', loading: true })
    try {
      const { startDate, endDate } = buildDateParams()
      const response = await screenerResultsApi.list({
        page: state.screenerResults.page,
        pageSize: state.screenerResults.pageSize,
        startDate,
        endDate,
      })

      const mapped = response.results.map((summary) => ({
        id: summary.id,
        timestamp: summary.timestamp,
        symbol_count: summary.symbolCount,
        filters: summary.filters,
        execution_time_ms: summary.executionTimeMs ?? 0,
        total_symbols_screened: summary.totalSymbolsScreened ?? 0,
      }))

      dispatch({ type: 'SET_SCREENER_RESULTS', data: mapped, totalCount: response.totalCount })
    } catch (error) {
      dispatch({
        type: 'SET_SCREENER_ERROR',
        error: error instanceof Error ? error.message : 'Failed to fetch screener results',
      })
    }
  }, [state.screenerResults.page, state.screenerResults.pageSize, state.dateFilter, dispatch])

  const toSummary = (run: BacktestRunInfo) => ({
    backtestId: run.backtestId,
    strategyName: run.request.strategyName,
    startDate: run.request.startDate,
    endDate: run.request.endDate,
    initialCash: run.request.initialCash,
    finalValue: undefined,
    statistics: {
      totalReturn: run.metrics?.total_return ?? 0,
      sharpeRatio: run.metrics?.sharpe_ratio ?? 0,
      sortinoRatio: run.metrics?.sortino_ratio ?? 0,
      maxDrawdown: run.metrics?.max_drawdown ?? 0,
      winRate: run.metrics?.win_rate ?? 0,
      totalTrades: run.metrics?.total_trades ?? 0,
      netProfitCurrency: run.metrics?.net_profit_currency ?? 0,
      netProfit: run.metrics?.net_profit ?? 0,
      averageWin: run.metrics?.average_win ?? 0,
      averageLoss: run.metrics?.average_loss ?? 0,
      averageWinCurrency: run.metrics?.average_win_currency ?? 0,
      averageLossCurrency: run.metrics?.average_loss_currency ?? 0,
      profitFactor: run.metrics?.profit_factor ?? 0,
      profitLossRatio: run.metrics?.profit_loss_ratio ?? 0,
      expectancy: run.metrics?.expectancy ?? 0,
      alpha: run.metrics?.alpha ?? 0,
      beta: run.metrics?.beta ?? 0,
      annualStandardDeviation: run.metrics?.annual_standard_deviation ?? 0,
      annualVariance: run.metrics?.annual_variance ?? 0,
      informationRatio: run.metrics?.information_ratio ?? 0,
      trackingError: run.metrics?.tracking_error ?? 0,
      treynorRatio: run.metrics?.treynor_ratio ?? 0,
      totalFees: run.metrics?.total_fees ?? 0,
      estimatedStrategyCapacity: run.metrics?.estimated_strategy_capacity ?? 0,
      lowestCapacityAsset:
        typeof run.metrics?.lowest_capacity_asset === 'string'
          ? run.metrics.lowest_capacity_asset
          : run.metrics?.lowest_capacity_asset != null
            ? String(run.metrics.lowest_capacity_asset)
            : '',
      portfolioTurnover: run.metrics?.portfolio_turnover ?? 0,
      probabilisticSharpeRatio: run.metrics?.probabilistic_sharpe_ratio ?? 0,
      totalOrders: run.metrics?.total_orders ?? 0,
      lossRate: run.metrics?.loss_rate ?? 0,
      profitableTrades: run.metrics?.winning_trades ?? 0,
    },
    resolution: run.request.resolution,
    pivotBars: run.request.pivotBars,
    lowerTimeframe: run.request.lowerTimeframe,
    executionTimeMs: run.metrics?.execution_time_ms ?? 0,
    resultPath: run.resultPath ?? undefined,
    status: run.status,
    errorMessage: run.errorMessage ?? undefined,
    cacheHit: Boolean(run.metrics?.cache_hit),
    createdAt: run.createdAt,
  })

  const fetchBacktestResults = useCallback(async () => {
    dispatch({ type: 'SET_BACKTEST_LOADING', loading: true })
    try {
      const response = await backtestApi.listRuns({
        page: state.backtestResults.page,
        pageSize: state.backtestResults.pageSize,
      })

      dispatch({ type: 'SET_BACKTEST_RESULTS', data: response.runs.map(toSummary), totalCount: response.totalCount })
    } catch (error) {
      dispatch({
        type: 'SET_BACKTEST_ERROR',
        error: error instanceof Error ? error.message : 'Failed to fetch backtest results',
      })
    }
  }, [state.backtestResults.page, state.backtestResults.pageSize, dispatch])

  const getScreenerResultDetails = useCallback(async (resultId: string) => {
    return screenerResultsApi.detail(resultId)
  }, [])

  const getBacktestResultDetails = useCallback(async (backtestId: string) => {
    return backtestApi.getRun(backtestId)
  }, [])

  const deleteScreenerResult = useCallback(async (_resultId: string) => {
    throw new Error('Deleting screener results is not supported with the current backend API')
  }, [])

  const deleteBacktestResult = useCallback(async (_backtestId: string) => {
    throw new Error('Deleting backtest results is not supported with the current backend API')
  }, [])

  return {
    fetchScreenerResults,
    fetchBacktestResults,
    getScreenerResultDetails,
    getBacktestResultDetails,
    deleteScreenerResult,
    deleteBacktestResult,
  }
}
