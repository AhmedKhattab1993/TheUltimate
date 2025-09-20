import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useBacktestContext } from '@/contexts/BacktestContext'
import { Activity } from 'lucide-react'

export function BacktestMonitor() {
  const { state } = useBacktestContext()
  const { isRunning } = state

  // Only show if running
  if (!isRunning) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backtest Status</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-3">
          <Activity className="h-5 w-5 text-blue-500 animate-pulse" />
          <p className="text-sm font-medium">Running backtests...</p>
        </div>
      </CardContent>
    </Card>
  )
}
