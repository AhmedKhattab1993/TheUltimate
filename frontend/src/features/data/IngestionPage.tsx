import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { formatISO, subDays } from 'date-fns'

import { dataApi, backtestApi } from '@/services/api'
import type { BacktestRunInfo } from '@/types/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { DatePicker } from '@/components/ui/date-picker'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Loader2 } from 'lucide-react'

export function IngestionPage() {
  const queryClient = useQueryClient()
  const runsQuery = useQuery({
    queryKey: ['backtest-runs'],
    queryFn: () => backtestApi.listRuns({ page: 1, pageSize: 100 }),
    refetchInterval: 5000,
  })
  const summaryQuery = useQuery({
    queryKey: ['run-summary'],
    queryFn: backtestApi.summary,
    refetchInterval: 10000,
  })

  const [startDate, setStartDate] = useState(() => subDays(new Date(), 7))
  const [endDate, setEndDate] = useState(() => new Date())
  const [resume, setResume] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const ingestionRuns = runsQuery.data?.runs.filter((run) => run.jobType === 'data') ?? []
  const dataSummary = summaryQuery.data?.jobTypes.find((item) => item.jobType === 'data')
  const dataTargets = summaryQuery.data?.targets.find((item) => item.jobType === 'data')

  const ingestMutation = useMutation({
    mutationFn: dataApi.ingest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-runs'] })
    },
  })

  const handleSubmit = () => {
    if (!startDate || !endDate || startDate > endDate) {
      setFormError('Provide a valid start/end date range.')
      return
    }

    setFormError(null)

    ingestMutation.mutate({
      dataset: 'minute',
      startDate: formatISO(startDate, { representation: 'date' }),
      endDate: formatISO(endDate, { representation: 'date' }),
      resume,
    })
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Ingestion Summary</CardTitle>
          <CardDescription>Track historical data downloads at a glance.</CardDescription>
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
                <p className="text-xs text-muted-foreground">Total Jobs</p>
                <p className="text-xl font-semibold">{dataSummary?.totalRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Completed</p>
                <p className="text-xl font-semibold">{dataSummary?.completedRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Failed</p>
                <p className="text-xl font-semibold">{dataSummary?.failedRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Targets Processed</p>
                <p className="text-xl font-semibold">{dataTargets?.targetCount ?? 0}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Download Historical Minute Data</CardTitle>
          <CardDescription>
            Submit a background job that uses the existing ingestion pipeline to backfill Polygon minute data.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <DatePicker date={startDate} onDateChange={(value) => setStartDate(value ?? subDays(new Date(), 7))} />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <DatePicker date={endDate} onDateChange={(value) => setEndDate(value ?? new Date())} />
            </div>
          </div>

          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <Label htmlFor="resume" className="font-medium">
                Resume from checkpoint
              </Label>
              <p className="text-xs text-muted-foreground">
                Continue from the last saved position instead of restarting the download.
              </p>
            </div>
            <Switch id="resume" checked={resume} onCheckedChange={setResume} />
          </div>

          {formError && (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}

          <Button onClick={handleSubmit} disabled={ingestMutation.isPending}>
            {ingestMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Start Ingestion
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Ingestion Jobs</CardTitle>
          <CardDescription>Monitor the latest dataset downloads triggered through the pipeline.</CardDescription>
        </CardHeader>
        <CardContent>
          {runsQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading run history...
            </div>
          ) : runsQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription>Unable to load ingestion jobs right now.</AlertDescription>
            </Alert>
          ) : ingestionRuns.length === 0 ? (
            <p className="text-sm text-muted-foreground">No ingestion jobs have been submitted yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Window</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ingestionRuns.map((run: BacktestRunInfo) => (
                    <TableRow key={run.backtestId}>
                      <TableCell className="font-mono text-xs">{run.backtestId.slice(0, 8)}</TableCell>
                      <TableCell className="capitalize">{run.status}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {run.request.startDate} → {run.request.endDate}
                      </TableCell>
                      <TableCell>{run.createdAt ? new Date(run.createdAt).toLocaleString() : '—'}</TableCell>
                      <TableCell>
                        {run.completedAt ? new Date(run.completedAt).toLocaleString() : 'Pending'}
                      </TableCell>
                      <TableCell className="text-xs text-destructive">
                        {run.errorMessage ?? '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
