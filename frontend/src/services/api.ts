import axios from 'axios'
import type {
  BacktestRequestPayload,
  BacktestRunInfo,
  BacktestRunListResponse,
  CombinedResultsResponse,
  CombinedRow,
  DataIngestionRequestPayload,
  FilterControl,
  FilterDefinition,
  FilterOption,
  FilterStateMap,
  GridBacktestRequestPayload,
  GridResultsListResponse,
  GridRunDetail,
  GridRunResult,
  GridRunSummary,
  JobTypeSummary,
  MetricSummary,
  OptimizeRequestPayload,
  RegistryResponse,
  RunSummaryResponse,
  ScreenerRequestPayload,
  ScreenerResponse,
  ScreenerResultDetail,
  ScreenerResultsListResponse,
  StrategyDefinition,
  StrategyParameter,
  TargetSummary,
} from '@/types/api'
import type {
  EnhancedScreenerRequest,
  EnhancedScreenerResponse,
  SimpleFilters,
} from '@/types/screener'

type RawFilterOption = {
  label: string
  value: string | number
  description?: string
}

type RawFilterControl = {
  control_type: string
  field: string
  label: string
  description?: string
  default?: string | number | boolean
  min_value?: number
  max_value?: number
  step?: number
  options?: RawFilterOption[]
  unit?: string
  placeholder?: string
  required?: boolean
}

type RawFilterDefinition = {
  id: string
  backend_key: string
  label: string
  category: string
  description: string
  default_enabled: boolean
  controls: RawFilterControl[]
  tags?: string[]
  sort_order?: number
  doc_url?: string | null
}

type RawStrategyParameter = {
  name: string
  label: string
  description?: string
  control_type: string
  default?: string | number | boolean
  min_value?: number
  max_value?: number
  step?: number
  options?: RawFilterOption[]
  required?: boolean
}

type RawStrategyDefinition = {
  id: string
  label: string
  description: string
  project_path: string
  parameters: RawStrategyParameter[]
  defaults: Record<string, string | number | boolean>
  capabilities: {
    supports: Array<'backtest' | 'grid' | 'optimize'>
    default_job_type: 'backtest' | 'grid' | 'optimize'
    parallelism?: number | null
  }
  documentation_url?: string | null
  notes?: string | null
}

type RawRegistryResponse = {
  filters: RawFilterDefinition[]
  strategies: RawStrategyDefinition[]
}

type RawScreenerResponse = {
  execution_time_ms: number
  total_symbols_screened: number
  total_qualifying_stocks: number
  results: Array<{
    symbol: string
    qualifying_dates: string[]
    total_days_analyzed: number
    qualifying_days_count: number
    metrics: Record<string, number | string | null>
  }>
}

type RawScreenerResultSummary = {
  id: string
  timestamp: string
  symbol_count: number
  filters: Record<string, unknown>
  execution_time_ms: number
  total_symbols_screened: number
}

type RawScreenerResultDetail = {
  id: string
  timestamp: string
  symbol_count: number
  filters: Record<string, unknown>
  metadata: Record<string, unknown>
  symbols: Array<{
    symbol: string
    latest_price?: number
    latest_volume?: number
  }>
}

type RawScreenerResultsListResponse = {
  results: RawScreenerResultSummary[]
  total_count: number
  page: number
  page_size: number
}

type RawBacktestRunInfo = {
  backtest_id: string
  status: string
  job_type: string
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  error_message?: string | null
  result_path?: string | null
  metrics?: Record<string, number>
  targets?: string[]
  request: {
    strategy_name: string
    start_date: string
    end_date: string
    initial_cash: number
    resolution: BacktestRequestPayload['resolution']
    pivot_bars: number
    lower_timeframe: string
    symbols?: string[]
    use_screener_results?: boolean
    parameters?: Record<string, string | number | boolean>
  }
}

type RawBacktestListResponse = {
  runs: RawBacktestRunInfo[]
  total_count: number
  page: number
  page_size: number
}

type RawOptimizationRequest = {
  base_request: ReturnType<typeof toBacktestPayload>
  target_metric: string
  target_direction: 'maximize' | 'minimize'
  parameters: Array<{ name: string; min: number; max: number; step: number }>
  max_concurrent_backtests?: number
}

