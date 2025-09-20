import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { backtestApi, registryApi } from '@/services/api'
import type { BacktestRunInfo } from '@/types/api'
import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Loader2 } from 'lucide-react'
import { TableSkeleton } from '@/components/LoadingSkeleton'

function formatDate(value?: string | null) {
  if (!value) return '—'
  return format(new Date(value), 'yyyy-MM-dd HH:mm')
}

function formatMetrics(run: BacktestRunInfo): string {
  if (!run.metrics) return '—'
  const entries = Object.entries(run.metrics)
    .filter(([, value]) => typeof value === 'number' && Number.isFinite(value))
    .slice(0, 3)
  if (entries.length === 0) return '—'
  return entries
    .map(([key, value]) => `${key}: ${(value as number).toFixed(2)}`)
    .join(', ')
}

export function BacktestsPage() {
  const queryClient = useQueryClient()
  const registryQuery = useQuery({ queryKey: ['registry'], queryFn: registryApi.fetch })
  const runsQuery = useQuery({
    queryKey: ['backtest-runs'],
    queryFn: () => backtestApi.listRuns({ page: 1, pageSize: 50 }),
    refetchInterval: 5000,
  })
  const summaryQuery = useQuery({
    queryKey: ['run-summary'],
    queryFn: backtestApi.summary,
    refetchInterval: 10000,
  })

  const backtestSummary = summaryQuery.data?.jobTypes.find((item) => item.jobType === 'backtest')
  const backtestTargets = summaryQuery.data?.targets.find((item) => item.jobType === 'backtest')
  const bestBacktestMetric = summaryQuery.data?.metrics.find((item) => item.jobType === 'backtest')

  const runMutation = useMutation({
    mutationFn: backtestApi.start,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-runs'] })
    },
  })

  const [detailsOpen, setDetailsOpen] = useState(false)
  const runDetailsMutation = useMutation({
    mutationFn: backtestApi.getRun,
  })

  const defaultStrategy = registryQuery.data?.strategies[0]

  const handleStartBacktest = () => {
    if (!defaultStrategy) return
    runMutation.mutate({
      strategyName: defaultStrategy.id,
      startDate: format(new Date(), 'yyyy-MM-dd'),
      endDate: format(new Date(), 'yyyy-MM-dd'),
      initialCash: 100_000,
      resolution: 'Minute',
      pivotBars: Number(defaultStrategy.defaults.pivot_bars ?? 5),
      lowerTimeframe: String(defaultStrategy.defaults.lower_timeframe ?? '5min'),
      symbols: [],
      useScreenerResults: true,
      parameters: defaultStrategy.defaults,
    })
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Backtest Summary</CardTitle>
          <CardDescription>Recent activity and best metrics across all jobs.</CardDescription>
        </CardHeader>
        <CardContent>
          {summaryQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading summary...
            </div>
          ) : summaryQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription>Unable to load summary.</AlertDescription>
            </Alert>
          ) : (
            <div className="grid gap-4 md:grid-cols-4">
              <div>
                <p className="text-xs text-muted-foreground">Total Runs</p>
                <p className="text-xl font-semibold">{backtestSummary?.totalRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Completed</p>
                <p className="text-xl font-semibold">{backtestSummary?.completedRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Failed</p>
                <p className="text-xl font-semibold">{backtestSummary?.failedRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Best Metric</p>
                <p className="text-sm font-medium">
                  {bestBacktestMetric
                    ? `${bestBacktestMetric.metricKey}: ${bestBacktestMetric.metricValue.toFixed(2)}`
                    : '—'}
                </p>
                <p className="text-xs text-muted-foreground">
                  Targets: {backtestTargets?.targetCount ?? 0}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Backtest Runs</CardTitle>
            <CardDescription>Monitor submitted Lean jobs and launch new ones.</CardDescription>
          </div>
          <Button onClick={handleStartBacktest} disabled={!defaultStrategy || runMutation.isPending}>
            {runMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Run Default Strategy
          </Button>
        </CardHeader>
        <CardContent>
          {runsQuery.isLoading ? (
            <TableSkeleton />
          ) : runsQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription>Failed to load backtest runs.</AlertDescription>
            </Alert>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                  <TableHead>Job</TableHead>
                  <TableHead>Job</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Metrics</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                  {runsQuery.data?.runs.map((run: BacktestRunInfo) => (
                    <TableRow key={run.backtestId}>
                      <TableCell className="font-mono text-xs">{run.backtestId.slice(0, 8)}</TableCell>
                      <TableCell className="capitalize">{run.jobType}</TableCell>
                      <TableCell className="capitalize">{run.jobType}</TableCell>
                      <TableCell>{run.request.strategyName}</TableCell>
                      <TableCell className="capitalize">{run.status}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{formatMetrics(run)}</TableCell>
                      <TableCell>{formatDate(run.createdAt)}</TableCell>
                      <TableCell>{formatDate(run.startedAt)}</TableCell>
                      <TableCell>{formatDate(run.completedAt)}</TableCell>
                      <TableCell className="text-xs text-destructive">
                        {run.errorMessage ?? '—'}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setDetailsOpen(true)
                            runDetailsMutation.mutate(run.backtestId)
                          }}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Run Details</DialogTitle>
            <DialogDescription>Metrics and targets for the selected job.</DialogDescription>
          </DialogHeader>
          {runDetailsMutation.isPending ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading...
            </div>
          ) : runDetailsMutation.isError ? (
            <Alert variant="destructive">
              <AlertDescription>Unable to load run details.</AlertDescription>
            </Alert>
          ) : runDetailsMutation.data ? (
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Run ID</p>
                <p className="font-mono text-xs">{runDetailsMutation.data.backtestId}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Metrics</p>
                <ul className="space-y-1">
                  {runDetailsMutation.data.metrics
                    ? Object.entries(runDetailsMutation.data.metrics).map(([key, value]) => (
                        <li key={key} className="flex items-center justify-between">
                          <span>{key}</span>
                          <span>{(value as number).toFixed(4)}</span>
                        </li>
                      ))
                    : <li className="text-muted-foreground">No metrics recorded</li>}
                </ul>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Targets</p>
                <p>{runDetailsMutation.data.targets?.join(', ') || '—'}</p>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
