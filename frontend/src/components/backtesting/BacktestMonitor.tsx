import React, { useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useBacktestContext } from '@/contexts/BacktestContext'
import { Activity, CheckCircle, XCircle, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

export function BacktestMonitor() {
  const { state } = useBacktestContext()
  const { progress, bulkProgress } = state

  const statusIcon = {
    idle: Clock,
    running: Activity,
    completed: CheckCircle,
    error: XCircle
  }[progress.status]

  const StatusIcon = statusIcon

  const statusColor = {
    idle: 'text-muted-foreground',
    running: 'text-blue-500',
    completed: 'text-green-500',
    error: 'text-red-500'
  }[progress.status]

  if (progress.status === 'idle') {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backtest Progress</CardTitle>
        <CardDescription>
          Real-time backtest execution status
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <StatusIcon className={cn('h-5 w-5', statusColor)} />
          <div className="flex-1">
            <p className="text-sm font-medium capitalize">{progress.status}</p>
            <p className="text-xs text-muted-foreground">{progress.message}</p>
          </div>
          <span className="text-lg font-mono">{progress.percentage}%</span>
        </div>

        <Progress value={progress.percentage} className="h-2" />

        {/* Bulk Progress Details */}
        {bulkProgress && bulkProgress.total > 1 && (
          <div className="pt-3 border-t space-y-2">
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-muted-foreground">Total</p>
                <p className="font-medium">{bulkProgress.total}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Completed</p>
                <p className="font-medium text-green-600">{bulkProgress.completed}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Running</p>
                <p className="font-medium text-blue-600">{bulkProgress.running}</p>
              </div>
            </div>
            
            {bulkProgress.currentSymbol && bulkProgress.currentDate && (
              <div className="pt-2">
                <p className="text-xs text-muted-foreground">
                  Current: <span className="font-medium">{bulkProgress.currentSymbol}</span> on {bulkProgress.currentDate}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Single Backtest ID */}
        {progress.backtestId && !bulkProgress && (
          <div className="pt-2 border-t">
            <p className="text-xs text-muted-foreground">
              Backtest ID: <span className="font-mono">{progress.backtestId}</span>
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}