type RawGridRunSummary = {
  run_id: string
  strategy_name: string
  status: string
  job_type: string
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  duration_ms?: number | null
  target_count: number
  metrics: Record<string, number | string | null>
  metadata: Record<string, unknown>
}

type RawGridResultsListResponse = {
  results: RawGridRunSummary[]
  total_count: number
  page: number
  page_size: number
}

type RawGridRunResult = {
  symbol?: string | null
  status: string
  created_at: string
  parameters: Record<string, unknown>
  metrics: Record<string, unknown>
}

type RawGridRunDetail = RawGridRunSummary & {
  results: RawGridRunResult[]
}

type RawCombinedResultsResponse = {
  results: Array<Record<string, any>>
  total_count: number
  limit: number
  offset: number
}

type RawJobTypeSummary = {
  job_type: string
  total_runs: number
  completed_runs: number
  failed_runs: number
  last_run_id?: string | null
  last_run_at?: string | null
}

type RawMetricSummary = {
  job_type: string
  metric_key: string
  metric_value: number
  run_id: string
  strategy_name: string
  created_at: string
}

type RawTargetSummary = {
  job_type: string
  target_count: number
}

type RawRunSummaryResponse = {
  job_types: RawJobTypeSummary[]
  metrics: RawMetricSummary[]
  targets: RawTargetSummary[]
}

const mapOption = (option: RawFilterOption): FilterOption => ({
  label: option.label,
  value: option.value,
  description: option.description,
})

const mapControl = (control: RawFilterControl): FilterControl => ({
  controlType: control.control_type as FilterControl['controlType'],
  field: control.field,
  label: control.label,
  description: control.description,
  defaultValue: control.default,
  minValue: control.min_value,
  maxValue: control.max_value,
  step: control.step,
  options: control.options?.map(mapOption),
  unit: control.unit,
  placeholder: control.placeholder,
  required: control.required,
})

const mapFilterDefinition = (definition: RawFilterDefinition): FilterDefinition => ({
  id: definition.id,
  backendKey: definition.backend_key,
  label: definition.label,
  category: definition.category as FilterDefinition['category'],
  description: definition.description,
  defaultEnabled: definition.default_enabled,
  controls: definition.controls.map(mapControl),
  tags: definition.tags ?? [],
  sortOrder: definition.sort_order ?? 0,
  docUrl: definition.doc_url ?? undefined,
})

const mapStrategyParameter = (parameter: RawStrategyParameter): StrategyParameter => ({
  name: parameter.name,
  label: parameter.label,
  description: parameter.description,
  controlType: parameter.control_type as StrategyParameter['controlType'],
  defaultValue: parameter.default,
  minValue: parameter.min_value,
  maxValue: parameter.max_value,
  step: parameter.step,
  options: parameter.options?.map(mapOption),
  required: parameter.required,
})

const mapStrategyDefinition = (definition: RawStrategyDefinition): StrategyDefinition => ({
  id: definition.id,
  label: definition.label,
  description: definition.description,
  projectPath: definition.project_path,
  parameters: definition.parameters.map(mapStrategyParameter),
  defaults: definition.defaults,
  capabilities: {
    supports: definition.capabilities.supports,
    defaultJobType: definition.capabilities.default_job_type,
    parallelism: definition.capabilities.parallelism ?? undefined,
  },
  documentationUrl: definition.documentation_url ?? undefined,
  notes: definition.notes ?? undefined,
})

const mapBacktestRequest = (
  request: RawBacktestRunInfo['request'],
): BacktestRequestPayload => ({
  strategyName: request.strategy_name,
  startDate: request.start_date,
  endDate: request.end_date,
  initialCash: Number(request.initial_cash),
  resolution: request.resolution,
  pivotBars: request.pivot_bars,
  lowerTimeframe: request.lower_timeframe,
  symbols: request.symbols,
  useScreenerResults: request.use_screener_results,
  parameters: request.parameters,
})

const mapBacktestRun = (run: RawBacktestRunInfo): BacktestRunInfo => ({
  backtestId: run.backtest_id,
  status: run.status,
  jobType: run.job_type,
  createdAt: run.created_at,
  startedAt: run.started_at ?? undefined,
  completedAt: run.completed_at ?? undefined,
  errorMessage: run.error_message ?? undefined,
  resultPath: run.result_path ?? undefined,
  request: mapBacktestRequest(run.request),
  metrics: run.metrics ?? undefined,
  targets: run.targets ?? undefined,
})

