export type ControlType = 'range' | 'number' | 'select' | 'toggle'

export interface FilterOption {
  label: string
  value: string | number
  description?: string
}

export interface FilterControl {
  controlType: ControlType
  field: string
  label: string
  description?: string
  defaultValue?: string | number | boolean
  minValue?: number
  maxValue?: number
  step?: number
  options?: FilterOption[]
  unit?: string
  placeholder?: string
  required?: boolean
}

export type FilterCategory = 'price' | 'momentum' | 'volume' | 'volatility' | 'liquidity' | 'misc'

export interface FilterDefinition {
  id: string
  backendKey: string
  label: string
  category: FilterCategory
  description: string
  defaultEnabled: boolean
  controls: FilterControl[]
  tags: string[]
  sortOrder: number
  docUrl?: string
}

export interface FilterState {
  enabled: boolean
  values: Record<string, string | number | boolean>
}

export type FilterStateMap = Record<string, FilterState>

export interface StrategyParameter {
  name: string
  label: string
  description?: string
  controlType: ControlType | 'text'
  defaultValue?: string | number | boolean
  minValue?: number
  maxValue?: number
  step?: number
  options?: FilterOption[]
  required?: boolean
}

export interface StrategyDefinition {
  id: string
  label: string
  description: string
  projectPath: string
  parameters: StrategyParameter[]
  defaults: Record<string, string | number | boolean>
  capabilities: {
    supports: Array<'backtest' | 'grid' | 'optimize'>
    defaultJobType: 'backtest' | 'grid' | 'optimize'
    parallelism?: number | null
  }
  documentationUrl?: string
  notes?: string
}

export interface RegistryResponse {
  filters: FilterDefinition[]
  strategies: StrategyDefinition[]
}

export interface ScreenerRequestPayload {
  startDate: string
  endDate: string
  filters: FilterStateMap
  useAllUsStocks?: boolean
  enableDbPrefiltering?: boolean
}

export interface ScreenerResultRow {
  symbol: string
  qualifyingDates: string[]
  totalDaysAnalyzed: number
  qualifyingDaysCount: number
  metrics: Record<string, number | string | null>
}

export interface ScreenerResponse {
  executionTimeMs: number
  totalSymbolsScreened: number
  totalQualifyingStocks: number
  results: ScreenerResultRow[]
}

export interface BacktestRequestPayload {
  strategyName: string
  startDate: string
  endDate: string
  initialCash: number
  resolution: 'Tick' | 'Second' | 'Minute' | 'Hour' | 'Daily'
  pivotBars: number
  lowerTimeframe: string
  symbols?: string[]
  useScreenerResults?: boolean
  parameters?: Record<string, string | number | boolean>
}

export interface BacktestRunInfo {
  backtestId: string
  status: string
  jobType: string
  createdAt: string
  startedAt?: string | null
  completedAt?: string | null
  errorMessage?: string | null
  resultPath?: string | null
  request: BacktestRequestPayload
  metrics?: Record<string, number>
  targets?: string[]
}

export interface BacktestRunListResponse {
  runs: BacktestRunInfo[]
  totalCount: number
  page: number
  pageSize: number
}

export interface GridBacktestRequestPayload {
  baseRequest: BacktestRequestPayload
  parameterSweeps: Array<Record<string, string | number | boolean>>
}

export interface OptimizationParameterRange {
  name: string
  min: number
  max: number
  step: number
}

export interface OptimizeRequestPayload {
  baseRequest: BacktestRequestPayload
  targetMetric: string
  targetDirection: 'maximize' | 'minimize'
  parameters: OptimizationParameterRange[]
  maxConcurrentBacktests?: number
}

export interface DataIngestionRequestPayload {
  dataset: 'minute'
  startDate: string
  endDate: string
  resume: boolean
}

export interface JobTypeSummary {
  jobType: string
  totalRuns: number
  completedRuns: number
  failedRuns: number
  lastRunId?: string | null
  lastRunAt?: string | null
}

export interface MetricSummary {
  jobType: string
  metricKey: string
  metricValue: number
  runId: string
  strategyName: string
  createdAt: string
}

export interface TargetSummary {
  jobType: string
  targetCount: number
}

export interface RunSummaryResponse {
  jobTypes: JobTypeSummary[]
  metrics: MetricSummary[]
  targets: TargetSummary[]
}

export interface GridResultSummary {
  date: string
  screeningSymbols: number
  backtestCount: number
  backtestCompleted: number
  backtestFailed: number
  screeningTimeMs?: number | null
  backtestTimeMs?: number | null
}

export interface GridResultsListResponse {
  results: GridResultSummary[]
  totalCount: number
  page: number
  pageSize: number
}

export interface GridScreeningResult {
  symbol: string
  price: number
  ma20: number
  ma50: number
  ma200: number
  rsi14: number
  gapPercent: number
  prevDayDollarVolume: number
  relativeVolume: number
}

export interface GridBacktestResultRow {
  symbol: string
  pivotBars: number
  status: string
  totalReturn: number
  sharpeRatio: number
  maxDrawdown: number
  winRate: number
  totalTrades: number
  backtestId?: string | null
}

export interface GridResultDetail {
  date: string
  screeningResults: GridScreeningResult[]
  backtestResults: GridBacktestResultRow[]
  totalScreeningSymbols: number
  totalBacktests: number
}

export interface CombinedScreenerBacktestRow {
  symbol: string
  screeningDate?: string | null
  source?: string | null
  companyName?: string | null
  screenedAt?: string | null
  backtestId?: string | null
  backtestCreatedAt?: string | null
  strategyName?: string | null
  totalReturn?: number | null
  sharpeRatio?: number | null
  maxDrawdown?: number | null
  winRate?: number | null
  totalTrades?: number | null
  pivotBars?: number | null
  lowerTimeframe?: string | null
  initialCash?: number | null
}

export interface CombinedResultsResponse {
  results: CombinedScreenerBacktestRow[]
  totalCount: number
  limit: number
  offset: number
}
