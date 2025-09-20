import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2 } from 'lucide-react'
import { combinedResultsApi } from '@/services/api'

interface CombinedResultsViewProps {
  filterByLatestRun?: boolean
  hideFilters?: boolean
}

export function CombinedResultsView({ filterByLatestRun = false, hideFilters: _hideFilters = false }: CombinedResultsViewProps = {}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<Array<{ symbol: string; strategyName?: string; totalReturn?: number; screenerCreatedAt: string }>>([])

  useEffect(() => {
    void loadResults()
  }, [filterByLatestRun])

  const loadResults = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await combinedResultsApi.list({ limit: filterByLatestRun ? 50 : 100 })
      const mapped = response.results.map((row) => ({
        symbol: row.symbol,
        strategyName: row.strategyName ?? undefined,
        totalReturn: typeof row.backtestMetrics?.total_return === 'number' ? Number(row.backtestMetrics.total_return) : undefined,
        screenerCreatedAt: row.screenerCreatedAt ?? '',
      }))
      setResults(mapped)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load combined results')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Combined Screener & Backtest Results</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading combined results...
          </div>
        ) : error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : results.length === 0 ? (
          <p className="text-sm text-muted-foreground">No combined results available yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Total Return</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((row, index) => (
                  <TableRow key={`${row.symbol}-${index}`}>
                    <TableCell>{row.screenerCreatedAt ? new Date(row.screenerCreatedAt).toLocaleDateString() : '—'}</TableCell>
                    <TableCell>{row.symbol}</TableCell>
                    <TableCell>{row.strategyName ?? '—'}</TableCell>
                    <TableCell>
                      {typeof row.totalReturn === 'number' ? `${row.totalReturn.toFixed(2)}%` : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
