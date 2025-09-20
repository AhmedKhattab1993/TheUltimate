import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { StrategySelector } from './StrategySelector'
import { BacktestForm } from './BacktestForm'
import { BacktestMonitor } from './BacktestMonitor'
import { CombinedResultsView } from '../results/CombinedResultsView'
import { MarketStructureForm } from './MarketStructureForm'
import { useBacktestContext } from '@/contexts/BacktestContext'
import type { BacktestResult, BacktestStatistics } from '@/contexts/BacktestContext'
import { useResultsContext } from '@/contexts/ResultsContext'
import { Play, RefreshCw, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'
import { getApiUrl } from '@/services/api'

const toBacktestStatistics = (stats: any): BacktestStatistics => ({
  totalReturn: stats?.total_return ?? 0,
  netProfit: stats?.net_profit ?? 0,
  netProfitCurrency: stats?.net_profit_currency ?? 0,
  compoundingAnnualReturn: stats?.compounding_annual_return ?? 0,
  sharpeRatio: stats?.sharpe_ratio ?? 0,
  sortinoRatio: stats?.sortino_ratio ?? 0,
  maxDrawdown: stats?.max_drawdown ?? 0,
  probabilisticSharpeRatio: stats?.probabilistic_sharpe_ratio ?? 0,
  totalOrders: stats?.total_orders ?? 0,
  totalTrades: stats?.total_trades ?? 0,
  winRate: stats?.win_rate ?? 0,
  lossRate: stats?.loss_rate ?? 0,
  averageWin: stats?.average_win ?? 0,
  averageLoss: stats?.average_loss ?? 0,
  averageWinCurrency: stats?.average_win_currency ?? 0,
  averageLossCurrency: stats?.average_loss_currency ?? 0,
  profitFactor: stats?.profit_factor ?? 0,
  profitLossRatio: stats?.profit_loss_ratio ?? 0,
  expectancy: stats?.expectancy ?? 0,
  alpha: stats?.alpha ?? 0,
  beta: stats?.beta ?? 0,
  annualStandardDeviation: stats?.annual_standard_deviation ?? 0,
  annualVariance: stats?.annual_variance ?? 0,
  informationRatio: stats?.information_ratio ?? 0,
  trackingError: stats?.tracking_error ?? 0,
  treynorRatio: stats?.treynor_ratio ?? 0,
  startEquity: stats?.start_equity ?? 0,
  endEquity: stats?.end_equity ?? 0,
  totalFees: stats?.total_fees ?? 0,
  estimatedStrategyCapacity: stats?.estimated_strategy_capacity ?? 0,
  lowestCapacityAsset: stats?.lowest_capacity_asset ?? '',
  portfolioTurnover: stats?.portfolio_turnover ?? 0,
  profitableTrades: stats?.profitable_trades ?? stats?.winning_trades ?? 0
})

const mapBacktestResult = (result: any): BacktestResult => {
  const backtestId = String(result.backtest_id ?? result.backtestId ?? result.timestamp ?? '')
  return {
    backtest_id: backtestId,
    backtestId,
    timestamp: String(result.timestamp ?? backtestId),
    statistics: toBacktestStatistics(result.statistics ?? {}),
    equityCurve: result.equity_curve ?? [],
    orders: result.trades ?? result.orders ?? [],
    logs: result.logs,
    strategy_name: result.strategy_name ?? result.strategyName,
    strategyName: result.strategyName ?? result.strategy_name,
    start_date: result.start_date,
    end_date: result.end_date,
    initial_cash: result.initial_cash,
    final_value: result.final_value
  }
}

export function BacktestingTab() {
  const { state, dispatch } = useBacktestContext()
  const { dispatch: resultsDispatch } = useResultsContext()
  const { parameters, isRunning, error, strategies } = state

  // Fetch available strategies on mount
  useEffect(() => {
    fetchStrategies()
    fetchHistoricalResults()
  }, [])

  const fetchStrategies = async () => {
    try {
      const response = await fetch(`${getApiUrl()}/api/v2/backtest/strategies`)
      if (!response.ok) throw new Error('Failed to fetch strategies')
      const data = await response.json()
      dispatch({ type: 'SET_STRATEGIES', strategies: data })
    } catch (err) {
      dispatch({ type: 'SET_ERROR', error: 'Failed to load strategies' })
    }
  }

  const fetchHistoricalResults = async () => {
    try {
      const response = await fetch(`${getApiUrl()}/api/v2/backtest/results`)
      if (!response.ok) throw new Error('Failed to fetch historical results')
      const data = await response.json()
      
      // Update the ResultsContext with the fetched data
      resultsDispatch({
        type: 'SET_BACKTEST_RESULTS',
        data: data.results,
        totalCount: data.total_count
      })
      if (typeof data.page === 'number') {
        resultsDispatch({ type: 'SET_BACKTEST_PAGE', page: data.page })
      }
      
      // Map API response to frontend format
      const mappedResults: BacktestResult[] = data.results.map((result: any) => mapBacktestResult(result))
      
      dispatch({ type: 'SET_HISTORICAL_RESULTS', results: mappedResults })
    } catch (err) {
      console.error('Failed to load historical results:', err)
    }
  }

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

    // Track the symbols being run
    let runSymbols: string[] = []

    try {
      let response
      
      if (parameters.useScreenerResults) {
        // For screener results, we'll get the symbols from the response
        const strategyName = strategies.find(s => s.file_path === parameters.strategy)?.name || 'main'
        const requestBody = {
          strategy_name: strategyName,
          initial_cash: parameters.initialCash,
          resolution: 'Minute',
          use_latest_ui_session: true,
          parameters: parameters.strategyParameters || {}
        }
        console.log('Screener backtest request:', requestBody)
        console.log('Strategy parameters:', parameters.strategyParameters)
        response = await fetch(`${getApiUrl()}/api/v2/backtest/run-screener-backtests`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody)
        })
      } else {
        // Use regular bulk backtest endpoint
        runSymbols = parameters.symbols
        // Extract lower_timeframe and pivot_bars from strategyParameters for root level
        const { lower_timeframe, pivot_bars, ...otherParams } = parameters.strategyParameters || {};
        
        response = await fetch(`${getApiUrl()}/api/v2/backtest/run-bulk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            strategy_name: strategies.find(s => s.file_path === parameters.strategy)?.name || 'main',
            initial_cash: parameters.initialCash,
            start_date: format(parameters.startDate!, 'yyyy-MM-dd'),
            end_date: format(parameters.endDate!, 'yyyy-MM-dd'),
            symbols: parameters.symbols,
            use_screener_results: false,
            lower_timeframe: lower_timeframe || '5min',
            pivot_bars: pivot_bars || 20,
            parameters: otherParams
          })
        })
      }

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to start backtests')
      }

      const data = await response.json()

      // Extract symbols from response if using screener results
      if (parameters.useScreenerResults && data.symbols) {
        runSymbols = data.symbols
      }

      // Store last run details
      dispatch({ 
        type: 'SET_LAST_RUN_DETAILS', 
        details: {
          symbols: runSymbols,
          startTime: new Date(),
          bulkId: data.bulk_id,
          screenerSessionId: data.screener_session_id
        }
      })

      // Connect to simplified WebSocket endpoint
      if (data.bulk_id) {
        connectWebSocket(data.bulk_id)
      }

    } catch (err) {
      dispatch({ 
        type: 'SET_ERROR', 
        error: err instanceof Error ? err.message : 'Failed to run backtests' 
      })
    }
  }

  const connectWebSocket = (bulkId: string) => {
    const timestamp = new Date().toLocaleTimeString() + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
    console.log(`[BacktestingTab] WEBSOCKET_CONNECT START at ${timestamp} - bulkId: ${bulkId}`)
    console.log(`[BacktestingTab] Current isRunning state: ${isRunning}`)
    
    // Close existing connection if any
    if (state.websocket) {
      console.log('[BacktestingTab] Closing existing WebSocket connection')
      state.websocket.close()
    }

    const wsUrl = getApiUrl().replace('http', 'ws')
    const fullWsUrl = `${wsUrl}/api/v2/backtest/monitor/bulk/${bulkId}`
    console.log(`[BacktestingTab] Connecting to WebSocket URL: ${fullWsUrl}`)
    const ws = new WebSocket(fullWsUrl)

    ws.onopen = () => {
      const connectTime = new Date().toLocaleTimeString() + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
      console.log(`[BacktestingTab] ✅ WEBSOCKET CONNECTED at ${connectTime} for bulkId: ${bulkId}`)
      console.log(`[BacktestingTab] WebSocket readyState: ${ws.readyState}`)
    }

    ws.onmessage = (event) => {
      const messageTime = new Date().toLocaleTimeString() + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
      const data = JSON.parse(event.data)
      console.log(`[BacktestingTab] 📨 WEBSOCKET MESSAGE RECEIVED at ${messageTime}:`, data)
      console.log(`[BacktestingTab] Message type: ${data.type}, bulk_id: ${data.bulk_id}`)
      console.log(`[BacktestingTab] Current isRunning before processing: ${isRunning}`)
      
      // Only listen for completion message
      if (data.type === 'all_complete') {
        console.log(`[BacktestingTab] 🎉 ALL BACKTESTS COMPLETE for bulk_id: ${data.bulk_id}`)
        console.log('[BacktestingTab] Dispatching COMPLETE_BACKTESTS action')
        
        // Update state to not running
        dispatch({ type: 'COMPLETE_BACKTESTS' })
        
        // Refresh results and close WebSocket
        setTimeout(() => {
          console.log('[BacktestingTab] Refreshing results and closing WebSocket after 500ms')
          fetchHistoricalResults()
          if (ws.readyState === WebSocket.OPEN) {
            console.log('[BacktestingTab] Closing WebSocket')
            ws.close()
          } else {
            console.log(`[BacktestingTab] WebSocket already closed, readyState: ${ws.readyState}`)
          }
        }, 500)
      } else {
        console.log(`[BacktestingTab] Ignoring message with type: ${data.type}`)
      }
    }

    ws.onerror = (error) => {
      const errorTime = new Date().toLocaleTimeString() + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
      console.error(`[BacktestingTab] ❌ WEBSOCKET ERROR at ${errorTime}:`, error)
      console.error(`[BacktestingTab] WebSocket readyState: ${ws.readyState}`)
      dispatch({ 
        type: 'SET_ERROR', 
        error: 'Lost connection to backtest updates' 
      })
    }

    ws.onclose = (event) => {
      const closeTime = new Date().toLocaleTimeString() + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
      console.log(`[BacktestingTab] 🔌 WEBSOCKET DISCONNECTED at ${closeTime}`)
      console.log(`[BacktestingTab] Close code: ${event.code}, reason: ${event.reason}, wasClean: ${event.wasClean}`)
      dispatch({ type: 'SET_WEBSOCKET', websocket: null })
    }

    console.log('[BacktestingTab] Setting WebSocket in context')
    dispatch({ type: 'SET_WEBSOCKET', websocket: ws })
  }

  const handleReset = () => {
    dispatch({ type: 'RESET' })
  }

  // isRunning state is now directly from context

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold">Backtesting</h2>
        <p className="text-muted-foreground mt-1">
          Test LEAN strategies with historical data
        </p>
      </div>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Strategy Selection */}
      <StrategySelector />

      {/* Backtest Parameters */}
      <BacktestForm />

      {/* Strategy-specific parameters */}
      {parameters.strategy && strategies.find(s => s.file_path === parameters.strategy)?.name === 'MarketStructure' && (
        <MarketStructureForm 
          parameters={parameters.strategyParameters || {}}
          onParameterChange={(field, value) => {
            dispatch({ 
              type: 'SET_PARAMETER', 
              field: 'strategyParameters',
              value: { ...parameters.strategyParameters, [field]: value }
            })
          }}
        />
      )}

      {/* Progress Monitor */}
      <BacktestMonitor />

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          onClick={runBacktest}
          disabled={isRunning}
          size="lg"
        >
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


        <Button
          variant="outline"
          onClick={handleReset}
          disabled={isRunning}
          size="lg"
        >
          Reset
        </Button>
      </div>

      {/* Results - Show combined view filtered for last run */}
      <div className="mt-6">
        {state.lastRunDetails && (
          <CombinedResultsView 
            filterByLatestRun={true} 
            hideFilters={true} 
          />
        )}
      </div>
    </div>
  )
}
