export class ApiError extends Error {
  public statusCode?: number
  public details?: unknown

  constructor(message: string, statusCode?: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.details = details
  }
}

export function parseApiError(error: any): string {
  // Handle axios errors
  if (error.response) {
    const status = error.response.status
    const data = error.response.data

    // Handle specific status codes
    switch (status) {
      case 400:
        return data.message || data.detail || 'Invalid request. Please check your filters.'
      case 401:
        return 'Authentication required. Please log in.'
      case 403:
        return 'You do not have permission to perform this action.'
      case 404:
        return 'The requested resource was not found.'
      case 422:
        if (data.detail && Array.isArray(data.detail)) {
          const errors = data.detail.map((err: any) => {
            const field = err.loc?.join('.') || 'field'
            return `${field}: ${err.msg}`
          })
          return errors.join(', ')
        }
        return data.message || 'Validation error. Please check your input.'
      case 429:
        return 'Too many requests. Please wait a moment and try again.'
      case 500:
        return 'Server error. Please try again later.'
      case 502:
      case 503:
      case 504:
        return 'Service temporarily unavailable. Please try again later.'
      default:
        return data.message || data.detail || `Server error (${status})`
    }
  }

  // Handle network errors
  if (error.request) {
    return 'Network error. Please check your internet connection.'
  }

  // Handle other errors
  return error.message || 'An unexpected error occurred.'
}

export function isRetryableError(error: any): boolean {
  if (!error.response) return true // Network errors are retryable
  
  const status = error.response?.status
  return status >= 500 || status === 429
}
