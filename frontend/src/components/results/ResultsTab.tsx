import React, { useEffect } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useResultsContext } from '@/contexts/ResultsContext'
import { useResults } from '@/hooks/useResults'
import { ScreenerResultsView } from './ScreenerResultsView'
import { BacktestResultsView } from './BacktestResultsView'

export function ResultsTab() {
  const { state, dispatch } = useResultsContext()
  const { fetchScreenerResults, fetchBacktestResults } = useResults()

  // Fetch results when tab changes or page changes
  useEffect(() => {
    if (state.activeTab === 'screener') {
      fetchScreenerResults()
    } else {
      fetchBacktestResults()
    }
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

      {/* Results Tabs */}
      <Tabs
        value={state.activeTab}
        onValueChange={(value) => dispatch({ type: 'SET_ACTIVE_TAB', tab: value as 'screener' | 'backtest' })}
      >
        <TabsList className="grid w-full grid-cols-2">
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
        </TabsList>

        <TabsContent value="screener" className="mt-6">
          <ScreenerResultsView />
        </TabsContent>

        <TabsContent value="backtest" className="mt-6">
          <BacktestResultsView />
        </TabsContent>
      </Tabs>
    </div>
  )
}