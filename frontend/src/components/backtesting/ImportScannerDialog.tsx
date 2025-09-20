import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Calendar, FileSearch, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'
import { screenerResultsApi } from '@/services/api'

interface ImportScannerDialogProps {
  open: boolean
  onClose: () => void
  onImport: (dateRange: { start: string; end: string }) => void
  parameters: {
    strategy: string
    initialCash: number
    strategyParameters?: Record<string, unknown>
  }
}

interface LatestSummary {
  id: string
  timestamp: string
  symbolCount: number
  filters: Record<string, unknown>
}

const extractDateRange = (filters: Record<string, unknown>) => {
  const start = typeof filters.start_date === 'string' ? filters.start_date : ''
  const end = typeof filters.end_date === 'string' ? filters.end_date : ''
  return { start, end }
}

export function ImportScannerDialog({ open, onClose, onImport }: ImportScannerDialogProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [latestSummary, setLatestSummary] = useState<LatestSummary | null>(null)

  useEffect(() => {
    if (open) {
      void loadLatestSummary()
    }
  }, [open])

  const loadLatestSummary = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await screenerResultsApi.list({ page: 1, pageSize: 1 })
      const summary = response.results[0]
      if (summary) {
        setLatestSummary({
          id: summary.id,
          timestamp: summary.timestamp,
          symbolCount: summary.symbolCount,
          filters: summary.filters,
        })
      } else {
        setLatestSummary(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load screener results')
      setLatestSummary(null)
    } finally {
      setLoading(false)
    }
  }

  const handleImport = () => {
    if (!latestSummary) {
      setError('No screener results available. Please run the screener first.')
      return
    }

    const dateRange = extractDateRange(latestSummary.filters)
    onImport(dateRange)
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSearch className="h-5 w-5" />
            Import Latest Screener Session
          </DialogTitle>
          <DialogDescription>
            Use symbols from your most recent screener run when launching backtests.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-10 text-muted-foreground">
            Loading latest screener summary...
          </div>
        ) : latestSummary ? (
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg space-y-2">
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <Calendar className="h-4 w-4" /> Last run
              </div>
              <div className="text-lg font-semibold">
                {format(new Date(latestSummary.timestamp), 'PPP p')}
              </div>
              <div className="text-sm text-muted-foreground">
                {latestSummary.symbolCount} symbols qualified
              </div>
            </div>

            <div className="border rounded-lg p-4 bg-muted/50 space-y-2">
              <div className="text-sm font-medium">Active filters</div>
              <pre className="text-xs whitespace-pre-wrap text-muted-foreground">
                {JSON.stringify(latestSummary.filters, null, 2)}
              </pre>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <FileSearch className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-muted-foreground">No screener runs found.</p>
            <p className="text-sm text-muted-foreground">Run the screener to generate results for backtesting.</p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleImport} disabled={!latestSummary}>
            Use Screener Symbols
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
