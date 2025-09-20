import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { formatISO, subDays } from 'date-fns'

import { registryApi, backtestApi } from '@/services/api'
import type { BacktestRunInfo } from '@/types/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { DatePicker } from '@/components/ui/date-picker'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Loader2 } from 'lucide-react'

type ParameterState = {
  enabled: boolean
  min: number
  max: number
  step: number
}

const formatMetrics = (run: BacktestRunInfo) => {
  if (!run.metrics) return '—'
  const entries = Object.entries(run.metrics)
    .filter(([, value]) => typeof value === 'number' && Number.isFinite(value))
    .sort(([, a], [, b]) => (b as number) - (a as number))
    .slice(0, 3)
  if (entries.length === 0) return '—'
  return entries
    .map(([key, value]) => `${key}: ${(value as number).toFixed(2)}`)
    .join(', ')
}

export function OptimizerPage() {
  const registryQuery = useQuery({ queryKey: ['registry'], queryFn: registryApi.fetch })
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

  const defaultStrategy = registryQuery.data?.strategies[0]
  const [strategyId, setStrategyId] = useState<string | undefined>(defaultStrategy?.id)
  const [initialCash, setInitialCash] = useState(100_000)
  const [useScreenerResults, setUseScreenerResults] = useState(true)
  const [resolution, setResolution] = useState<'Minute' | 'Hour' | 'Daily'>('Minute')
  const [startDate, setStartDate] = useState(() => subDays(new Date(), 90))
  const [endDate, setEndDate] = useState(() => new Date())
  const [pivotBars, setPivotBars] = useState(5)
  const [lowerTimeframe, setLowerTimeframe] = useState('5min')
  const [targetMetric, setTargetMetric] = useState('SharpeRatio')
  const [targetDirection, setTargetDirection] = useState<'maximize' | 'minimize'>('maximize')
  const [maxConcurrent, setMaxConcurrent] = useState<number | undefined>(4)
  const [parameterState, setParameterState] = useState<Record<string, ParameterState>>({})
  const [formError, setFormError] = useState<string | null>(null)

  const strategies = registryQuery.data?.strategies ?? []
  const selectedStrategy = useMemo(
    () => strategies.find((strategy) => strategy.id === strategyId) ?? defaultStrategy,
    [strategies, strategyId, defaultStrategy],
  )

  useEffect(() => {
    if (!selectedStrategy) return

    const parseNumber = (value: unknown, fallback: number) => {
      const parsed = Number(value)
      return Number.isFinite(parsed) ? parsed : fallback
    }

    setInitialCash(parseNumber(selectedStrategy.defaults.cash, 100_000))
    setPivotBars(parseNumber(selectedStrategy.defaults.pivot_bars, 5))
    setLowerTimeframe(String(selectedStrategy.defaults.lower_timeframe ?? '5min'))
    setResolution((selectedStrategy.defaults.resolution as typeof resolution) ?? 'Minute')

    const nextState: Record<string, ParameterState> = {}
    selectedStrategy.parameters.forEach((parameter) => {
      const base = parseNumber(parameter.defaultValue, 0)
      const minValue = parseNumber(parameter.minValue, base)
      const maxValue = parseNumber(parameter.maxValue, base)
      const step = parseNumber(parameter.step, 1) || 1
      nextState[parameter.name] = {
        enabled: false,
        min: minValue,
        max: maxValue,
        step,
      }
    })
    setParameterState(nextState)
  }, [selectedStrategy])

  const optimizeRuns = useMemo(() => {
    if (!runsQuery.data) return []
    return runsQuery.data.runs.filter((run) => run.jobType === 'optimize')
  }, [runsQuery.data])

  const optimizeSummary = summaryQuery.data?.jobTypes.find((item) => item.jobType === 'optimize')
  const optimizeMetrics = summaryQuery.data?.metrics.filter((item) => item.jobType === 'optimize') ?? []
  const optimizeTargets = summaryQuery.data?.targets.find((item) => item.jobType === 'optimize')

  const startOptimizeMutation = useMutation({
    mutationFn: backtestApi.startOptimize,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-runs'] })
    },
  })

  const handleParameterToggle = (name: string, enabled: boolean) => {
    setParameterState((prev) => ({
      ...prev,
      [name]: {
        ...(prev[name] ?? { enabled: false, min: 0, max: 0, step: 1 }),
        enabled,
      },
    }))
  }

  const handleParameterValue = (name: string, field: keyof ParameterState, value: number) => {
    setParameterState((prev) => ({
      ...prev,
      [name]: {
        ...(prev[name] ?? { enabled: false, min: 0, max: 0, step: 1 }),
        [field]: value,
      },
    }))
  }

  const handleSubmit = () => {
    if (!selectedStrategy) {
      setFormError('Select a strategy before running optimization.')
      return
    }

    if (!startDate || !endDate || startDate > endDate) {
      setFormError('Provide a valid start/end date range.')
      return
    }

    let parameters: Array<{ name: string; min: number; max: number; step: number }>
    try {
      parameters = Object.entries(parameterState)
        .filter(([, state]) => state.enabled)
        .map(([name, state]) => {
          if (state.max < state.min) {
            throw new Error(`Max must be greater than min for ${name}`)
          }
          return {
            name,
            min: state.min,
            max: state.max,
            step: state.step,
          }
        })
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Invalid parameter range')
      return
    }

    if (parameters.length === 0) {
      setFormError('Enable at least one parameter to optimize.')
      return
    }

    let baseRequestDefaults = { ...selectedStrategy.defaults }
    delete baseRequestDefaults.pivot_bars
    delete baseRequestDefaults.lower_timeframe
    delete baseRequestDefaults.resolution

    parameters.forEach((parameter) => {
      delete baseRequestDefaults[parameter.name]
    })

    setFormError(null)

    startOptimizeMutation.mutate({
      baseRequest: {
        strategyName: selectedStrategy.id,
        startDate: formatISO(startDate, { representation: 'date' }),
        endDate: formatISO(endDate, { representation: 'date' }),
        initialCash,
        resolution,
        pivotBars,
        lowerTimeframe,
        symbols: [],
        useScreenerResults,
        parameters: baseRequestDefaults,
      },
      targetMetric,
      targetDirection,
      parameters,
      maxConcurrentBacktests: maxConcurrent,
    })
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Optimization Summary</CardTitle>
          <CardDescription>Best performing optimization runs and counts.</CardDescription>
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
                <p className="text-xl font-semibold">{optimizeSummary?.totalRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Completed</p>
                <p className="text-xl font-semibold">{optimizeSummary?.completedRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Failed</p>
                <p className="text-xl font-semibold">{optimizeSummary?.failedRuns ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Top Metric</p>
                <p className="text-sm font-medium">
                  {optimizeMetrics.length > 0
                    ? `${optimizeMetrics[0].metricKey}: ${optimizeMetrics[0].metricValue.toFixed(2)}`
                    : '—'}
                </p>
                <p className="text-xs text-muted-foreground">
                  Targets: {optimizeTargets?.targetCount ?? 0}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Launch Optimization</CardTitle>
          <CardDescription>
            Configure the base request and ranges for numeric parameters to let Lean CLI search
            for the best configuration.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Strategy</Label>
              <Select value={selectedStrategy?.id} onValueChange={(value) => setStrategyId(value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select strategy" />
                </SelectTrigger>
                <SelectContent>
                  {strategies.map((strategy) => (
                    <SelectItem key={strategy.id} value={strategy.id}>
                      {strategy.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Initial Cash</Label>
              <Input
                type="number"
                min={1000}
                step={1000}
                value={initialCash}
                onChange={(event) => setInitialCash(Number(event.target.value))}
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <DatePicker date={startDate} onDateChange={(value) => setStartDate(value ?? subDays(new Date(), 90))} />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <DatePicker date={endDate} onDateChange={(value) => setEndDate(value ?? new Date())} />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Pivot Bars</Label>
              <Input
                type="number"
                min={1}
                step={1}
                value={pivotBars}
                onChange={(event) => setPivotBars(Number(event.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label>Lower Timeframe</Label>
              <Input value={lowerTimeframe} onChange={(event) => setLowerTimeframe(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Resolution</Label>
              <Select value={resolution} onValueChange={(value) => setResolution(value as typeof resolution)}>
                <SelectTrigger>
                  <SelectValue placeholder="Resolution" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Minute">Minute</SelectItem>
                  <SelectItem value="Hour">Hour</SelectItem>
                  <SelectItem value="Daily">Daily</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="targetMetric">Target Metric</Label>
              <Input
                id="targetMetric"
                value={targetMetric}
                onChange={(event) => setTargetMetric(event.target.value)}
                placeholder="SharpeRatio"
              />
            </div>
            <div className="space-y-2">
              <Label>Direction</Label>
              <Select value={targetDirection} onValueChange={(value) => setTargetDirection(value as typeof targetDirection)}>
                <SelectTrigger>
                  <SelectValue placeholder="Direction" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="maximize">Maximize</SelectItem>
                  <SelectItem value="minimize">Minimize</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Max Concurrent Backtests</Label>
              <Input
                type="number"
                min={1}
                value={maxConcurrent ?? ''}
                onChange={(event) => {
                  const value = Number(event.target.value)
                  setMaxConcurrent(Number.isNaN(value) ? undefined : value)
                }}
                placeholder="Auto"
              />
            </div>
            <div className="space-y-2">
              <Label className="flex items-center justify-between">
                Use latest screener symbols
                <Switch checked={useScreenerResults} onCheckedChange={(checked) => setUseScreenerResults(checked)} />
              </Label>
            </div>
          </div>

          <div className="space-y-3">
            <Label>Parameters</Label>
            <div className="space-y-3">
              {selectedStrategy?.parameters.map((parameter) => {
                const state = parameterState[parameter.name]
                const isNumeric = parameter.controlType === 'number'

                return (
                  <div key={parameter.name} className="rounded-md border p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">{parameter.label}</p>
                        {parameter.description && (
                          <p className="text-xs text-muted-foreground">{parameter.description}</p>
                        )}
                      </div>
                      {isNumeric ? (
                        <Switch
                          checked={state?.enabled ?? false}
                          onCheckedChange={(checked) => handleParameterToggle(parameter.name, checked)}
                        />
                      ) : (
                        <span className="text-xs text-muted-foreground">Non-numeric</span>
                      )}
                    </div>

                    {isNumeric && state?.enabled && (
                      <div className="mt-3 grid gap-3 md:grid-cols-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Min</Label>
                          <Input
                            type="number"
                            value={state.min}
                            onChange={(event) => handleParameterValue(parameter.name, 'min', Number(event.target.value))}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Max</Label>
                          <Input
                            type="number"
                            value={state.max}
                            onChange={(event) => handleParameterValue(parameter.name, 'max', Number(event.target.value))}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Step</Label>
                          <Input
                            type="number"
                            value={state.step}
                            min={0.0001}
                            step={0.1}
                            onChange={(event) => handleParameterValue(parameter.name, 'step', Number(event.target.value))}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {formError && (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}

          <Button onClick={handleSubmit} disabled={startOptimizeMutation.isPending}>
            {startOptimizeMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Run Optimization
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Optimization Jobs</CardTitle>
          <CardDescription>Live view of Lean optimize jobs handled by the shared service.</CardDescription>
        </CardHeader>
        <CardContent>
          {runsQuery.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading run history...
            </div>
          ) : runsQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription>Unable to load optimization runs right now.</AlertDescription>
            </Alert>
          ) : optimizeRuns.length === 0 ? (
            <p className="text-sm text-muted-foreground">No optimization jobs have been submitted yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Metrics</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {optimizeRuns.map((run: BacktestRunInfo) => (
                    <TableRow key={run.backtestId}>
                      <TableCell className="font-mono text-xs">{run.backtestId.slice(0, 8)}</TableCell>
                      <TableCell className="capitalize">{run.status}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{formatMetrics(run)}</TableCell>
                      <TableCell>{run.request.strategyName}</TableCell>
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
