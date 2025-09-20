import { createContext, useContext, useReducer } from 'react'
import type { Dispatch, ReactNode } from 'react'

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
  strategyParameters?: Record<string, unknown>
}

// Simplified - just track running state

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
  backtestId?: string
  timestamp: string
  statistics: BacktestStatistics
  equityCurve: EquityPoint[]
  orders: Order[]
  logs?: string[]
  strategyName?: string
  strategy_name?: string
  start_date?: string
  end_date?: string
  initial_cash?: number
  final_value?: number
}

export interface LastRunDetails {
  symbols: string[]
  startTime: Date
  bulkId?: string
  screenerSessionId?: string
}

export interface BacktestState {
  strategies: Strategy[]
  parameters: BacktestParameters
  isRunning: boolean
  currentResult: BacktestResult | null
  historicalResults: BacktestResult[]
  error: string | null
  websocket: WebSocket | null
  lastRunDetails: LastRunDetails | null
  completedAt: number | null  // Timestamp when backtests completed
}

// Action types
export type BacktestAction =
  | { type: 'SET_STRATEGIES'; strategies: Strategy[] }
  | { type: 'SET_PARAMETER'; field: keyof BacktestParameters; value: any }
  | { type: 'SET_SYMBOLS'; symbols: string[] }
  | { type: 'START_BACKTESTS' }
  | { type: 'COMPLETE_BACKTESTS' }
  | { type: 'SET_RESULT'; result: BacktestResult }
  | { type: 'ADD_HISTORICAL_RESULT'; result: BacktestResult }
  | { type: 'SET_HISTORICAL_RESULTS'; results: BacktestResult[] }
  | { type: 'SET_ERROR'; error: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SET_WEBSOCKET'; websocket: WebSocket | null }
  | { type: 'SET_LAST_RUN_DETAILS'; details: LastRunDetails }
  | { type: 'RESET' }

// Initial state
const initialState: BacktestState = {
  strategies: [],
  parameters: {
    strategy: null,
    initialCash: 100000,
    startDate: new Date(new Date().getFullYear() - 1, 0, 1), // Default to January 1st of last year
    endDate: new Date(), // Default to today
    symbols: [],
    strategyParameters: {}
  },
  isRunning: false,
  currentResult: null,
  historicalResults: [],
  error: null,
  websocket: null,
  lastRunDetails: null,
  completedAt: null
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

    case 'START_BACKTESTS':
      return {
        ...state,
        isRunning: true,
        currentResult: null,
        error: null
      }

    case 'COMPLETE_BACKTESTS':
      return {
        ...state,
        isRunning: false,
        completedAt: Date.now()  // Set timestamp when backtests complete
      }

    case 'SET_RESULT':
      return {
        ...state,
        currentResult: action.result
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
        isRunning: false
      }

    case 'CLEAR_ERROR':
      return { ...state, error: null }

    case 'SET_WEBSOCKET':
      return { ...state, websocket: action.websocket }

    case 'SET_LAST_RUN_DETAILS':
      return { ...state, lastRunDetails: action.details }

    case 'RESET':
      return {
        ...initialState,
        strategies: state.strategies,
        historicalResults: state.historicalResults,
        lastRunDetails: state.lastRunDetails,
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
  dispatch: Dispatch<BacktestAction>
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
