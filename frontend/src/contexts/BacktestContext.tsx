import React, { createContext, useContext, useReducer } from 'react'
import type { ReactNode } from 'react'

// Types
export interface Strategy {
  name: string
  file_path: string
  description?: string
  parameters?: Record<string, any>
  last_modified?: string
}

export interface BacktestParameters {
  strategy: string | null
  initialCash: number
  startDate: Date | null
  endDate: Date | null
  symbols: string[]
  useScreenerResults?: boolean
}

export interface BacktestProgress {
  status: 'idle' | 'running' | 'completed' | 'error'
  percentage: number
  message: string
  backtestId?: string
}

export interface BulkBacktestInfo {
  totalBacktests: number
  successfulStarts: number
  failedStarts: number
  backtests: Array<{
    backtest_id: string | null
    symbol: string
    date: string
    status: string
    error?: string
  }>
}

export interface BulkProgress {
  total: number
  completed: number
  running: number
  failed: number
  currentBacktest?: number
  currentSymbol?: string
  currentDate?: string
  message?: string
}

export interface BacktestStatistics {
  // Core Performance Metrics
  totalReturn: number
  netProfit: number
  netProfitCurrency: number
  compoundingAnnualReturn: number
  
  // Risk Metrics
  sharpeRatio: number
  sortinoRatio: number
  maxDrawdown: number
  probabilisticSharpeRatio: number
  
  // Trading Statistics
  totalOrders: number
  totalTrades: number
  winRate: number
  lossRate: number
  averageWin: number
  averageLoss: number
  averageWinCurrency: number
  averageLossCurrency: number
  
  // Advanced Metrics
  profitFactor: number
  profitLossRatio: number
  expectancy: number
  alpha: number
  beta: number
  annualStandardDeviation: number
  annualVariance: number
  informationRatio: number
  trackingError: number
  treynorRatio: number
  
  // Portfolio Information
  startEquity: number
  endEquity: number
  totalFees: number
  estimatedStrategyCapacity: number
  lowestCapacityAsset: string
  portfolioTurnover: number
  
  // Legacy fields for backward compatibility
  profitableTrades?: number
}

export interface EquityPoint {
  date: string
  value: number
}

export interface Order {
  time: string
  symbol: string
  type: 'Market' | 'Limit' | 'StopMarket' | 'StopLimit'
  direction: 'Buy' | 'Sell'
  quantity: number
  price: number
  status: 'Filled' | 'Canceled' | 'Submitted'
  fillPrice?: number
  fillTime?: string
}

export interface BacktestResult {
  backtest_id: string
  timestamp: string
  statistics: BacktestStatistics
  equityCurve: EquityPoint[]
  orders: Order[]
  logs?: string[]
  strategy_name?: string
  start_date?: string
  end_date?: string
  initial_cash?: number
  final_value?: number
}

export interface BacktestState {
  strategies: Strategy[]
  parameters: BacktestParameters
  progress: BacktestProgress
  currentResult: BacktestResult | null
  historicalResults: BacktestResult[]
  error: string | null
  loading: boolean
  websocket: WebSocket | null
  websockets?: WebSocket[]
  bulkInfo?: BulkBacktestInfo
  bulkProgress?: BulkProgress
}

// Action types
export type BacktestAction =
  | { type: 'SET_STRATEGIES'; strategies: Strategy[] }
  | { type: 'SET_PARAMETER'; field: keyof BacktestParameters; value: any }
  | { type: 'SET_SYMBOLS'; symbols: string[] }
  | { type: 'START_BACKTEST'; backtestId: string }
  | { type: 'START_BULK_BACKTESTS'; bulkInfo: BulkBacktestInfo }
  | { type: 'UPDATE_PROGRESS'; progress: Partial<BacktestProgress> }
  | { type: 'UPDATE_BULK_PROGRESS'; bulkProgress: BulkProgress }
  | { type: 'SET_RESULT'; result: BacktestResult }
  | { type: 'ADD_HISTORICAL_RESULT'; result: BacktestResult }
  | { type: 'SET_HISTORICAL_RESULTS'; results: BacktestResult[] }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SET_LOADING'; loading: boolean }
  | { type: 'SET_WEBSOCKET'; websocket: WebSocket | null }
  | { type: 'SET_WEBSOCKETS'; websockets: WebSocket[] }
  | { type: 'RESET' }