const mapJobTypeSummary = (summary: RawJobTypeSummary): JobTypeSummary => ({
  jobType: summary.job_type,
  totalRuns: summary.total_runs,
  completedRuns: summary.completed_runs,
  failedRuns: summary.failed_runs,
  lastRunId: summary.last_run_id ?? undefined,
  lastRunAt: summary.last_run_at ?? undefined,
})

const mapMetricSummary = (summary: RawMetricSummary): MetricSummary => ({
  jobType: summary.job_type,
  metricKey: summary.metric_key,
  metricValue: summary.metric_value,
  runId: summary.run_id,
  strategyName: summary.strategy_name,
  createdAt: summary.created_at,
})

const mapTargetSummary = (summary: RawTargetSummary): TargetSummary => ({
  jobType: summary.job_type,
  targetCount: summary.target_count,
})

const mapRunSummary = (data: RawRunSummaryResponse): RunSummaryResponse => ({
  jobTypes: data.job_types.map(mapJobTypeSummary),
  metrics: data.metrics.map(mapMetricSummary),
  targets: data.targets.map(mapTargetSummary),
})

const mapGridSummary = (summary: RawGridRunSummary): GridRunSummary => ({
  runId: summary.run_id,
  strategyName: summary.strategy_name,
  status: summary.status,
  jobType: summary.job_type,
  createdAt: summary.created_at,
  startedAt: summary.started_at ?? undefined,
  completedAt: summary.completed_at ?? undefined,
  durationMs: summary.duration_ms ?? undefined,
  targetCount: summary.target_count,
  metrics: Object.entries(summary.metrics ?? {}).reduce<Record<string, number>>((acc, [key, value]) => {
    const numeric = Number(value)
    if (!Number.isNaN(numeric)) {
      acc[key] = numeric
    }
    return acc
  }, {}),
  metadata: summary.metadata ?? {},
})

const mapGridResult = (result: RawGridRunResult): GridRunResult => ({
  symbol: result.symbol ?? undefined,
  status: result.status,
  createdAt: result.created_at,
  parameters: result.parameters ?? {},
  metrics: result.metrics ?? {},
})

const mapGridDetail = (detail: RawGridRunDetail): GridRunDetail => ({
  ...mapGridSummary(detail),
  results: detail.results.map(mapGridResult),
})

const mapCombinedRow = (row: Record<string, any>): CombinedRow => ({
  screenerResultId: row.screener_result_id,
  screenerRunId: row.screener_run_id,
  symbol: row.symbol,
  screenerCreatedAt: row.screener_created_at,
  screenerMetrics: row.screener_metrics ?? {},
  filters: row.filters ?? {},
  screenerMetadata: row.screener_metadata ?? {},
  runId: row.run_id ?? undefined,
  runCreatedAt: row.run_created_at ?? undefined,
  runStatus: row.run_status ?? undefined,
  strategyName: row.strategy_name ?? undefined,
  backtestParameters: row.backtest_parameters ?? {},
  backtestMetrics: row.backtest_metrics ?? {},
})

const mapCombinedResponse = (data: RawCombinedResultsResponse): CombinedResultsResponse => ({
  results: data.results.map(mapCombinedRow),
  totalCount: data.total_count,
  limit: data.limit,
  offset: data.offset,
})

const mapScreenerResponse = (data: RawScreenerResponse): ScreenerResponse => ({
  executionTimeMs: data.execution_time_ms,
  totalSymbolsScreened: data.total_symbols_screened,
  totalQualifyingStocks: data.total_qualifying_stocks,
  results: data.results.map((row) => ({
    symbol: row.symbol,
    qualifyingDates: row.qualifying_dates,
    totalDaysAnalyzed: row.total_days_analyzed,
    qualifyingDaysCount: row.qualifying_days_count,
    metrics: row.metrics,
  })),
})

const mapScreenerSummary = (summary: RawScreenerResultSummary) => ({
  id: summary.id,
  timestamp: summary.timestamp,
  symbolCount: summary.symbol_count,
  filters: summary.filters ?? {},
  executionTimeMs: summary.execution_time_ms,
  totalSymbolsScreened: summary.total_symbols_screened,
})

