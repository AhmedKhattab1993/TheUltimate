import React, { useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useBacktestContext } from '@/contexts/BacktestContext'
import { Activity, CheckCircle, XCircle, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

export function BacktestMonitor() {
  const { state } = useBacktestContext()
  const { progress } = state

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

        {progress.backtestId && (
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