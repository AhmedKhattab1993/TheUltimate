import React, { createContext, useContext, useReducer, ReactNode } from 'react'

// Types
export interface ScreenerResultSummary {
  id: string
  timestamp: string
  symbol_count: number
  filters: any
  execution_time_ms: number
  total_symbols_screened: number
}

export interface BacktestResultSummary {
  backtestId: string
  strategyName: string
  symbol?: string
  startDate: string
  endDate: string
  initialCash?: number
  finalValue?: number
  statistics: {
    totalReturn: number
    sharpeRatio: number
    sortinoRatio?: number
    maxDrawdown: number
    winRate: number
    totalTrades: number
    netProfitCurrency?: number
    // Enhanced statistics for detailed view
    netProfit?: number
    compoundingAnnualReturn?: number
    startEquity?: number
    endEquity?: number
    probabilisticSharpeRatio?: number
    annualStandardDeviation?: number
    annualVariance?: number
    beta?: number
    alpha?: number
    totalOrders?: number
    winningTrades?: number
    losingTrades?: number
    lossRate?: number
    averageWin?: number
    averageLoss?: number
    profitFactor?: number
    profitLossRatio?: number
    expectancy?: number
    informationRatio?: number
    trackingError?: number
    treynorRatio?: number
    totalFees?: number
    estimatedStrategyCapacity?: number
    lowestCapacityAsset?: string
    portfolioTurnover?: number
    pivotHighsDetected?: number
    pivotLowsDetected?: number
    bosSignalsGenerated?: number
    positionFlips?: number
    liquidationEvents?: number
  }
  // Algorithm Parameters
  resolution?: string
  pivotBars?: number
  lowerTimeframe?: string
  // Execution Metadata
  executionTimeMs?: number
  resultPath?: string
  status?: string
  errorMessage?: string
  cacheHit?: boolean
  createdAt: string
  // Optional detailed data
  orders?: any[]
  equityCurve?: any[]
}

export interface ResultsState {
  activeTab: 'screener' | 'backtest' | 'combined'
  screenerResults: {
    data: ScreenerResultSummary[]
    loading: boolean
    error: string | null
    totalCount: number
    page: number
    pageSize: number
  }
  backtestResults: {
    data: BacktestResultSummary[]
    loading: boolean
    error: string | null
    totalCount: number
    page: number
    pageSize: number
  }
  combinedResults: {
    page: number
    pageSize: number
  }
  dateFilter: {
    startDate: Date | null
    endDate: Date | null
  }
}

// Action types
type ResultsAction =
  | { type: 'SET_ACTIVE_TAB'; tab: 'screener' | 'backtest' | 'combined' }
  | { type: 'SET_SCREENER_RESULTS'; data: ScreenerResultSummary[]; totalCount: number }
  | { type: 'SET_BACKTEST_RESULTS'; data: BacktestResultSummary[]; totalCount: number }
  | { type: 'SET_SCREENER_LOADING'; loading: boolean }
  | { type: 'SET_BACKTEST_LOADING'; loading: boolean }
  | { type: 'SET_SCREENER_ERROR'; error: string | null }
  | { type: 'SET_BACKTEST_ERROR'; error: string | null }
  | { type: 'SET_SCREENER_PAGE'; page: number }
  | { type: 'SET_BACKTEST_PAGE'; page: number }
  | { type: 'SET_COMBINED_PAGE'; page: number }
  | { type: 'SET_DATE_FILTER'; startDate: Date | null; endDate: Date | null }
  | { type: 'RESET_FILTERS' }

// Initial state
const initialState: ResultsState = {
  activeTab: 'screener',
  screenerResults: {
    data: [],
    loading: false,
    error: null,
    totalCount: 0,
    page: 1,
    pageSize: 20
  },
  backtestResults: {
    data: [],
    loading: false,
    error: null,
    totalCount: 0,
    page: 1,
    pageSize: 20
  },
  combinedResults: {
    page: 1,
    pageSize: 20
  },
  dateFilter: {
    startDate: null,
    endDate: null
  }
}

// Reducer
function resultsReducer(state: ResultsState, action: ResultsAction): ResultsState {
  switch (action.type) {
    case 'SET_ACTIVE_TAB':
      return { ...state, activeTab: action.tab }
    
    case 'SET_SCREENER_RESULTS':
      return {
        ...state,
        screenerResults: {
          ...state.screenerResults,
          data: action.data,
          totalCount: action.totalCount,
          loading: false,
          error: null
        }
      }
    
    case 'SET_BACKTEST_RESULTS':
      return {
        ...state,
        backtestResults: {
          ...state.backtestResults,
          data: action.data,
          totalCount: action.totalCount,
          loading: false,
          error: null
        }
      }
    
    case 'SET_SCREENER_LOADING':
      return {
        ...state,
        screenerResults: { ...state.screenerResults, loading: action.loading }
      }
    
    case 'SET_BACKTEST_LOADING':
      return {
        ...state,
        backtestResults: { ...state.backtestResults, loading: action.loading }
      }
    
    case 'SET_SCREENER_ERROR':
      return {
        ...state,
        screenerResults: {
          ...state.screenerResults,
          error: action.error,
          loading: false
        }
      }
    
    case 'SET_BACKTEST_ERROR':
      return {
        ...state,
        backtestResults: {
          ...state.backtestResults,
          error: action.error,
          loading: false
        }
      }
    
    case 'SET_SCREENER_PAGE':
      return {
        ...state,
        screenerResults: { ...state.screenerResults, page: action.page }
      }
    
    case 'SET_BACKTEST_PAGE':
      return {
        ...state,
        backtestResults: { ...state.backtestResults, page: action.page }
      }
    
    case 'SET_COMBINED_PAGE':
      return {
        ...state,
        combinedResults: { ...state.combinedResults, page: action.page }
      }
    
    case 'SET_DATE_FILTER':
      return {
        ...state,
        dateFilter: {
          startDate: action.startDate,
          endDate: action.endDate
        }
      }
    
    case 'RESET_FILTERS':
      return {
        ...state,
        dateFilter: {
          startDate: null,
          endDate: null
        },
        screenerResults: { ...state.screenerResults, page: 1 },
        backtestResults: { ...state.backtestResults, page: 1 }
      }
    
    default:
      return state
  }
}

// Context
const ResultsContext = createContext<{
  state: ResultsState
  dispatch: React.Dispatch<ResultsAction>
} | undefined>(undefined)

// Provider
export function ResultsProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(resultsReducer, initialState)

  return (
    <ResultsContext.Provider value={{ state, dispatch }}>
      {children}
    </ResultsContext.Provider>
  )
}

// Hook
export function useResultsContext() {
  const context = useContext(ResultsContext)
  if (!context) {
    throw new Error('useResultsContext must be used within a ResultsProvider')
  }
  return context
}