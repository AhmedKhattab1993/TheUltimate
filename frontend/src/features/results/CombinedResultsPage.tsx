import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format, subDays } from 'date-fns'

import { combinedResultsApi } from '@/services/api'
import type { CombinedRow } from '@/types/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DatePicker } from '@/components/ui/date-picker'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Loader2 } from 'lucide-react'

const PAGE_LIMIT = 100

export function CombinedResultsPage() {
  const [symbol, setSymbol] = useState('')
  const [startDate, setStartDate] = useState<Date | undefined>(() => subDays(new Date(), 7))
  const [endDate, setEndDate] = useState<Date | undefined>(() => new Date())
  const [offset, setOffset] = useState(0)

  const resultsQuery = useQuery({
    queryKey: ['combined-results', symbol, startDate?.toISOString(), endDate?.toISOString(), offset],
    queryFn: () =>
      combinedResultsApi.list({
        symbol: symbol ? symbol.trim().toUpperCase() : undefined,
        startDate: startDate ? format(startDate, 'yyyy-MM-dd') : undefined,
        endDate: endDate ? format(endDate, 'yyyy-MM-dd') : undefined,
        offset,
        limit: PAGE_LIMIT,
      }),
  })

  const canPrev = offset > 0
  const canNext = Boolean(resultsQuery.data && offset + PAGE_LIMIT < resultsQuery.data.totalCount)

  const toDisplayString = (value: unknown): string | undefined => {
    if (typeof value === 'string') return value
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    return undefined
  }

  const extractMetric = (metrics: Record<string, unknown>, key: string): number | undefined => {
    const stats = metrics?.statistics as Record<string, unknown> | undefined
    const value = stats?.[key] ?? metrics[key]
    if (typeof value === 'number') return value
    if (typeof value === 'string') {
      const numeric = Number(value)
      if (!Number.isNaN(numeric)) return numeric
    }
    return undefined
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Combined Screener / Backtest Results</CardTitle>
          <CardDescription>
            Inspect enriched records that join screener filters to completed backtests.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Symbol</Label>
              <Input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="AAPL" />
            </div>
            <div className="space-y-2">
              <Label>Start Date</Label>
              <DatePicker date={startDate} onDateChange={setStartDate} />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <DatePicker date={endDate} onDateChange={setEndDate} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setOffset(0)
                resultsQuery.refetch()
              }}
              disabled={resultsQuery.isFetching}
            >
              Apply Filters
            </Button>
            {resultsQuery.isFetching && <Loader2 className="h-4 w-4 animate-spin" />}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
          <CardDescription>Rows include both screener configuration and backtest performance.</CardDescription>
        </CardHeader>
        <CardContent>
          {resultsQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading combined results...
            </div>
          ) : resultsQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription>Unable to load combined results.</AlertDescription>
            </Alert>
          ) : resultsQuery.data?.results.length ? (
            <div className="space-y-3">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Symbol</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>Strategy</TableHead>
                      <TableHead>Total Return</TableHead>
                      <TableHead>Sharpe</TableHead>
                      <TableHead>Win Rate</TableHead>
                      <TableHead>Pivot Bars</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {resultsQuery.data.results.map((row: CombinedRow) => {
                      const metrics = row.backtestMetrics ?? {}
                      const totalReturn = extractMetric(metrics, 'total_return')
                      const sharpe = extractMetric(metrics, 'sharpe_ratio')
                      const winRate = extractMetric(metrics, 'win_rate')
                      const metadataSource = toDisplayString(row.screenerMetadata['source'])
                        ?? toDisplayString(row.screenerMetadata['dataset_source'])
                      const pivotBarsRaw = row.backtestParameters['pivot_bars']
                      const pivotBars = typeof pivotBarsRaw === 'number' ? pivotBarsRaw : undefined
                      return (
                        <TableRow key={`${row.symbol}-${row.screenerResultId}`}>
                          <TableCell>{format(new Date(row.screenerCreatedAt), 'yyyy-MM-dd')}</TableCell>
                          <TableCell>{row.symbol}</TableCell>
                          <TableCell className="capitalize">{metadataSource ?? '—'}</TableCell>
                          <TableCell>{row.strategyName ?? '—'}</TableCell>
                          <TableCell>{totalReturn !== undefined ? `${totalReturn.toFixed(2)}%` : '—'}</TableCell>
                          <TableCell>{sharpe !== undefined ? sharpe.toFixed(2) : '—'}</TableCell>
                          <TableCell>{winRate !== undefined ? `${winRate.toFixed(2)}%` : '—'}</TableCell>
                          <TableCell>{pivotBars ?? '—'}</TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>
                  Showing {offset + 1} – {Math.min(offset + PAGE_LIMIT, resultsQuery.data.totalCount)} of {resultsQuery.data.totalCount}
                </span>
                <div className="space-x-2">
                  <Button variant="outline" size="sm" disabled={!canPrev} onClick={() => setOffset((value) => Math.max(0, value - PAGE_LIMIT))}>
                    Previous
                  </Button>
                  <Button variant="outline" size="sm" disabled={!canNext} onClick={() => setOffset((value) => value + PAGE_LIMIT)}>
                    Next
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No records match the selected filters.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
