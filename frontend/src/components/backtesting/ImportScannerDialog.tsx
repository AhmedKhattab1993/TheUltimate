import React, { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Calendar, FileSearch, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'
import { getApiUrl } from '@/services/api'

interface ScreenerResultGroup {
  date: string
  sessions: Array<{
    session_id: string
    symbol_count: number
    symbols: string[]
  }>
  total_symbols: number
  all_symbols: string[]
}

interface ImportScannerDialogProps {
  open: boolean
  onClose: () => void
  onImport: (dateRange: { start: string; end: string }) => void
  parameters: {
    strategy: string
    initialCash: number
    strategyParameters?: any
  }
}

export function ImportScannerDialog({ 
  open, 
  onClose, 
  onImport,
  parameters 
}: ImportScannerDialogProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [screenerResults, setScreenerResults] = useState<ScreenerResultGroup[]>([])
  const [selectedDates, setSelectedDates] = useState<Set<string>>(new Set())
  const [totalSymbols, setTotalSymbols] = useState(0)

  useEffect(() => {
    if (open) {
      fetchScreenerResults()
    }
  }, [open])

  const fetchScreenerResults = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${getApiUrl()}/api/v2/backtest/screener-results/grouped`)
      if (!response.ok) {
        throw new Error('Failed to fetch screener results')
      }
      
      const data = await response.json()
      setScreenerResults(data.results || [])
      
      // Select all dates by default
      const allDates = new Set(data.results.map((r: ScreenerResultGroup) => r.date))
      setSelectedDates(allDates)
      
      // Calculate total symbols
      const total = data.results.reduce((sum: number, group: ScreenerResultGroup) => {
        return sum + group.total_symbols
      }, 0)
      setTotalSymbols(total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load screener results')
    } finally {
      setLoading(false)
    }
  }

  const handleDateToggle = (date: string) => {
    const newSelected = new Set(selectedDates)
    if (newSelected.has(date)) {
      newSelected.delete(date)
    } else {
      newSelected.add(date)
    }
    setSelectedDates(newSelected)
  }

  const handleSelectAll = () => {
    if (selectedDates.size === screenerResults.length) {
      setSelectedDates(new Set())
    } else {
      const allDates = new Set(screenerResults.map(r => r.date))
      setSelectedDates(allDates)
    }
  }

  const calculateSelectedBacktests = () => {
    return screenerResults
      .filter(group => selectedDates.has(group.date))
      .reduce((sum, group) => sum + group.total_symbols, 0)
  }

  const handleImport = async () => {
    if (selectedDates.size === 0) {
      setError('Please select at least one date')
      return
    }

    const sortedDates = Array.from(selectedDates).sort()
    const dateRange = {
      start: sortedDates[sortedDates.length - 1], // Earliest date
      end: sortedDates[0] // Latest date
    }

    setLoading(true)
    setError(null)

    try {
      // Start backtests for screener results
      const response = await fetch(
        `${getApiUrl()}/api/v2/backtest/run-screener-backtests?` + 
        new URLSearchParams({
          start_date: dateRange.start,
          end_date: dateRange.end,
          strategy_name: parameters.strategy,
          initial_cash: parameters.initialCash.toString(),
          resolution: 'Minute',
          ...(parameters.strategyParameters && { parameters: JSON.stringify(parameters.strategyParameters) })
        }),
        {
          method: 'POST'
        }
      )

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to start backtests')
      }

      const data = await response.json()
      
      // Success - close dialog and let parent handle the response
      onImport(dateRange)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start backtests')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSearch className="h-5 w-5" />
            Import Scanner Results
          </DialogTitle>
          <DialogDescription>
            Select screening dates to import. Backtests will run for each symbol on its screening day.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-4">
          {/* Summary */}
          <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
            <div className="flex items-center gap-4">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSelectAll}
                disabled={loading}
              >
                {selectedDates.size === screenerResults.length ? 'Deselect All' : 'Select All'}
              </Button>
              <span className="text-sm text-muted-foreground">
                {selectedDates.size} of {screenerResults.length} dates selected
              </span>
            </div>
            <div className="text-sm">
              <span className="font-medium">{calculateSelectedBacktests()}</span>
              <span className="text-muted-foreground"> backtests will be created</span>
            </div>
          </div>

          {/* Results list */}
          <ScrollArea className="h-[400px] pr-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-muted-foreground">Loading screener results...</div>
              </div>
            ) : screenerResults.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <FileSearch className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No screener results found in database</p>
                <p className="text-sm text-muted-foreground mt-2">
                  Run a screening first to generate results
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {screenerResults.map((group) => (
                  <div
                    key={group.date}
                    className={`p-4 border rounded-lg transition-colors ${
                      selectedDates.has(group.date) 
                        ? 'bg-accent/50 border-accent' 
                        : 'hover:bg-muted/50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <Checkbox
                        checked={selectedDates.has(group.date)}
                        onCheckedChange={() => handleDateToggle(group.date)}
                        className="mt-1"
                      />
                      <div className="flex-1 space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Calendar className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">
                              {format(new Date(group.date), 'EEEE, MMMM d, yyyy')}
                            </span>
                          </div>
                          <Badge variant="secondary">
                            {group.total_symbols} symbols
                          </Badge>
                        </div>
                        
                        {/* Sessions */}
                        {group.sessions.map((session) => (
                          <div key={session.session_id} className="ml-6 text-sm">
                            <div className="flex items-center gap-2 text-muted-foreground mb-1">
                              <span>Session {session.session_id.slice(0, 8)}</span>
                              <span>•</span>
                              <span>{session.symbol_count} symbols</span>
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {session.symbols.slice(0, 10).map((symbol) => (
                                <Badge 
                                  key={symbol} 
                                  variant="outline" 
                                  className="text-xs py-0 h-5"
                                >
                                  {symbol}
                                </Badge>
                              ))}
                              {session.symbols.length > 10 && (
                                <Badge 
                                  variant="outline" 
                                  className="text-xs py-0 h-5 text-muted-foreground"
                                >
                                  +{session.symbols.length - 10} more
                                </Badge>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button 
            onClick={handleImport} 
            disabled={loading || selectedDates.size === 0}
          >
            {loading ? 'Starting Backtests...' : `Import ${calculateSelectedBacktests()} Backtests`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}