const mapScreenerDetail = (detail: RawScreenerResultDetail): ScreenerResultDetail => ({
  id: detail.id,
  timestamp: detail.timestamp,
  symbolCount: detail.symbol_count,
  filters: detail.filters ?? {},
  metadata: detail.metadata ?? {},
  symbols: detail.symbols?.map((symbol) => ({
    symbol: symbol.symbol,
    latestPrice: symbol.latest_price,
    latestVolume: symbol.latest_volume,
  })) ?? [],
})

const mapRegistryResponse = (data: RawRegistryResponse): RegistryResponse => ({
  filters: data.filters.map(mapFilterDefinition),
  strategies: data.strategies.map(mapStrategyDefinition),
})

// -----------------------------------------------------------------------------
// Axios client configuration
// -----------------------------------------------------------------------------

export const getApiUrl = () => {
  const hostname = window.location.hostname

  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000'
  }

  return `http://${hostname}:8000`
}

const API_BASE_URL = getApiUrl()

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

type AxiosConfig = {
  params?: Record<string, string | number | boolean>
}

api.interceptors.request.use((config) => {
  const version = Date.now()
  const cfg: AxiosConfig = config
  cfg.params = { ...(cfg.params ?? {}), _v: version }
  return config
})

// -----------------------------------------------------------------------------
// Public API
// -----------------------------------------------------------------------------

export const registryApi = {
  fetch: async (): Promise<RegistryResponse> => {
    const response = await api.get<RawRegistryResponse>('/api/v2/registry/all')
    return mapRegistryResponse(response.data)
  },
}

const toScreenerPayload = (payload: ScreenerRequestPayload) => ({
  start_date: payload.startDate,
  end_date: payload.endDate,
  use_all_us_stocks: payload.useAllUsStocks ?? true,
  enable_db_prefiltering: payload.enableDbPrefiltering ?? true,
  filters: Object.entries(payload.filters).reduce<Record<string, unknown>>((acc, [key, state]) => {
    acc[key] = {
      enabled: state.enabled,
      values: state.values,
    }
    return acc
  }, {}),
})

const simpleFiltersToStateMap = (filters: SimpleFilters): FilterStateMap => {
  const map: FilterStateMap = {}

  const add = (id: string, values?: Record<string, string | number | boolean>) => {
    if (values && Object.keys(values).length > 0) {
      map[id] = { enabled: true, values }
    } else {
      map[id] = { enabled: false, values: {} }
    }
  }

  const priceRange = filters.simple_price_range
  add('simple_price_range', priceRange ? {
    min_price: priceRange.min_price,
    max_price: priceRange.max_price,
    step: priceRange.step,
  } : undefined)

  const priceVsMa = filters.price_vs_ma
  if (priceVsMa) {
    const maList = Array.isArray(priceVsMa) ? priceVsMa : [priceVsMa]
    const primary = maList[0]
    add('price_vs_ma', {
      ma_period: primary?.ma_period,
      min_ratio: primary?.min_ratio,
      max_ratio: primary?.max_ratio,
      step_ratio: primary?.step_ratio,
      setups: maList.map((entry) => ({
        ma_period: entry.ma_period,
        min_ratio: entry.min_ratio,
        max_ratio: entry.max_ratio,
        step_ratio: entry.step_ratio,
      })),
    })
  } else {
    add('price_vs_ma')
  }

  const rsi = filters.rsi
  if (rsi) {
    const rsiList = Array.isArray(rsi) ? rsi : [rsi]
    const primary = rsiList[0]
    add('rsi', {
      rsi_period: primary?.rsi_period,
      min_value: primary?.min_value,
      max_value: primary?.max_value,
      step_value: primary?.step_value,
      periods: rsiList.map((entry) => ({
        rsi_period: entry.rsi_period,
        min_value: entry.min_value,
        max_value: entry.max_value,
        step_value: entry.step_value,
      })),
    })
  } else {
    add('rsi')
  }

  const gap = filters.gap
  add('gap', gap ? {
    min_gap_percent: gap.min_gap_percent,
    max_gap_percent: gap.max_gap_percent,
    step_gap_percent: gap.step_gap_percent,
    direction: gap.direction,
  } : undefined)

  const prevDay = filters.prev_day_dollar_volume
  add('prev_day_dollar_volume', prevDay ? {
    min_dollar_volume: prevDay.min_dollar_volume,
    max_dollar_volume: prevDay.max_dollar_volume,
    step_dollar_volume: prevDay.step_dollar_volume,
  } : undefined)

  const relVolume = filters.relative_volume
  add('relative_volume', relVolume ? {
    recent_days: relVolume.recent_days,
    lookback_days: relVolume.lookback_days,
    min_ratio: relVolume.min_ratio,
    max_ratio: relVolume.max_ratio,
    step_ratio: relVolume.step_ratio,
  } : undefined)

  return map
}

