import React, { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { StrategySelector } from './StrategySelector'
import { BacktestForm } from './BacktestForm'
import { BacktestMonitor } from './BacktestMonitor'
import { BacktestResultsView } from '../results/BacktestResultsView'
import { MarketStructureForm } from './MarketStructureForm'
import { useBacktestContext } from '@/contexts/BacktestContext'
import { useResultsContext } from '@/contexts/ResultsContext'
import { Play, RefreshCw, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'
import { getApiUrl } from '@/services/api'

interface BacktestingTabProps {
  screenerResults?: string[]
}

export function BacktestingTab({ screenerResults = [] }: BacktestingTabProps) {
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
        totalCount: data.total_count,
        page: data.page,
        pageSize: data.page_size
      })
      
      // Map API response to frontend format
      const mappedResults = data.results.map((result: any) => {
        // Convert snake_case statistics to camelCase
        const statistics = result.statistics ? {
          totalReturn: result.statistics.total_return,
          netProfit: result.statistics.net_profit,
          netProfitCurrency: result.statistics.net_profit_currency,
          compoundingAnnualReturn: result.statistics.compounding_annual_return,
          sharpeRatio: result.statistics.sharpe_ratio,
          sortinoRatio: result.statistics.sortino_ratio,
          maxDrawdown: result.statistics.max_drawdown,
          probabilisticSharpeRatio: result.statistics.probabilistic_sharpe_ratio,
          totalOrders: result.statistics.total_orders,
          totalTrades: result.statistics.total_trades,
          winRate: result.statistics.win_rate,
          lossRate: result.statistics.loss_rate,
          averageWin: result.statistics.average_win,
          averageLoss: result.statistics.average_loss,
          averageWinCurrency: result.statistics.average_win_currency,
          averageLossCurrency: result.statistics.average_loss_currency,
          profitFactor: result.statistics.profit_factor,
          profitLossRatio: result.statistics.profit_loss_ratio,
          expectancy: result.statistics.expectancy,
          alpha: result.statistics.alpha,
          beta: result.statistics.beta,
          annualStandardDeviation: result.statistics.annual_standard_deviation,
          annualVariance: result.statistics.annual_variance,
          informationRatio: result.statistics.information_ratio,
          trackingError: result.statistics.tracking_error,
          treynorRatio: result.statistics.treynor_ratio,
          startEquity: result.statistics.start_equity,
          endEquity: result.statistics.end_equity,
          totalFees: result.statistics.total_fees,
          estimatedStrategyCapacity: result.statistics.estimated_strategy_capacity,
          lowestCapacityAsset: result.statistics.lowest_capacity_asset,
          portfolioTurnover: result.statistics.portfolio_turnover
        } : {}
        
        return {
          ...result,
          statistics,
          timestamp: result.backtest_id, // For backward compatibility
          equityCurve: result.equity_curve || [],
          orders: result.trades || []
        }
      })
      
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

    try {
      let response
      
      if (parameters.useScreenerResults) {
        // Use latest UI screener session from database
        const strategyName = strategies.find(s => s.file_path === parameters.strategy)?.name || 'main'
        response = await fetch(`${getApiUrl()}/api/v2/backtest/run-screener-backtests`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            strategy_name: strategyName,
            initial_cash: parameters.initialCash,
            resolution: 'Minute',
            use_latest_ui_session: true,
            parameters: parameters.strategyParameters || {}
          })
        })
      } else {
        // Use regular bulk backtest endpoint
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
            parameters: parameters.strategyParameters || {}
          })
        })
      }

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to start backtests')
      }

      const data = await response.json()

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
      <BacktestForm screenerSymbols={screenerResults} />

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

      {/* Results */}
      <div className="mt-6">
        <BacktestResultsView />
      </div>
    </div>
  )
}