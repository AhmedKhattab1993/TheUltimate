import { useState } from 'react'
import type { ReactNode } from 'react'
import { format, parseISO } from 'date-fns'
import { Eye, Trash2, TrendingUp, TrendingDown, Activity, Info, DollarSign, BarChart, Target, Settings, Clock } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useResultsContext } from '@/contexts/ResultsContext'
import { useResults } from '@/hooks/useResults'
import { Pagination } from '@/components/ui/pagination'
import { cn } from '@/lib/utils'
import { getApiUrl } from '@/services/api'

// Metric display component
interface MetricProps {
  label: string
  value: string
  isPositive?: boolean
  isNegative?: boolean
  tooltip?: string
}

function MetricCard({ label, value, isPositive, isNegative, tooltip }: MetricProps) {
  const content = (
    <Card className="h-full">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          {tooltip && (
            <Info className="h-3 w-3 text-muted-foreground" />
          )}
        </div>
        <p className={cn(
          "text-lg font-semibold",
          isPositive && "text-green-600",
          isNegative && "text-red-600"
        )}>
          {value}
        </p>
      </CardContent>
    </Card>
  )

  if (tooltip) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          {content}
        </TooltipTrigger>
        <TooltipContent>
          <p>{tooltip}</p>
        </TooltipContent>
      </Tooltip>
    )
  }

  return content
}

// Section component for grouping metrics
interface MetricsSectionProps {
  title: string
  icon: ReactNode
  metrics: MetricProps[]
}

function MetricsSection({ title, icon, metrics }: MetricsSectionProps) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h4 className="font-semibold">{title}</h4>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {metrics.map((metric, index) => (
          <MetricCard key={index} {...metric} />
        ))}
      </div>
      <Separator className="mt-6" />
    </div>
  )
}

