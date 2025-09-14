import type { GridResultsListResponse, GridResultDetail } from '@/types/gridResults'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const GridResultsService = {
  async listResults(page: number = 1, pageSize: number = 20): Promise<GridResultsListResponse> {
    const response = await fetch(
      `${API_BASE_URL}/api/v2/grid/results?page=${page}&page_size=${pageSize}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch grid results')
    }

    return response.json()
  },

  async getResultDetail(date: string, symbol?: string): Promise<GridResultDetail> {
    const url = symbol 
      ? `${API_BASE_URL}/api/v2/grid/results/${date}/detail?symbol=${symbol}`
      : `${API_BASE_URL}/api/v2/grid/results/${date}/detail`
      
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch grid result details')
    }

    return response.json()
  },

  async getSymbolResults(date: string, symbol: string): Promise<any> {
    const response = await fetch(
      `${API_BASE_URL}/api/v2/grid/results/${date}/symbols/${symbol}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch symbol results')
    }

    return response.json()
  },

  async getSymbolPivotTrades(date: string, symbol: string, pivotBars: number, limit: number = 50): Promise<any[]> {
    const response = await fetch(
      `${API_BASE_URL}/api/v2/grid/results/${date}/symbols/${symbol}/pivot/${pivotBars}/trades?limit=${limit}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to fetch trades')
    }

    return response.json()
  }
}