const mapToEnhancedResponse = (
  response: ScreenerResponse,
): EnhancedScreenerResponse => ({
  request_date: new Date().toISOString(),
  total_symbols_screened: response.totalSymbolsScreened,
  total_qualifying_stocks: response.totalQualifyingStocks,
  execution_time_ms: response.executionTimeMs,
  results: response.results.map((row) => ({
    symbol: row.symbol,
    qualifying_dates: row.qualifyingDates,
    metrics: {
      latest_price: typeof row.metrics.avg_open_price === 'number' ? Number(row.metrics.avg_open_price) : undefined,
      latest_volume: typeof row.metrics.avg_volume === 'number' ? Number(row.metrics.avg_volume) : undefined,
      simple_price_range: true,
      price_vs_ma: typeof row.metrics.ma_20_mean === 'number'
        ? Number(row.metrics.ma_20_mean)
        : typeof row.metrics.ma_50_mean === 'number'
          ? Number(row.metrics.ma_50_mean)
          : typeof row.metrics.ma_200_mean === 'number'
            ? Number(row.metrics.ma_200_mean)
            : undefined,
      rsi: typeof row.metrics.rsi_mean === 'number' ? Number(row.metrics.rsi_mean) : undefined,
    },
  })),
  performance_metrics: {
    data_fetch_time_ms: 0,
    screening_time_ms: response.executionTimeMs,
    total_execution_time_ms: response.executionTimeMs,
    used_bulk_endpoint: false,
    symbols_fetched: response.totalSymbolsScreened,
    symbols_failed: 0,
  },
})

export const screenerApi = {
  run: async (payload: ScreenerRequestPayload): Promise<ScreenerResponse> => {
    const response = await api.post<RawScreenerResponse>(
      '/api/v2/simple-screener/screen',
      toScreenerPayload(payload),
    )
    return mapScreenerResponse(response.data)
  },
}

export const stockScreenerApi = {
  screenEnhanced: async (request: EnhancedScreenerRequest): Promise<EnhancedScreenerResponse> => {
    const payload: ScreenerRequestPayload = {
      startDate: request.start_date,
      endDate: request.end_date,
      useAllUsStocks: request.use_all_us_stocks,
      filters: simpleFiltersToStateMap(request.filters ?? {}),
      enableDbPrefiltering: true,
    }
    const response = await screenerApi.run(payload)
    return mapToEnhancedResponse(response)
  },
  getFilterInfo: async () => {
    const response = await api.get('/api/v2/simple-screener/filters/info')
    return response.data
  },
  getExamples: async () => {
    const response = await api.get('/api/v2/simple-screener/examples')
    return response.data
  },
}

const toBacktestPayload = (payload: BacktestRequestPayload) => ({
  strategy_name: payload.strategyName,
  start_date: payload.startDate,
  end_date: payload.endDate,
  initial_cash: payload.initialCash,
  resolution: payload.resolution,
  pivot_bars: payload.pivotBars,
  lower_timeframe: payload.lowerTimeframe,
  symbols: payload.symbols ?? [],
  use_screener_results: payload.useScreenerResults ?? false,
  parameters: payload.parameters ?? {},
})

const toOptimizePayload = (payload: OptimizeRequestPayload): RawOptimizationRequest => ({
  base_request: toBacktestPayload(payload.baseRequest),
  target_metric: payload.targetMetric,
  target_direction: payload.targetDirection,
  parameters: payload.parameters.map((parameter) => ({
    name: parameter.name,
    min: parameter.min,
    max: parameter.max,
    step: parameter.step,
  })),
  max_concurrent_backtests: payload.maxConcurrentBacktests,
})

const toDataPayload = (payload: DataIngestionRequestPayload) => ({
  dataset: payload.dataset,
  start_date: payload.startDate,
  end_date: payload.endDate,
  resume: payload.resume,
})

