import { AlertCircle, RefreshCw, WifiOff } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface ApiErrorProps {
  error: string
  onRetry?: () => void
}

export function ApiError({ error, onRetry }: ApiErrorProps) {
  const isNetworkError = error.toLowerCase().includes('network') || error.toLowerCase().includes('fetch')
  const isServerError = error.toLowerCase().includes('500') || error.toLowerCase().includes('server')
  const isValidationError = error.toLowerCase().includes('validation') || error.toLowerCase().includes('invalid')

  const getErrorIcon = () => {
    if (isNetworkError) return <WifiOff className="h-4 w-4" />
    return <AlertCircle className="h-4 w-4" />
  }

  const getErrorTitle = () => {
    if (isNetworkError) return 'Connection Error'
    if (isServerError) return 'Server Error'
    if (isValidationError) return 'Invalid Request'
    return 'Error'
  }

  const getErrorDescription = () => {
    if (isNetworkError) {
      return 'Unable to connect to the server. Please check your internet connection and try again.'
    }
    if (isServerError) {
      return 'The server encountered an error. Please try again later or contact support if the issue persists.'
    }
    return error
  }

  return (
    <Alert variant="destructive">
      {getErrorIcon()}
      <AlertTitle>{getErrorTitle()}</AlertTitle>
      <AlertDescription className="mt-2">
        <p className="mb-3">{getErrorDescription()}</p>
        {onRetry && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="gap-2"
          >
            <RefreshCw className="h-3 w-3" />
            Try Again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}