export function BacktestResultsView() {
  const { state, dispatch } = useResultsContext()
  const { deleteBacktestResult, getBacktestResultDetails } = useResults()
  const [selectedResult, setSelectedResult] = useState<any>(null)
  const [showDetailsDialog, setShowDetailsDialog] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [trades, setTrades] = useState<any[]>([])
  const [loadingTrades, setLoadingTrades] = useState(false)

  // Safety check for undefined state
  if (!state.backtestResults) {
    return (
      <Card>
        <CardContent className="p-6">
          <p className="text-center text-muted-foreground">Loading backtest results...</p>
        </CardContent>
      </Card>
    )
  }

  const handleViewDetails = async (backtestId: string) => {
    try {
      const details = await getBacktestResultDetails(backtestId)
      setSelectedResult(details)
      setShowDetailsDialog(true)
      
      // Fetch trades for this backtest
      setLoadingTrades(true)
      try {
        const response = await fetch(`${getApiUrl()}/api/v2/backtest/db/results/${backtestId}/trades?limit=50`)
        if (response.ok) {
          const tradesData = await response.json()
          setTrades(tradesData)
        } else {
          console.error('Failed to fetch trades')
          setTrades([])
        }
      } catch (error) {
        console.error('Error fetching trades:', error)
        setTrades([])
      } finally {
        setLoadingTrades(false)
      }
    } catch (error) {
      console.error('Failed to fetch result details:', error)
    }
  }

  const handleDelete = async (backtestId: string) => {
    try {
      await deleteBacktestResult(backtestId)
      setDeleteConfirmId(null)
    } catch (error) {
      console.error('Failed to delete result:', error)
    }
  }

  // Formatting utilities
  const formatPercentage = (value: number | null | undefined, decimals = 2) => {
    if (value === null || value === undefined) return 'N/A'
    const formatted = value.toFixed(decimals)
    return value >= 0 ? `+${formatted}%` : `${formatted}%`
  }

  const formatCurrency = (value: number | null | undefined, symbol = '$') => {
    if (value === null || value === undefined) return 'N/A'
    return `${symbol}${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const formatNumber = (value: number | null | undefined, decimals = 2) => {
    if (value === null || value === undefined) return 'N/A'
    return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
  }

  const formatInteger = (value: number | null | undefined) => {
    if (value === null || value === undefined) return 'N/A'
    return value.toLocaleString('en-US')
  }

  const formatRatio = (value: number | null | undefined, decimals = 3) => {
    if (value === null || value === undefined) return 'N/A'
    return value.toFixed(decimals)
  }

  const formatReturn = (value: number | null | undefined) => {
    return formatPercentage(value)
  }

  if (state.backtestResults.loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading backtest results...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (state.backtestResults.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{state.backtestResults.error}</AlertDescription>
      </Alert>
    )
  }

  if (state.backtestResults.data.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-8 text-center">
          <Activity className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Backtest Results</h3>
          <p className="text-muted-foreground">
            Run a backtest to see results here
          </p>
        </CardContent>
      </Card>
    )
  }

  const totalPages = Math.ceil(state.backtestResults.totalCount / state.backtestResults.pageSize)

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Comprehensive Backtest Results
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Enhanced view with 40+ performance metrics organized by category
          </p>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead className="text-center">Pivots</TableHead>
                  <TableHead className="text-center">Lower TF</TableHead>
                  <TableHead className="text-center">Return</TableHead>
                  <TableHead className="text-center">Sharpe</TableHead>
                  <TableHead className="text-center">Max DD</TableHead>
                  <TableHead className="text-center">Win Rate</TableHead>
                  <TableHead className="text-center">Trades</TableHead>
                  <TableHead className="text-center">Final Value</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {state.backtestResults.data.map((result) => (
                  <TableRow key={result.backtestId}>
                    <TableCell>
                      {result.createdAt ? format(parseISO(result.createdAt), 'PP') : 'N/A'}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{result.strategyName}</Badge>
                    </TableCell>
                    <TableCell className="font-medium">
                      {result.symbol || 'N/A'}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {result.startDate && result.endDate ? 
                        `${format(parseISO(result.startDate), 'MMM dd')} - ${format(parseISO(result.endDate), 'MMM dd, yyyy')}` : 
                        'N/A'
                      }
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="font-medium">
                        {result.pivotBars || 'N/A'}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className="font-mono text-xs">
                        {result.lowerTimeframe || 'N/A'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <div className={cn(
                        "flex items-center justify-center gap-1 font-medium",
                        (result.statistics?.totalReturn ?? 0) >= 0 ? "text-green-600" : "text-red-600"
                      )}>
                        {(result.statistics?.totalReturn ?? 0) >= 0 ? (
                          <TrendingUp className="h-4 w-4" />
                        ) : (
                          <TrendingDown className="h-4 w-4" />
                        )}
                        {formatReturn(result.statistics?.totalReturn)}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <span className={cn(
                        "font-medium",
                        (result.statistics?.sharpeRatio ?? 0) >= 0 ? "text-green-600" : "text-red-600"
                      )}>
                        {formatRatio(result.statistics?.sharpeRatio)}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="text-red-600 font-medium">
                        {formatPercentage(result.statistics?.maxDrawdown)}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="font-medium">
                        {formatPercentage(result.statistics?.winRate, 1)}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      {formatInteger(result.statistics?.totalTrades)}
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="font-medium">
                        {formatCurrency(result.finalValue || result.statistics?.endEquity)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewDetails(result.backtestId)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteConfirmId(result.backtestId)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {totalPages > 1 && (
            <div className="mt-4">
              <Pagination
                currentPage={state.backtestResults.page}
                totalPages={totalPages}
                onPageChange={(page) => dispatch({ type: 'SET_BACKTEST_PAGE', page })}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Details Dialog */}
      <Dialog open={showDetailsDialog} onOpenChange={(open) => {
        setShowDetailsDialog(open)
        if (!open) {
          setTrades([])  // Clear trades when dialog closes
        }
      }}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Backtest Result Details</DialogTitle>
            <DialogDescription>
              {selectedResult && (
                <>
                  {selectedResult.strategyName || selectedResult.strategy_name || 'Unknown Strategy'} • 
                  {(selectedResult.startDate || selectedResult.start_date) && (selectedResult.endDate || selectedResult.end_date) ? 
                    `${format(parseISO(selectedResult.startDate || selectedResult.start_date), 'PP')} - ${format(parseISO(selectedResult.endDate || selectedResult.end_date), 'PP')}` :
                    'Date not available'
                  }
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          {selectedResult && (
            <TooltipProvider>
              <div className="space-y-6">
                {/* Core Performance Results */}
                <MetricsSection 
                  title="Core Performance Results" 
                  icon={<DollarSign className="h-4 w-4" />}
                  metrics={[
                    { label: 'Total Return', value: formatPercentage(selectedResult.statistics?.totalReturn), isPositive: (selectedResult.statistics?.totalReturn ?? 0) >= 0 },
                    { label: 'Net Profit', value: formatPercentage(selectedResult.statistics?.netProfit), isPositive: (selectedResult.statistics?.netProfit ?? 0) >= 0 },
                    { label: 'Net Profit ($)', value: formatCurrency(selectedResult.statistics?.netProfitCurrency), isPositive: (selectedResult.statistics?.netProfitCurrency ?? 0) >= 0 },
                    { label: 'Compounding Annual Return', value: formatPercentage(selectedResult.statistics?.compoundingAnnualReturn), isPositive: (selectedResult.statistics?.compoundingAnnualReturn ?? 0) >= 0 },
                    { label: 'Final Value', value: formatCurrency(selectedResult.finalValue || selectedResult.statistics?.endEquity) },
                    { label: 'Start Equity', value: formatCurrency(selectedResult.statistics?.startEquity) },
                    { label: 'End Equity', value: formatCurrency(selectedResult.statistics?.endEquity) }
                  ]}
                />

                {/* Risk Metrics */}
                <MetricsSection 
                  title="Risk Metrics" 
                  icon={<BarChart className="h-4 w-4" />}
                  metrics={[
                    { label: 'Sharpe Ratio', value: formatRatio(selectedResult.statistics?.sharpeRatio), tooltip: 'Risk-adjusted return measure' },
                    { label: 'Sortino Ratio', value: formatRatio(selectedResult.statistics?.sortinoRatio), tooltip: 'Risk-adjusted return using downside deviation' },
                    { label: 'Max Drawdown', value: formatPercentage(selectedResult.statistics?.maxDrawdown), isNegative: true, tooltip: 'Maximum peak-to-trough decline' },
                    { label: 'Probabilistic Sharpe Ratio', value: formatPercentage(selectedResult.statistics?.probabilisticSharpeRatio), tooltip: 'Probability that Sharpe ratio is above threshold' },
                    { label: 'Annual Standard Deviation', value: formatNumber(selectedResult.statistics?.annualStandardDeviation), tooltip: 'Annualized volatility' },
                    { label: 'Annual Variance', value: formatNumber(selectedResult.statistics?.annualVariance), tooltip: 'Annualized variance of returns' },
                    { label: 'Beta', value: formatRatio(selectedResult.statistics?.beta), tooltip: 'Sensitivity to market movements' },
                    { label: 'Alpha', value: formatRatio(selectedResult.statistics?.alpha), tooltip: 'Excess return over expected market return' }
                  ]}
                />

                {/* Trading Statistics */}
                <MetricsSection 
                  title="Trading Statistics" 
                  icon={<Target className="h-4 w-4" />}
                  metrics={[
                    { label: 'Total Orders', value: formatInteger(selectedResult.statistics?.totalOrders) },
                    { label: 'Total Trades', value: formatInteger(selectedResult.statistics?.totalTrades) },
                    { label: 'Winning Trades', value: formatInteger(selectedResult.statistics?.winningTrades) },
                    { label: 'Losing Trades', value: formatInteger(selectedResult.statistics?.losingTrades) },
                    { label: 'Win Rate', value: formatPercentage(selectedResult.statistics?.winRate, 1) },
                    { label: 'Loss Rate', value: formatPercentage(selectedResult.statistics?.lossRate, 1) },
                    { label: 'Average Win', value: formatPercentage(selectedResult.statistics?.averageWin) },
                    { label: 'Average Loss', value: formatPercentage(selectedResult.statistics?.averageLoss) },
                    { label: 'Profit Factor', value: formatRatio(selectedResult.statistics?.profitFactor), tooltip: 'Gross profit divided by gross loss' },
                    { label: 'Profit-Loss Ratio', value: formatRatio(selectedResult.statistics?.profitLossRatio), tooltip: 'Average win divided by average loss' },
                    { label: 'Expectancy', value: formatPercentage(selectedResult.statistics?.expectancy), tooltip: 'Expected value per trade' }
                  ]}
                />

                {/* Advanced Metrics */}
                <MetricsSection 
                  title="Advanced Metrics" 
                  icon={<Activity className="h-4 w-4" />}
                  metrics={[
                    { label: 'Information Ratio', value: formatRatio(selectedResult.statistics?.informationRatio), tooltip: 'Active return divided by tracking error' },
                    { label: 'Tracking Error', value: formatNumber(selectedResult.statistics?.trackingError), tooltip: 'Standard deviation of excess returns' },
                    { label: 'Treynor Ratio', value: formatRatio(selectedResult.statistics?.treynorRatio), tooltip: 'Risk-adjusted return using beta' },
                    { label: 'Total Fees', value: formatCurrency(selectedResult.statistics?.totalFees) },
                    { label: 'Estimated Strategy Capacity', value: formatCurrency(selectedResult.statistics?.estimatedStrategyCapacity), tooltip: 'Maximum capital strategy can handle' },
                    { label: 'Lowest Capacity Asset', value: selectedResult.statistics?.lowestCapacityAsset || 'N/A' },
                    { label: 'Portfolio Turnover', value: formatPercentage(selectedResult.statistics?.portfolioTurnover), tooltip: 'Rate of trading activity' }
                  ]}
                />

                {/* Strategy-Specific Metrics */}
                {(selectedResult.statistics?.pivotHighsDetected || selectedResult.statistics?.pivotLowsDetected || selectedResult.statistics?.bosSignalsGenerated) && (
                  <MetricsSection 
                    title="Strategy-Specific Metrics" 
                    icon={<TrendingUp className="h-4 w-4" />}
                    metrics={[
                      { label: 'Pivot Highs Detected', value: formatInteger(selectedResult.statistics?.pivotHighsDetected) },
                      { label: 'Pivot Lows Detected', value: formatInteger(selectedResult.statistics?.pivotLowsDetected) },
                      { label: 'Break of Structure Signals', value: formatInteger(selectedResult.statistics?.bosSignalsGenerated) },
                      { label: 'Position Flips', value: formatInteger(selectedResult.statistics?.positionFlips) },
                      { label: 'Liquidation Events', value: formatInteger(selectedResult.statistics?.liquidationEvents) }
                    ]}
                  />
                )}

                {/* Algorithm Parameters */}
                <MetricsSection 
                  title="Algorithm Parameters" 
                  icon={<Settings className="h-4 w-4" />}
                  metrics={[
                    { label: 'Initial Cash', value: formatCurrency(selectedResult.initialCash) },
                    { label: 'Resolution', value: selectedResult.resolution || 'N/A' },
                    { label: 'Pivot Bars', value: formatInteger(selectedResult.pivotBars) },
                    { label: 'Lower Timeframe', value: selectedResult.lowerTimeframe || 'N/A' }
                  ]}
                />

                {/* Execution Metadata */}
                <MetricsSection 
                  title="Execution Metadata" 
                  icon={<Clock className="h-4 w-4" />}
                  metrics={[
                    { label: 'Execution Time', value: selectedResult.executionTimeMs ? `${selectedResult.executionTimeMs}ms` : 'N/A' },
                    { label: 'Status', value: selectedResult.status || 'N/A' },
                    { label: 'Cache Hit', value: selectedResult.cacheHit !== undefined ? (selectedResult.cacheHit ? 'Yes' : 'No') : 'N/A' },
                    { label: 'Created At', value: selectedResult.createdAt ? format(parseISO(selectedResult.createdAt), 'PPpp') : 'N/A' }
                  ]}
                />

                {/* Equity Curve */}
                {selectedResult?.equityCurve && Array.isArray(selectedResult.equityCurve) && selectedResult.equityCurve.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp className="h-4 w-4" />
                      <h4 className="font-semibold">Equity Curve</h4>
                    </div>
                    <Card>
                      <CardContent className="p-4">
                        <p className="text-sm text-muted-foreground">
                          {selectedResult.equityCurve.length} data points available
                        </p>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* Trades Table */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Activity className="h-4 w-4" />
                    <h4 className="font-semibold">Trade History</h4>
                    {trades.length > 0 && (
                      <span className="text-sm text-muted-foreground">
                        (Showing last {trades.length} trades)
                      </span>
                    )}
                  </div>
                  <Card>
                    <CardContent className="p-0">
                      {loadingTrades ? (
                        <div className="p-8 text-center">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
                          <p className="text-muted-foreground">Loading trades...</p>
                        </div>
                      ) : trades.length === 0 ? (
                        <div className="p-8 text-center text-muted-foreground">
                          No trades available for this backtest
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead className="w-12">#</TableHead>
                                <TableHead>Time (ET)</TableHead>
                                <TableHead>Symbol</TableHead>
                                <TableHead className="text-center">Direction</TableHead>
                                <TableHead className="text-right">Quantity</TableHead>
                                <TableHead className="text-right">Fill Price</TableHead>
                                <TableHead className="text-right">Value</TableHead>
                                <TableHead className="text-right">Fee</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {trades.map((trade, index) => {
                                const tradeValue = trade.fillQuantity * trade.fillPrice
                                return (
                                  <TableRow key={index}>
                                    <TableCell className="font-mono text-xs text-muted-foreground">
                                      {index + 1}
                                    </TableCell>
                                    <TableCell className="font-mono text-sm">
                                      {format(parseISO(trade.tradeTime), 'HH:mm:ss')}
                                    </TableCell>
                                    <TableCell className="font-medium">
                                      {trade.symbol}
                                    </TableCell>
                                    <TableCell className="text-center">
                                      <Badge 
                                        variant={trade.direction === 'buy' ? 'default' : 'secondary'}
                                        className={cn(
                                          "text-xs",
                                          trade.direction === 'buy' ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                                        )}
                                      >
                                        {trade.direction.toUpperCase()}
                                      </Badge>
                                    </TableCell>
                                    <TableCell className="text-right font-mono">
                                      {trade.quantity.toLocaleString()}
                                    </TableCell>
                                    <TableCell className="text-right font-mono">
                                      ${trade.fillPrice.toFixed(2)}
                                    </TableCell>
                                    <TableCell className="text-right font-mono">
                                      ${tradeValue.toFixed(2)}
                                    </TableCell>
                                    <TableCell className="text-right font-mono text-muted-foreground">
                                      ${trade.orderFee.toFixed(2)}
                                    </TableCell>
                                  </TableRow>
                                )
                              })}
                            </TableBody>
                          </Table>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </TooltipProvider>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Backtest Result?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The backtest result will be permanently deleted.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
