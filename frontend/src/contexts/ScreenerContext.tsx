import { createContext, useContext, useReducer } from 'react'
import type { Dispatch, ReactNode } from 'react'

// State interface
type MAPeriod = 20 | 50 | 200
type RSIPeriod = 3 | 14 | 21

type RatioRange = {
  enabled: boolean
  minRatio: string
  maxRatio: string
}

type RsiRange = {
  enabled: boolean
  minValue: string
  maxValue: string
}

type PriceVsMAFilterState = {
  enabled: boolean
  setups: Record<MAPeriod, RatioRange>
}

type RSIFilterState = {
  enabled: boolean
  periods: Record<RSIPeriod, RsiRange>
}

export interface ScreenerState {
  filters: {
    simplePriceRange: {
      enabled: boolean
      minPrice: string
      maxPrice: string
    }
    priceVsMA: PriceVsMAFilterState
    rsi: RSIFilterState
    gap: {
      enabled: boolean
      minGapPercent: string
      maxGapPercent: string
      direction: 'up' | 'down' | 'both'
    }
    prevDayDollarVolume: {
      enabled: boolean
      minDollarVolume: string
      maxDollarVolume: string
    }
    relativeVolume: {
      enabled: boolean
      recentDays: string
      lookbackDays: string
      minRatio: string
      maxRatio: string
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
  | { type: 'TOGGLE_MA_PERIOD'; period: MAPeriod }
  | { type: 'SET_MA_RATIO'; period: MAPeriod; field: 'minRatio' | 'maxRatio'; value: string }
  | { type: 'TOGGLE_RSI_PERIOD'; period: RSIPeriod }
  | { type: 'SET_RSI_VALUE'; period: RSIPeriod; field: 'minValue' | 'maxValue'; value: string }
  | { type: 'SET_DATE_RANGE'; field: 'startDate' | 'endDate'; value: Date | null }
  | { type: 'SET_RESULTS'; data: any }
  | { type: 'SET_LOADING'; loading: boolean }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'SORT_RESULTS'; column: string }
  | { type: 'SET_VIEW_MODE'; mode: 'table' | 'cards' }
  | { type: 'RESET_FILTERS' }

const createInitialFilters = () => ({
  simplePriceRange: {
    enabled: true,
    minPrice: '1.00',
    maxPrice: '100.00'
  },
  priceVsMA: {
    enabled: false,
    setups: {
      20: { enabled: false, minRatio: '1.00', maxRatio: '' },
      50: { enabled: false, minRatio: '1.00', maxRatio: '' },
      200: { enabled: false, minRatio: '1.00', maxRatio: '' }
    }
  } satisfies PriceVsMAFilterState,
  rsi: {
    enabled: false,
    periods: {
      3: { enabled: false, minValue: '', maxValue: '30' },
      14: { enabled: false, minValue: '', maxValue: '30' },
      21: { enabled: false, minValue: '', maxValue: '30' }
    }
  } satisfies RSIFilterState,
  gap: {
    enabled: false,
    minGapPercent: '2.0',
    maxGapPercent: '',
    direction: 'both'
  },
  prevDayDollarVolume: {
    enabled: false,
    minDollarVolume: '10000000',
    maxDollarVolume: ''
  },
  relativeVolume: {
    enabled: false,
    recentDays: '2',
    lookbackDays: '20',
    minRatio: '1.5',
    maxRatio: ''
  }
})

// Initial state
const initialState: ScreenerState = {
  filters: createInitialFilters(),
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

    case 'TOGGLE_MA_PERIOD': {
      const current = state.filters.priceVsMA.setups[action.period]
      const updatedSetups = {
        ...state.filters.priceVsMA.setups,
        [action.period]: {
          ...current,
          enabled: !current.enabled
        }
      }
      const hasEnabled = Object.values(updatedSetups).some((setup) => setup.enabled)

      return {
        ...state,
        filters: {
          ...state.filters,
          priceVsMA: {
            enabled: hasEnabled,
            setups: updatedSetups
          }
        }
      }
    }

    case 'SET_MA_RATIO': {
      const current = state.filters.priceVsMA.setups[action.period]
      const updatedSetups = {
        ...state.filters.priceVsMA.setups,
        [action.period]: {
          ...current,
          [action.field]: action.value
        }
      }
      const hasEnabled = Object.values(updatedSetups).some((setup) => setup.enabled)

      return {
        ...state,
        filters: {
          ...state.filters,
          priceVsMA: {
            enabled: hasEnabled,
            setups: updatedSetups
          }
        }
      }
    }

    case 'TOGGLE_RSI_PERIOD': {
      const current = state.filters.rsi.periods[action.period]
      const updatedPeriods = {
        ...state.filters.rsi.periods,
        [action.period]: {
          ...current,
          enabled: !current.enabled
        }
      }
      const hasEnabled = Object.values(updatedPeriods).some((period) => period.enabled)

      return {
        ...state,
        filters: {
          ...state.filters,
          rsi: {
            enabled: hasEnabled,
            periods: updatedPeriods
          }
        }
      }
    }

    case 'SET_RSI_VALUE': {
      const current = state.filters.rsi.periods[action.period]
      const updatedPeriods = {
        ...state.filters.rsi.periods,
        [action.period]: {
          ...current,
          [action.field]: action.value
        }
      }
      const hasEnabled = Object.values(updatedPeriods).some((period) => period.enabled)

      return {
        ...state,
        filters: {
          ...state.filters,
          rsi: {
            enabled: hasEnabled,
            periods: updatedPeriods
          }
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

    case 'SORT_RESULTS': {
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
        filters: createInitialFilters(),
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
