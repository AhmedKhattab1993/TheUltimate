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

interface ScreenerResultsPreviewDialogProps {
  open: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ScreenerResultsPreviewDialog({ open, onConfirm, onCancel }: ScreenerResultsPreviewDialogProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [summary, setSummary] = useState<{ timestamp: string; symbolCount: number } | null>(null)

  useEffect(() => {
    if (open) {
      void loadSummary()
    }
  }, [open])

  const loadSummary = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await screenerResultsApi.list({ page: 1, pageSize: 1 })
      const latest = response.results[0]
      if (latest) {
        setSummary({ timestamp: latest.timestamp, symbolCount: latest.symbolCount })
      } else {
        setSummary(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load screener results')
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = () => {
    if (summary) {
      onConfirm()
    } else {
      setError('No screener results available. Please run the screener first.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onCancel()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSearch className="h-5 w-5" />
            Latest Screener Results Preview
          </DialogTitle>
          <DialogDescription>
            Preview the most recent screener run before launching backtests.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            Loading latest screener run...
          </div>
        ) : summary ? (
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg space-y-1">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Calendar className="h-4 w-4" /> Last run
              </div>
              <div className="text-lg font-semibold">
                {format(new Date(summary.timestamp), 'PPP p')}
              </div>
              <div className="text-sm text-muted-foreground">
                {summary.symbolCount} symbols qualified
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Backtests will use the configuration associated with the latest screener execution.
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <FileSearch className="h-12 w-12 text-muted-foreground mb-3" />
            <p className="text-muted-foreground">No screener runs found.</p>
            <p className="text-sm text-muted-foreground">Run a screening first to generate results.</p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={loading || !summary}>
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