export const backtestApi = {
  start: async (payload: BacktestRequestPayload): Promise<BacktestRunInfo> => {
    const response = await api.post<RawBacktestRunInfo>(
      '/api/v2/backtest/run',
      toBacktestPayload(payload),
    )
    return mapBacktestRun(response.data)
  },
  startGrid: async (
    payload: GridBacktestRequestPayload,
  ): Promise<BacktestRunInfo[]> => {
    const response = await api.post<RawBacktestRunInfo[]>(
      '/api/v2/backtest/grid/run',
      {
        base_request: toBacktestPayload(payload.baseRequest),
        parameter_sweeps: payload.parameterSweeps,
      },
    )
    return response.data.map(mapBacktestRun)
  },
  startOptimize: async (payload: OptimizeRequestPayload): Promise<BacktestRunInfo> => {
    const response = await api.post<RawBacktestRunInfo>(
      '/api/v2/backtest/optimize/run',
      toOptimizePayload(payload),
    )
    return mapBacktestRun(response.data)
  },
  listRuns: async (params?: { page?: number; pageSize?: number; strategyName?: string }): Promise<BacktestRunListResponse> => {
    const response = await api.get<RawBacktestListResponse>('/api/v2/backtest/runs', {
      params: {
        page: params?.page ?? 1,
        page_size: params?.pageSize ?? 20,
        strategy_name: params?.strategyName,
      },
    })
    return {
      runs: response.data.runs.map(mapBacktestRun),
      totalCount: response.data.total_count,
      page: response.data.page,
      pageSize: response.data.page_size,
    }
  },
  summary: async (): Promise<RunSummaryResponse> => {
    const response = await api.get<RawRunSummaryResponse>('/api/v2/backtest/summary')
    return mapRunSummary(response.data)
  },
  getRun: async (id: string): Promise<BacktestRunInfo> => {
    const response = await api.get<RawBacktestRunInfo>(`/api/v2/backtest/status/${id}`)
    return mapBacktestRun(response.data)
  },
}

export const dataApi = {
  ingest: async (payload: DataIngestionRequestPayload): Promise<BacktestRunInfo> => {
    const response = await api.post<RawBacktestRunInfo>(
      '/api/v2/data/ingest',
      toDataPayload(payload),
    )
    return mapBacktestRun(response.data)
  },
}

export const gridResultsApi = {
  list: async (params: {
    page: number
    pageSize: number
    startDate?: string
    endDate?: string
    symbol?: string
    strategyName?: string
  }): Promise<GridResultsListResponse> => {
    const response = await api.get<RawGridResultsListResponse>('/api/v2/grid/results', {
      params: {
        page: params.page,
        page_size: params.pageSize,
        start_date: params.startDate,
        end_date: params.endDate,
        symbol: params.symbol,
        strategy_name: params.strategyName,
      },
    })
    return {
      results: response.data.results.map(mapGridSummary),
      totalCount: response.data.total_count,
      page: response.data.page,
      pageSize: response.data.page_size,
    }
  },
  detail: async (runId: string): Promise<GridRunDetail> => {
    const response = await api.get<RawGridRunDetail>(`/api/v2/grid/results/${runId}`)
    return mapGridDetail(response.data)
  },
}

export const combinedResultsApi = {
  list: async (params: { symbol?: string; startDate?: string; endDate?: string; offset?: number; limit?: number }) => {
    const response = await api.get<RawCombinedResultsResponse>('/api/v2/combined-results/', {
      params: {
        symbol: params.symbol,
        start_date: params.startDate,
        end_date: params.endDate,
        offset: params.offset ?? 0,
        limit: params.limit ?? 100,
      },
    })
    return mapCombinedResponse(response.data)
  },
}

export const screenerResultsApi = {
  list: async (params: { page?: number; pageSize?: number; startDate?: string; endDate?: string } = {}): Promise<ScreenerResultsListResponse> => {
    const response = await api.get<RawScreenerResultsListResponse>('/api/v2/screener/results', {
      params: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
        start_date: params.startDate,
        end_date: params.endDate,
      },
    })

    return {
      results: response.data.results.map(mapScreenerSummary),
      totalCount: response.data.total_count,
      page: response.data.page,
      pageSize: response.data.page_size,
    }
  },
  detail: async (resultId: string): Promise<ScreenerResultDetail> => {
    const response = await api.get<RawScreenerResultDetail>(`/api/v2/screener/results/${resultId}`)
    return mapScreenerDetail(response.data)
  },
}
