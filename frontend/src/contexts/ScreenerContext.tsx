import { createContext, useContext, useReducer } from 'react'
import type { Dispatch, ReactNode } from 'react'

// State interface
export interface ScreenerState {
  filters: {
    simplePriceRange: {
      enabled: boolean
      minPrice: string
      maxPrice: string
    }
    priceVsMA: {
      enabled: boolean
      period: 20 | 50 | 200
      condition: 'above' | 'below'
    }
    rsi: {
      enabled: boolean
      period: string
      threshold: string
      condition: 'above' | 'below'
    }
    gap: {
      enabled: boolean
      threshold: string
      direction: 'up' | 'down' | 'both'
    }
    prevDayDollarVolume: {
      enabled: boolean
      minDollarVolume: string
    }
    relativeVolume: {
      enabled: boolean
      recentDays: string
      lookbackDays: string
      minRatio: string
    }
  }
  dateRange: {
    startDate: Date | null
    endDate: Date | null
  }
  stockSelection: {
    useAllStocks: boolean
  }
  results: {
    data: any | null
    loading: boolean
    error: string | null
  }
  ui: {
    sortColumn: string
    sortDirection: 'asc' | 'desc'
    resultsView: 'table' | 'cards'
  }
}

// Action types
export type ScreenerAction =
  | { type: 'SET_FILTER'; filter: keyof ScreenerState['filters']; field: string; value: any }
  | { type: 'TOGGLE_FILTER'; filter: keyof ScreenerState['filters'] }
  | { type: 'SET_DATE_RANGE'; field: 'startDate' | 'endDate'; value: Date | null }
  | { type: 'SET_RESULTS'; data: any }
  | { type: 'SET_LOADING'; loading: boolean }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'SORT_RESULTS'; column: string }
  | { type: 'SET_VIEW_MODE'; mode: 'table' | 'cards' }
  | { type: 'RESET_FILTERS' }

// Initial state
const initialState: ScreenerState = {
  filters: {
    simplePriceRange: {
      enabled: true,
      minPrice: '1.00',
      maxPrice: '100.00'
    },
    priceVsMA: {
      enabled: false,
      period: 50,
      condition: 'above'
    },
    rsi: {
      enabled: false,
      period: '14',
      threshold: '30',
      condition: 'below'
    },
    gap: {
      enabled: false,
      threshold: '2.0',
      direction: 'both'
    },
    prevDayDollarVolume: {
      enabled: false,
      minDollarVolume: '10000000'
    },
    relativeVolume: {
      enabled: false,
      recentDays: '2',
      lookbackDays: '20',
      minRatio: '1.5'
    }
  },
  dateRange: {
    startDate: null,
    endDate: null
  },
  stockSelection: {
    useAllStocks: true
  },
  results: {
    data: null,
    loading: false,
    error: null
  },
  ui: {
    sortColumn: 'symbol',
    sortDirection: 'asc',
    resultsView: 'table'
  }
}

// Reducer
function screenerReducer(state: ScreenerState, action: ScreenerAction): ScreenerState {
  switch (action.type) {
    case 'SET_FILTER':
      return {
        ...state,
        filters: {
          ...state.filters,
          [action.filter]: {
            ...state.filters[action.filter],
            [action.field]: action.value
          }
        },
        ui: {
          ...state.ui
        }
      }

    case 'TOGGLE_FILTER':
      return {
        ...state,
        filters: {
          ...state.filters,
          [action.filter]: {
            ...state.filters[action.filter],
            enabled: !state.filters[action.filter].enabled
          }
        }
      }


    case 'SET_DATE_RANGE':
      return {
        ...state,
        dateRange: {
          ...state.dateRange,
          [action.field]: action.value
        }
      }

    case 'SET_RESULTS':
      return {
        ...state,
        results: {
          ...state.results,
          data: action.data,
          loading: false,
          error: null
        }
      }

    case 'SET_LOADING':
      return {
        ...state,
        results: {
          ...state.results,
          loading: action.loading
        }
      }

    case 'SET_ERROR':
      return {
        ...state,
        results: {
          ...state.results,
          error: action.error,
          loading: false
        }
      }

    case 'SORT_RESULTS':
      const newDirection = 
        state.ui.sortColumn === action.column && state.ui.sortDirection === 'asc' 
          ? 'desc' 
          : 'asc'
      
      return {
        ...state,
        ui: {
          ...state.ui,
          sortColumn: action.column,
          sortDirection: newDirection
        }
      }

    case 'SET_VIEW_MODE':
      return {
        ...state,
        ui: {
          ...state.ui,
          resultsView: action.mode
        }
      }

    case 'RESET_FILTERS':
      return {
        ...state,
        filters: initialState.filters,
        ui: {
          ...state.ui
        }
      }

    default:
      return state
  }
}

// Context
interface ScreenerContextValue {
  state: ScreenerState
  dispatch: Dispatch<ScreenerAction>
}

const ScreenerContext = createContext<ScreenerContextValue | undefined>(undefined)

// Provider component
export function ScreenerProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(screenerReducer, initialState)

  return (
    <ScreenerContext.Provider value={{ state, dispatch }}>
      {children}
    </ScreenerContext.Provider>
  )
}

// Hook to use the context
export function useScreenerContext() {
  const context = useContext(ScreenerContext)
  if (!context) {
    throw new Error('useScreenerContext must be used within a ScreenerProvider')
  }
  return context
}
