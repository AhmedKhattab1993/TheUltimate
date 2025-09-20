import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useBacktestContext } from '@/contexts/BacktestContext'
import { Activity, BarChart3, History } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { format } from 'date-fns'

export function BacktestResults() {
  const { state } = useBacktestContext()
  const { currentResult, historicalResults } = state
  const [selectedHistoricalResult, setSelectedHistoricalResult] = useState<string | null>(null)

  const displayResult = selectedHistoricalResult
    ? historicalResults.find((result) => {
        const timestamp = result.backtestId || result.backtest_id || result.timestamp
        const strategyName = result.strategyName || result.strategy_name
        const displayName = strategyName ? `${strategyName} - ${timestamp}` : timestamp
        return displayName === selectedHistoricalResult
      }) ?? null
    : currentResult

  const filledOrders = displayResult?.orders?.filter((order: any) => order.status === 'filled' || order.status === 'Filled') || []

  if (!displayResult && historicalResults.length === 0) {
    return null
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value)
  }

  const formatPrice = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value)
  }

  const formatPercent = (value: number) => {
    if (value === null || value === undefined || isNaN(value)) {
      return '0.00%'
    }
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }

  const formatEasternTime = (timestamp: number) => {
    const date = new Date(timestamp * 1000)
    return date.toLocaleString('en-US', {
      timeZone: 'America/New_York',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
  }

  return (
    <div className="space-y-6">
      {/* Results Selector */}
      {historicalResults.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Backtest History
            </CardTitle>
            <CardDescription>
              View current or historical backtest results
            </CardDescription>
          </CardHeader>
          <CardContent>
            <select
              value={selectedHistoricalResult || ''}
              onChange={(e) => setSelectedHistoricalResult(e.target.value || null)}
              className="w-full p-2 border rounded-md"
            >
              <option value="">Current Result</option>
              {historicalResults.map((result) => {
                // Handle both snake_case and camelCase
                const timestamp = result.backtestId || result.backtest_id || result.timestamp;
                const strategyName = result.strategyName || result.strategy_name;
                const displayName = strategyName ? `${strategyName} - ${timestamp}` : timestamp;
                
                return (
                  <option key={timestamp} value={displayName}>
                    {displayName}
                  </option>
                );
              })}
            </select>
          </CardContent>
        </Card>
      )}

      {displayResult && (
        <Tabs defaultValue="statistics" className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="statistics">Statistics</TabsTrigger>
            <TabsTrigger value="equity">Equity Curve</TabsTrigger>
            <TabsTrigger value="orders">Orders</TabsTrigger>
          </TabsList>

          <TabsContent value="statistics">
            <Card>
              <CardHeader>
                <CardTitle>Performance Statistics</CardTitle>
                <CardDescription>
                  Key metrics from the backtest
                </CardDescription>
              </CardHeader>
              <CardContent>
                {displayResult ? (
                <div className="space-y-6">
                  {/* Key Performance Statistics */}
                  <div>
                    <h3 className="text-sm font-semibold text-muted-foreground mb-3">BACKTEST STATISTICS</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1">
                      <div className="flex justify-between py-1 border-b border-gray-100">
                        <span className="text-sm text-muted-foreground">Total Return</span>
                        <span className={`text-sm font-semibold ${displayResult.statistics.totalReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {formatPercent(displayResult.statistics.totalReturn)}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-gray-100">
                        <span className="text-sm text-muted-foreground">Sharpe Ratio</span>
                        <span className="text-sm font-semibold">
                          {displayResult.statistics.sharpeRatio?.toFixed(3) || '0.000'}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-gray-100">
                        <span className="text-sm text-muted-foreground">Max Drawdown</span>
                        <span className="text-sm font-semibold text-red-600">
                          {formatPercent(displayResult.statistics.maxDrawdown)}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-gray-100">
                        <span className="text-sm text-muted-foreground">Total Orders</span>
                        <span className="text-sm font-semibold">
                          {displayResult.statistics.totalOrders || displayResult.statistics.totalTrades || 0}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-gray-100">
                        <span className="text-sm text-muted-foreground">Win Rate</span>
                        <span className="text-sm font-semibold text-green-600">
                          {formatPercent(displayResult.statistics.winRate)}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-gray-100">
                        <span className="text-sm text-muted-foreground">Loss Rate</span>
                        <span className="text-sm font-semibold text-red-600">
                          {formatPercent(displayResult.statistics.lossRate || (100 - displayResult.statistics.winRate))}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-gray-100">
                        <span className="text-sm text-muted-foreground">Average Win</span>
                        <span className="text-sm font-semibold text-green-600">
                          {formatPercent(displayResult.statistics.averageWin)}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-gray-100">
                        <span className="text-sm text-muted-foreground">Average Loss</span>
                        <span className="text-sm font-semibold text-red-600">
                          {formatPercent(displayResult.statistics.averageLoss)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
                ) : null}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="equity">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Equity Curve
                </CardTitle>
                <CardDescription>
                  Portfolio value over time
                </CardDescription>
              </CardHeader>
              <CardContent>
                {displayResult && displayResult.equityCurve?.length ? (
                  <div className="h-[400px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={displayResult.equityCurve}
                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="time"
                          tickFormatter={(value) => format(new Date(value * 1000), 'MMM dd')}
                        />
                        <YAxis tickFormatter={(value) => formatCurrency(value)} />
                        <Tooltip
                          formatter={(value: number) => formatCurrency(value)}
                          labelFormatter={(label) => format(new Date(label * 1000), 'PPP')}
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke="#8884d8"
                          name="Portfolio Value"
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="orders">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Order History
                </CardTitle>
                <CardDescription>
                  All trades executed during the backtest
                </CardDescription>
              </CardHeader>
              <CardContent>
                {filledOrders.length ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Time</TableHead>
                          <TableHead>Symbol</TableHead>
                          <TableHead>Direction</TableHead>
                          <TableHead>Quantity</TableHead>
                          <TableHead>Fill Price</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filledOrders.map((order: any, index: number) => (
                          <TableRow key={`${order.time}-${order.symbol}-${index}`}>
                            <TableCell className="font-mono text-xs">
                              {formatEasternTime(order.time)}
                            </TableCell>
                            <TableCell className="font-medium">{order.symbolValue || order.symbol}</TableCell>
                            <TableCell>{order.direction}</TableCell>
                            <TableCell>{order.fillQuantity || order.quantity}</TableCell>
                            <TableCell>{formatPrice(order.fillPrice || 0)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <div className="flex items-center justify-center py-8 text-muted-foreground">
                    No filled orders found
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
