import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Calendar, FileSearch, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'
import { getApiUrl } from '@/services/api'

interface LatestUISession {
  session_id: string
  created_at: string
  date_range: {
    start: string
    end: string
  }
  total_days: number
  total_symbols: number
  symbols_by_date: Record<string, string[]>
  all_symbols: string[]
}

interface ScreenerResultsPreviewDialogProps {
  open: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ScreenerResultsPreviewDialog({ 
  open, 
  onConfirm,
  onCancel
}: ScreenerResultsPreviewDialogProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [latestSession, setLatestSession] = useState<LatestUISession | null>(null)

  useEffect(() => {
    if (open) {
      fetchLatestUISession()
    }
  }, [open])

  const fetchLatestUISession = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${getApiUrl()}/api/v2/backtest/screener-results/latest-ui-session`)
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('No screener results found. Please run a screener first.')
        }
        throw new Error('Failed to fetch latest screener session')
      }
      
      const data = await response.json()
      setLatestSession(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load latest screener session')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = () => {
    if (latestSession) {
      onConfirm()
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onCancel()}>
      <DialogContent className="max-w-3xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSearch className="h-5 w-5" />
            Latest Screener Results Preview
          </DialogTitle>
          <DialogDescription>
            These symbols will be used for backtesting. Each symbol will be backtested on its screening day.
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
          {latestSession && (
            <div className="p-4 bg-muted rounded-lg space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Session Date</p>
                  <p className="font-medium">
                    {format(new Date(latestSession.created_at), 'MMMM d, yyyy h:mm a')}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Date Range</p>
                  <p className="font-medium">
                    {format(new Date(latestSession.date_range.start), 'MMM d')} - 
                    {format(new Date(latestSession.date_range.end), 'MMM d, yyyy')}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Trading Days</p>
                  <p className="font-medium">{latestSession.total_days}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Total Backtests</p>
                  <p className="font-medium">{latestSession.total_symbols}</p>
                </div>
              </div>
            </div>
          )}

          {/* Symbols by date */}
          <div className="h-[350px] overflow-y-auto pr-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-muted-foreground">Loading latest screener session...</div>
              </div>
            ) : !latestSession ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <FileSearch className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No screener results found</p>
                <p className="text-sm text-muted-foreground mt-2">
                  Run a screening first to generate results
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {Object.entries(latestSession.symbols_by_date)
                  .sort(([a], [b]) => b.localeCompare(a))
                  .map(([date, symbols]) => (
                    <div key={date} className="p-4 border rounded-lg bg-muted/50">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Calendar className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">
                              {format(new Date(date), 'EEEE, MMMM d, yyyy')}
                            </span>
                          </div>
                          <Badge variant="secondary">
                            {symbols.length} symbols
                          </Badge>
                        </div>
                        
                        <div className="flex flex-wrap gap-1 ml-6">
                          {symbols.slice(0, 15).map((symbol) => (
                            <Badge 
                              key={symbol} 
                              variant="outline" 
                              className="text-xs py-0 h-5"
                            >
                              {symbol}
                            </Badge>
                          ))}
                          {symbols.length > 15 && (
                            <Badge 
                              variant="outline" 
                              className="text-xs py-0 h-5 text-muted-foreground"
                            >
                              +{symbols.length - 15} more
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button 
            onClick={handleConfirm} 
            disabled={loading || !latestSession}
          >
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
