import React, { useEffect } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useResultsContext } from '@/contexts/ResultsContext'
import { useResults } from '@/hooks/useResults'
import { ScreenerResultsView } from './ScreenerResultsView'
import { BacktestResultsView } from './BacktestResultsView'
import { CombinedResultsView } from './CombinedResultsView'

export function ResultsTab() {
  const { state, dispatch } = useResultsContext()
  const { fetchScreenerResults, fetchBacktestResults } = useResults()

  // Set default tab to combined on mount
  useEffect(() => {
    dispatch({ type: 'SET_ACTIVE_TAB', tab: 'combined' })
  }, [dispatch])

  // Fetch results when tab changes or page changes (kept for future reference)
  useEffect(() => {
    if (state.activeTab === 'screener') {
      fetchScreenerResults()
    } else if (state.activeTab === 'backtest') {
      fetchBacktestResults()
    }
    // Combined tab fetches its own data
  }, [state.activeTab, state.screenerResults.page, state.backtestResults.page, fetchScreenerResults, fetchBacktestResults])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold">Results History</h2>
        <p className="text-muted-foreground mt-1">
          View and manage your screening and backtesting results
        </p>
      </div>

      {/* Show Combined Results directly without tabs */}
      <CombinedResultsView />

      {/* Hidden Tabs - kept for future reference */}
      <div style={{ display: 'none' }}>
        <Tabs
          value={state.activeTab}
          onValueChange={(value) => dispatch({ type: 'SET_ACTIVE_TAB', tab: value as 'screener' | 'backtest' | 'combined' })}
        >
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="screener">
              Screener Results
              {state.screenerResults.totalCount > 0 && (
                <span className="ml-2 text-xs bg-muted px-2 py-0.5 rounded-full">
                  {state.screenerResults.totalCount}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="backtest">
              Backtest Results
              {state.backtestResults.totalCount > 0 && (
                <span className="ml-2 text-xs bg-muted px-2 py-0.5 rounded-full">
                  {state.backtestResults.totalCount}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="combined">
              Combined Results
            </TabsTrigger>
          </TabsList>

          <TabsContent value="screener" className="mt-6">
            <ScreenerResultsView />
          </TabsContent>

          <TabsContent value="backtest" className="mt-6">
            <BacktestResultsView />
          </TabsContent>
          
          <TabsContent value="combined" className="mt-6">
            <CombinedResultsView />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}