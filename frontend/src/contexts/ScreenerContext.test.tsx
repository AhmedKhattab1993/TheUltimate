import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { ScreenerProvider, useScreenerContext } from './ScreenerContext'
import type { ReactNode } from 'react'

// Wrapper component for testing
const wrapper = ({ children }: { children: ReactNode }) => (
  <ScreenerProvider>{children}</ScreenerProvider>
)

describe('ScreenerContext', () => {
  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      expect(result.current.state.filters.simplePriceRange).toEqual({
        enabled: true,
        minPrice: '1.00',
        maxPrice: '100.00'
      })
      
      expect(result.current.state.filters.priceVsMA).toEqual({
        enabled: false,
        period: 50,
        condition: 'above'
      })
      
      expect(result.current.state.filters.rsi).toEqual({
        enabled: false,
        period: '14',
        threshold: '30',
        condition: 'below'
      })
      
      expect(result.current.state.dateRange).toEqual({
        startDate: null,
        endDate: null
      })
      
      expect(result.current.state.stockSelection).toEqual({
        useAllStocks: true
      })
    })
  })

  describe('Filter Actions', () => {
    it('should update filter values', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      act(() => {
        result.current.dispatch({
          type: 'SET_FILTER',
          filter: 'simplePriceRange',
          field: 'minPrice',
          value: '5.00'
        })
      })
      
      expect(result.current.state.filters.simplePriceRange.minPrice).toBe('5.00')
    })

    it('should toggle filter enabled state', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      act(() => {
        result.current.dispatch({
          type: 'TOGGLE_FILTER',
          filter: 'priceVsMA'
        })
      })
      
      expect(result.current.state.filters.priceVsMA.enabled).toBe(true)
      
      act(() => {
        result.current.dispatch({
          type: 'TOGGLE_FILTER',
          filter: 'priceVsMA'
        })
      })
      
      expect(result.current.state.filters.priceVsMA.enabled).toBe(false)
    })


    it('should reset filters to initial state', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      // First modify some filters
      act(() => {
        result.current.dispatch({
          type: 'SET_FILTER',
          filter: 'simplePriceRange',
          field: 'minPrice',
          value: '50.00'
        })
        result.current.dispatch({
          type: 'TOGGLE_FILTER',
          filter: 'rsi'
        })
      })
      
      // Then reset
      act(() => {
        result.current.dispatch({ type: 'RESET_FILTERS' })
      })
      
      expect(result.current.state.filters.simplePriceRange.minPrice).toBe('1.00')
      expect(result.current.state.filters.rsi.enabled).toBe(false)
    })
  })

  describe('Date Range Actions', () => {
    it('should set date range correctly', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      const startDate = new Date('2024-01-01')
      const endDate = new Date('2024-01-31')
      
      act(() => {
        result.current.dispatch({
          type: 'SET_DATE_RANGE',
          field: 'startDate',
          value: startDate
        })
        result.current.dispatch({
          type: 'SET_DATE_RANGE',
          field: 'endDate',
          value: endDate
        })
      })
      
      expect(result.current.state.dateRange.startDate).toEqual(startDate)
      expect(result.current.state.dateRange.endDate).toEqual(endDate)
    })
  })


  describe('Results Actions', () => {
    it('should handle loading state', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      act(() => {
        result.current.dispatch({
          type: 'SET_LOADING',
          loading: true
        })
      })
      
      expect(result.current.state.results.loading).toBe(true)
      
      act(() => {
        result.current.dispatch({
          type: 'SET_LOADING',
          loading: false
        })
      })
      
      expect(result.current.state.results.loading).toBe(false)
    })

    it('should set results data', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      const mockData = {
        total_symbols_screened: 100,
        total_qualifying_stocks: 10,
        results: []
      }
      
      act(() => {
        result.current.dispatch({
          type: 'SET_RESULTS',
          data: mockData
        })
      })
      
      expect(result.current.state.results.data).toEqual(mockData)
      expect(result.current.state.results.loading).toBe(false)
      expect(result.current.state.results.error).toBe(null)
    })

    it('should handle error state', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      act(() => {
        result.current.dispatch({
          type: 'SET_ERROR',
          error: 'Test error message'
        })
      })
      
      expect(result.current.state.results.error).toBe('Test error message')
      expect(result.current.state.results.loading).toBe(false)
    })
  })

  describe('UI Actions', () => {
    it('should handle sorting', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      // Initial state has sortColumn as 'symbol' and sortDirection as 'asc'
      expect(result.current.state.ui.sortColumn).toBe('symbol')
      expect(result.current.state.ui.sortDirection).toBe('asc')
      
      // Second click on same column - should sort descending
      act(() => {
        result.current.dispatch({
          type: 'SORT_RESULTS',
          column: 'symbol'
        })
      })
      
      expect(result.current.state.ui.sortColumn).toBe('symbol')
      expect(result.current.state.ui.sortDirection).toBe('desc')
      
      // Click on different column - should reset to ascending
      act(() => {
        result.current.dispatch({
          type: 'SORT_RESULTS',
          column: 'price'
        })
      })
      
      expect(result.current.state.ui.sortColumn).toBe('price')
      expect(result.current.state.ui.sortDirection).toBe('asc')
    })

    it('should change view mode', () => {
      const { result } = renderHook(() => useScreenerContext(), { wrapper })
      
      act(() => {
        result.current.dispatch({
          type: 'SET_VIEW_MODE',
          mode: 'cards'
        })
      })
      
      expect(result.current.state.ui.resultsView).toBe('cards')
      
      act(() => {
        result.current.dispatch({
          type: 'SET_VIEW_MODE',
          mode: 'table'
        })
      })
      
      expect(result.current.state.ui.resultsView).toBe('table')
    })
  })

  describe('Error Handling', () => {
    it('should throw error when used outside provider', () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      
      expect(() => {
        renderHook(() => useScreenerContext())
      }).toThrow('useScreenerContext must be used within a ScreenerProvider')
      
      consoleError.mockRestore()
    })
  })
})
