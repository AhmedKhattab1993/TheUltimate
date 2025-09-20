import { useCallback, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { StrategySelector } from './StrategySelector'
import { BacktestForm } from './BacktestForm'
import { BacktestMonitor } from './BacktestMonitor'
import { CombinedResultsView } from '../results/CombinedResultsView'
import { MarketStructureForm } from './MarketStructureForm'
import { useBacktestContext } from '@/contexts/BacktestContext'
import type { BacktestResult, BacktestStatistics, Strategy } from '@/contexts/BacktestContext'
import { useResultsContext } from '@/contexts/ResultsContext'
import { Play, RefreshCw, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'
import { backtestApi, registryApi } from '@/services/api'
import type { BacktestRunInfo, StrategyDefinition } from '@/types/api'

const toStatistics = (metrics: BacktestRunInfo['metrics'] | undefined): BacktestStatistics => ({
  totalReturn: metrics?.total_return ?? 0,
  netProfit: metrics?.net_profit ?? 0,
  netProfitCurrency: metrics?.net_profit_currency ?? 0,
  compoundingAnnualReturn: metrics?.compounding_annual_return ?? 0,
  sharpeRatio: metrics?.sharpe_ratio ?? 0,
  sortinoRatio: metrics?.sortino_ratio ?? 0,
  maxDrawdown: metrics?.max_drawdown ?? 0,
  probabilisticSharpeRatio: metrics?.probabilistic_sharpe_ratio ?? 0,
  totalOrders: metrics?.total_orders ?? 0,
  totalTrades: metrics?.total_trades ?? 0,
  winRate: metrics?.win_rate ?? 0,
  lossRate: metrics?.loss_rate ?? 0,
  averageWin: metrics?.average_win ?? 0,
  averageLoss: metrics?.average_loss ?? 0,
  averageWinCurrency: metrics?.average_win_currency ?? 0,
  averageLossCurrency: metrics?.average_loss_currency ?? 0,
  profitFactor: metrics?.profit_factor ?? 0,
  profitLossRatio: metrics?.profit_loss_ratio ?? 0,
  expectancy: metrics?.expectancy ?? 0,
  alpha: metrics?.alpha ?? 0,
  beta: metrics?.beta ?? 0,
  annualStandardDeviation: metrics?.annual_standard_deviation ?? 0,
  annualVariance: metrics?.annual_variance ?? 0,
  informationRatio: metrics?.information_ratio ?? 0,
  trackingError: metrics?.tracking_error ?? 0,
  treynorRatio: metrics?.treynor_ratio ?? 0,
  startEquity: metrics?.start_equity ?? 0,
  endEquity: metrics?.end_equity ?? 0,
  totalFees: metrics?.total_fees ?? 0,
  estimatedStrategyCapacity: metrics?.estimated_strategy_capacity ?? 0,
  lowestCapacityAsset:
    typeof metrics?.lowest_capacity_asset === 'string'
      ? metrics.lowest_capacity_asset
      : metrics?.lowest_capacity_asset != null
        ? String(metrics.lowest_capacity_asset)
        : '',
  portfolioTurnover: metrics?.portfolio_turnover ?? 0,
  profitableTrades: metrics?.winning_trades ?? 0,
})

const mapStrategy = (strategy: StrategyDefinition): Strategy => ({
  name: strategy.label,
  file_path: strategy.projectPath,
  description: strategy.description,
  parameters: strategy.parameters,
  last_modified: undefined,
})

const mapRunToResult = (run: BacktestRunInfo): BacktestResult => ({
  backtest_id: run.backtestId,
  backtestId: run.backtestId,
  timestamp: run.createdAt,
  statistics: toStatistics(run.metrics),
  equityCurve: [],
  orders: [],
  strategyName: run.request.strategyName,
  strategy_name: run.request.strategyName,
  start_date: run.request.startDate,
  end_date: run.request.endDate,
  initial_cash: run.request.initialCash,
  final_value: undefined,
})

const mapRunToSummary = (run: BacktestRunInfo) => ({
  backtestId: run.backtestId,
  strategyName: run.request.strategyName,
  startDate: run.request.startDate,
  endDate: run.request.endDate,
  initialCash: run.request.initialCash,
  finalValue: undefined,
  statistics: toStatistics(run.metrics),
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

const normaliseParameters = (params: Record<string, unknown> | undefined) => {
  const normalised: Record<string, string | number | boolean> = {}
  if (!params) return normalised
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      normalised[key] = value
    }
  }
  return normalised
}

export function BacktestingTab() {
  const { state, dispatch } = useBacktestContext()
  const { dispatch: resultsDispatch } = useResultsContext()
  const { parameters, isRunning, error, strategies } = state

  const loadStrategies = useCallback(async () => {
    try {
      const response = await registryApi.fetch()
      const mapped = response.strategies.map(mapStrategy)
      dispatch({ type: 'SET_STRATEGIES', strategies: mapped })
    } catch (err) {
      dispatch({ type: 'SET_ERROR', error: 'Failed to load strategies' })
    }
  }, [dispatch])

  const loadHistoricalResults = useCallback(async () => {
    try {
      const response = await backtestApi.listRuns({ page: 1, pageSize: 20 })
      const mappedResults = response.runs.map(mapRunToResult)
      dispatch({ type: 'SET_HISTORICAL_RESULTS', results: mappedResults })
      resultsDispatch({ type: 'SET_BACKTEST_RESULTS', data: response.runs.map(mapRunToSummary), totalCount: response.totalCount })
    } catch (err) {
      // Surface but do not break UX
      console.error('Failed to load backtest runs', err)
    }
  }, [dispatch, resultsDispatch])

  useEffect(() => {
    loadStrategies()
    loadHistoricalResults()
  }, [loadStrategies, loadHistoricalResults])

  const validateForm = () => {
    if (!parameters.strategy || parameters.strategy === '') {
      dispatch({ type: 'SET_ERROR', error: 'Please select a strategy' })
      return false
    }
    if (!parameters.startDate || !parameters.endDate) {
      dispatch({ type: 'SET_ERROR', error: 'Please select both start and end dates' })
      return false
    }
    if (parameters.startDate >= parameters.endDate) {
      dispatch({ type: 'SET_ERROR', error: 'Start date must be before end date' })
      return false
    }
    if (parameters.symbols.length === 0 && !parameters.useScreenerResults) {
      dispatch({ type: 'SET_ERROR', error: 'Please add at least one symbol or use screener results' })
      return false
    }
    if (parameters.initialCash < 1000) {
      dispatch({ type: 'SET_ERROR', error: 'Initial cash must be at least $1,000' })
      return false
    }
    return true
  }

  const runBacktest = async () => {
    if (!validateForm()) return

    dispatch({ type: 'START_BACKTESTS' })
    dispatch({ type: 'CLEAR_ERROR' })

    try {
      const strategy = strategies.find((s) => s.file_path === parameters.strategy)
      const payload = {
        strategyName: strategy?.name ?? 'main',
        startDate: format(parameters.startDate!, 'yyyy-MM-dd'),
        endDate: format(parameters.endDate!, 'yyyy-MM-dd'),
        initialCash: parameters.initialCash,
        resolution: 'Minute' as const,
        pivotBars: Number(parameters.strategyParameters?.pivot_bars ?? 20),
        lowerTimeframe: String(parameters.strategyParameters?.lower_timeframe ?? '5min'),
        symbols: parameters.useScreenerResults ? [] : parameters.symbols,
        useScreenerResults: parameters.useScreenerResults ?? false,
        parameters: normaliseParameters(parameters.strategyParameters),
      }

      const runInfo = await backtestApi.start(payload)
      const result = mapRunToResult(runInfo)
      dispatch({ type: 'SET_RESULT', result })
      dispatch({
        type: 'SET_LAST_RUN_DETAILS',
        details: {
          symbols: runInfo.targets ?? payload.symbols ?? [],
          startTime: new Date(),
          bulkId: runInfo.backtestId,
        },
      })

      // Poll once for updated status to capture completion state.
      setTimeout(async () => {
        try {
          const refreshed = await backtestApi.getRun(runInfo.backtestId)
          dispatch({ type: 'SET_RESULT', result: mapRunToResult(refreshed) })
          dispatch({ type: 'COMPLETE_BACKTESTS' })
          loadHistoricalResults()
        } catch (pollError) {
          console.error('Failed to refresh backtest status', pollError)
          dispatch({ type: 'COMPLETE_BACKTESTS' })
        }
      }, 3000)
    } catch (err) {
      dispatch({
        type: 'SET_ERROR',
        error: err instanceof Error ? err.message : 'Failed to run backtests',
      })
      dispatch({ type: 'COMPLETE_BACKTESTS' })
    }
  }

  const handleReset = () => {
    dispatch({ type: 'RESET' })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Backtesting</h2>
        <p className="text-muted-foreground mt-1">
          Test strategies against historical data with Lean jobs
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <StrategySelector />
      <BacktestForm />

      {parameters.strategy && strategies.find((s) => s.file_path === parameters.strategy)?.name === 'MarketStructure' && (
        <MarketStructureForm
          parameters={parameters.strategyParameters || {}}
          onParameterChange={(field, value) => {
            dispatch({
              type: 'SET_PARAMETER',
              field: 'strategyParameters',
              value: { ...parameters.strategyParameters, [field]: value },
            })
          }}
        />
      )}

      <BacktestMonitor />

      <div className="flex gap-3">
        <Button onClick={runBacktest} disabled={isRunning} size="lg">
          {isRunning ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Running Backtest...
            </>
          ) : (
            <>
              <Play className="mr-2 h-4 w-4" />
              Run Backtest
            </>
          )}
        </Button>

        <Button variant="outline" onClick={handleReset} disabled={isRunning} size="lg">
          Reset
        </Button>
      </div>

      <div className="mt-6">
        {state.lastRunDetails && (
          <CombinedResultsView filterByLatestRun hideFilters />
        )}
      </div>
    </div>
  )
}
