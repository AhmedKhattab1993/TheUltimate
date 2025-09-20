import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Clock, Database, Zap, CheckCircle, XCircle } from 'lucide-react'

interface PerformanceMetricsProps {
  metrics: {
    data_fetch_time_ms: number
    screening_time_ms: number
    total_execution_time_ms: number
    used_bulk_endpoint: boolean
    symbols_fetched: number
    symbols_failed: number
  }
}

export function PerformanceMetrics({ metrics }: PerformanceMetricsProps) {
  const successRate = metrics.symbols_fetched > 0 
    ? ((metrics.symbols_fetched - metrics.symbols_failed) / metrics.symbols_fetched * 100).toFixed(1)
    : '0'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Performance Metrics</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock className="h-4 w-4" />
              <p className="text-sm font-medium">Total Time</p>
            </div>
            <p className="text-2xl font-bold">
              {metrics.total_execution_time_ms !== null && metrics.total_execution_time_ms !== undefined ? 
                `${(metrics.total_execution_time_ms / 1000).toFixed(2)}s` : '0s'
              }
            </p>
          </div>
          
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Database className="h-4 w-4" />
              <p className="text-sm font-medium">Data Fetch</p>
            </div>
            <p className="text-2xl font-bold">
              {metrics.data_fetch_time_ms !== null && metrics.data_fetch_time_ms !== undefined ? 
                `${metrics.data_fetch_time_ms.toFixed(0)}ms` : '0ms'
              }
            </p>
          </div>
          
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Zap className="h-4 w-4" />
              <p className="text-sm font-medium">Screening</p>
            </div>
            <p className="text-2xl font-bold">
              {metrics.screening_time_ms !== null && metrics.screening_time_ms !== undefined ? 
                `${metrics.screening_time_ms.toFixed(0)}ms` : '0ms'
              }
            </p>
          </div>
          
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-muted-foreground">
              <CheckCircle className="h-4 w-4" />
              <p className="text-sm font-medium">Success Rate</p>
            </div>
            <p className="text-2xl font-bold">{successRate}%</p>
          </div>
        </div>
        
        <div className="mt-4 pt-4 border-t grid grid-cols-2 gap-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Symbols Processed:</span>
            <span className="font-medium">{metrics.symbols_fetched}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Failed:</span>
            <span className="font-medium flex items-center gap-1">
              {metrics.symbols_failed > 0 && <XCircle className="h-3 w-3 text-red-500" />}
              {metrics.symbols_failed}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
