import React, { useCallback, useEffect } from 'react'
import { format, subDays } from 'date-fns'
import { Search, RefreshCw, AlertCircle, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DatePicker } from '@/components/ui/date-picker'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { SimplePriceRangeFilter } from '@/components/filters/SimplePriceRangeFilter'
import { PriceVsMAFilter } from '@/components/filters/PriceVsMAFilter'
import { RSIFilter } from '@/components/filters/RSIFilter'
import { ScreenerResults } from '@/components/results/ScreenerResults'
import { useScreenerContext } from '@/contexts/ScreenerContext'
import { useScreener } from '@/hooks/useScreener'
import { validateFilters } from '@/utils/validation'

export function SimpleStockScreener() {
  const { state, dispatch } = useScreenerContext()
  const { runScreener } = useScreener()
  const [localLoading, setLocalLoading] = React.useState(false)
  
  console.log('Loading state:', state.results.loading, 'Local loading:', localLoading)

  // Set default dates on mount
  useEffect(() => {
    const today = new Date()
    const thirtyDaysAgo = subDays(today, 30)
    
    dispatch({ type: 'SET_DATE_RANGE', field: 'startDate', value: thirtyDaysAgo })
    dispatch({ type: 'SET_DATE_RANGE', field: 'endDate', value: today })
  }, [dispatch])

  const handleSubmit = useCallback(async () => {
    // Validate dates
    if (!state.dateRange.startDate || !state.dateRange.endDate) {
      dispatch({ 
        type: 'SET_ERROR', 
        error: 'Please select both start and end dates' 
      })
      return
    }

    // Validate filters
    const validation = validateFilters(state)
    if (!validation.isValid) {
      dispatch({ 
        type: 'SET_ERROR', 
        error: validation.errors[0].message 
      })
      return
    }

    // Check if at least one filter is enabled
    const hasEnabledFilter = Object.values(state.filters).some(f => f.enabled)
    if (!hasEnabledFilter) {
      dispatch({ 
        type: 'SET_ERROR', 
        error: 'Please enable at least one filter' 
      })
      return
    }

    setLocalLoading(true)
    try {
      await runScreener()
    } finally {
      setLocalLoading(false)
    }
  }, [state, dispatch, runScreener])

  const handleReset = () => {
    dispatch({ type: 'RESET_FILTERS' })
  }

  const activeFilterCount = Object.values(state.filters).filter(f => f.enabled).length

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Simple Stock Screener</h1>
          <p className="text-muted-foreground mt-1">
            Find stocks using price, moving average, and RSI filters
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            {format(new Date(), 'PPP')}
          </span>
        </div>
      </div>


      {/* Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Screening Configuration</CardTitle>
          <CardDescription>
            Configure your date range for screening all US stocks
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Date Range */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <DatePicker
                date={state.dateRange.startDate || undefined}
                onDateChange={(date) => dispatch({ 
                  type: 'SET_DATE_RANGE', 
                  field: 'startDate', 
                  value: date || null 
                })}
                placeholder="Select start date"
              />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <DatePicker
                date={state.dateRange.endDate || undefined}
                onDateChange={(date) => dispatch({ 
                  type: 'SET_DATE_RANGE', 
                  field: 'endDate', 
                  value: date || null 
                })}
                placeholder="Select end date"
              />
            </div>
          </div>

        </CardContent>
      </Card>

      {/* Filters */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">
            Filters
            {activeFilterCount > 0 && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                ({activeFilterCount} active)
              </span>
            )}
          </h2>
        </div>
        
        <div className="grid gap-4">
          <SimplePriceRangeFilter />
          <PriceVsMAFilter />
          <RSIFilter />
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Button 
          onClick={handleSubmit} 
          disabled={localLoading || state.results.loading || activeFilterCount === 0}
          size="lg"
        >
          {(localLoading || state.results.loading) ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Screening...
            </>
          ) : (
            <>
              <Search className="mr-2 h-4 w-4" />
              Run Screener
            </>
          )}
        </Button>
        
        <Button 
          variant="outline" 
          onClick={handleReset}
          disabled={localLoading || state.results.loading}
          size="lg"
        >
          Reset Filters
        </Button>
      </div>

      {/* Error Display */}
      {state.results.error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{state.results.error}</AlertDescription>
        </Alert>
      )}

      {/* Results */}
      <ScreenerResults />

      {/* Loading Overlay */}
      {(localLoading || state.results.loading) && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center">
          <Card className="p-6">
            <div className="flex flex-col items-center space-y-4">
              <RefreshCw className="h-8 w-8 animate-spin text-primary" />
              <div className="text-center">
                <p className="text-lg font-semibold">Screening in Progress...</p>
                <p className="text-sm text-muted-foreground mt-1">
                  This may take a minute for all US stocks
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}