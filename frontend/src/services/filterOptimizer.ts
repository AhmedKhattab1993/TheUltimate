import type { 
  OptimizationRequest, 
  OptimizationResponse, 
  SuggestedRanges 
} from '@/types/filterOptimizer'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class FilterOptimizerService {
  async optimizeFilters(request: OptimizationRequest): Promise<OptimizationResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v2/filter-optimizer/optimize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to optimize filters')
    }

    return response.json()
  }

  async getSuggestedRanges(startDate: string, endDate: string): Promise<SuggestedRanges> {
    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
    })

    const response = await fetch(
      `${API_BASE_URL}/api/v2/filter-optimizer/suggested-ranges?${params}`
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to get suggested ranges')
    }

    return response.json()
  }
}

export const filterOptimizerService = new FilterOptimizerService()