// Initial state
const initialState: BacktestState = {
  strategies: [],
  parameters: {
    strategy: null,
    initialCash: 100000,
    startDate: new Date(new Date().getFullYear() - 1, 0, 1), // Default to January 1st of last year
    endDate: new Date(), // Default to today
    symbols: []
  },
  progress: {
    status: 'idle',
    percentage: 0,
    message: ''
  },
  currentResult: null,
  historicalResults: [],
  error: null,
  loading: false,
  websocket: null
}

// Reducer
function backtestReducer(state: BacktestState, action: BacktestAction): BacktestState {
  switch (action.type) {
    case 'SET_STRATEGIES':
      return { ...state, strategies: action.strategies }

    case 'SET_PARAMETER':
      return {
        ...state,
        parameters: {
          ...state.parameters,
          [action.field]: action.value
        }
      }

    case 'SET_SYMBOLS':
      return {
        ...state,
        parameters: {
          ...state.parameters,
          symbols: action.symbols
        }
      }

    case 'START_BACKTEST':
      return {
        ...state,
        progress: {
          status: 'running',
          percentage: 0,
          message: 'Initializing backtest...',
          backtestId: action.backtestId
        },
        currentResult: null,
        error: null
      }

    case 'UPDATE_PROGRESS':
      return {
        ...state,
        progress: {
          ...state.progress,
          ...action.progress
        }
      }

    case 'SET_RESULT':
      return {
        ...state,
        currentResult: action.result,
        progress: {
          ...state.progress,
          status: 'completed',
          percentage: 100
        }
      }

    case 'ADD_HISTORICAL_RESULT':
      return {
        ...state,
        historicalResults: [action.result, ...state.historicalResults]
      }

    case 'SET_HISTORICAL_RESULTS':
      return {
        ...state,
        historicalResults: action.results
      }

    case 'SET_ERROR':
      return {
        ...state,
        error: action.error,
        progress: {
          ...state.progress,
          status: 'error'
        },
        loading: false
      }

    case 'CLEAR_ERROR':
      return { ...state, error: null }

    case 'SET_LOADING':
      return { ...state, loading: action.loading }

    case 'SET_WEBSOCKET':
      return { ...state, websocket: action.websocket }

    case 'SET_WEBSOCKETS':
      return { ...state, websockets: action.websockets }

    case 'START_BULK_BACKTESTS':
      return {
        ...state,
        bulkInfo: action.bulkInfo,
        bulkProgress: {
          total: action.bulkInfo.totalBacktests,
          completed: 0,
          running: action.bulkInfo.successfulStarts,
          failed: action.bulkInfo.failedStarts,
          message: 'Starting backtests...'
        },
        progress: {
          status: 'running',
          percentage: 0,
          message: `Starting ${action.bulkInfo.totalBacktests} backtests...`
        },
        error: null
      }

    case 'UPDATE_BULK_PROGRESS':
      return {
        ...state,
        bulkProgress: action.bulkProgress,
        progress: {
          ...state.progress,
          percentage: action.bulkProgress.total > 0
            ? Math.round((action.bulkProgress.completed / action.bulkProgress.total) * 100)
            : 0,
          message: action.bulkProgress.message || state.progress.message,
          status: action.bulkProgress.completed === action.bulkProgress.total ? 'completed' : 'running'
        }
      }

    case 'RESET':
      return {
        ...initialState,
        strategies: state.strategies,
        historicalResults: state.historicalResults,
        parameters: {
          ...initialState.parameters,
          startDate: new Date(new Date().getFullYear() - 1, 0, 1),
          endDate: new Date()
        }
      }

    default:
      return state
  }
}

// Context
const BacktestContext = createContext<{
  state: BacktestState
  dispatch: React.Dispatch<BacktestAction>
} | undefined>(undefined)

// Provider
export function BacktestProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(backtestReducer, initialState)

  return (
    <BacktestContext.Provider value={{ state, dispatch }}>
      {children}
    </BacktestContext.Provider>
  )
}

// Hook
export function useBacktestContext() {
  const context = useContext(BacktestContext)
  if (context === undefined) {
    throw new Error('useBacktestContext must be used within a BacktestProvider')
  }
  return context
}