import React, { useState, useEffect } from 'react'
import { format, parseISO } from 'date-fns'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { RefreshCw, BarChart2, AlertCircle, Eye, ChevronLeft, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { GridResultsService } from '@/services/gridResults'
import type { GridResultSummary, GridResultDetail } from '@/types/gridResults'

interface CombinedGridRow {
  date: string
  symbol: string
  // Screening data
  price: number
  ma_20: number
  ma_50: number
  ma_200: number
  rsi_14: number
  gap_percent: number
  prev_day_dollar_volume: number
  relative_volume: number
  // Backtest data (for specific pivot_bars)
  pivot_bars: number
  total_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  backtest_status: string
}

export function GridBacktestResultsTab() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [allData, setAllData] = useState<CombinedGridRow[]>([])
  
  // Sorting state
  const [sortBy, setSortBy] = useState<string | null>(null)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 100
  
  // Trades dialog state
  const [showTradesDialog, setShowTradesDialog] = useState(false)
  const [selectedTrade, setSelectedTrade] = useState<{ symbol: string, date: string, pivotBars: number } | null>(null)
  const [trades, setTrades] = useState<any[]>([])
  const [loadingTrades, setLoadingTrades] = useState(false)

  // Load all grid results and combine them into a single table
  const loadAllData = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await GridResultsService.listResults()
      const combinedData: CombinedGridRow[] = []

      // For each date, load detailed results
      for (const summary of response.results) {
        try {
          const detail = await GridResultsService.getResultDetail(
            summary.date,
            undefined, // no symbol filter
            sortBy || undefined,
            sortOrder
          )
          
          // Determine whether we're sorting by a screening column or backtest column
          const screeningColumns = ['symbol', 'date', 'price', 'ma_20', 'ma_50', 'ma_200', 
                                   'rsi_14', 'gap_percent', 'prev_day_dollar_volume', 'relative_volume']
          const isScreeningSort = sortBy && screeningColumns.includes(sortBy)

          if (isScreeningSort) {
            // When sorting by screening columns, iterate through screening results
            // to preserve the sort order from the API
            const backtestMap = new Map<string, typeof detail.backtest_results[0][]>()
            detail.backtest_results.forEach(b => {
              if (!backtestMap.has(b.symbol)) {
                backtestMap.set(b.symbol, [])
              }
              backtestMap.get(b.symbol)!.push(b)
            })

            for (const screening of detail.screening_results) {
              const backtests = backtestMap.get(screening.symbol) || []
              // Sort backtests by pivot_bars to maintain consistent order within each symbol
              backtests.sort((a, b) => a.pivot_bars - b.pivot_bars)
              for (const backtest of backtests) {
                combinedData.push({
                  date: summary.date,
                  symbol: screening.symbol,
                  // Screening data
                  price: screening.price,
                  ma_20: screening.ma_20,
                  ma_50: screening.ma_50,
                  ma_200: screening.ma_200,
                  rsi_14: screening.rsi_14,
                  gap_percent: screening.gap_percent,
                  prev_day_dollar_volume: screening.prev_day_dollar_volume,
                  relative_volume: screening.relative_volume,
                  // Backtest data
                  pivot_bars: backtest.pivot_bars,
                  total_return: backtest.total_return,
                  sharpe_ratio: backtest.sharpe_ratio,
                  max_drawdown: backtest.max_drawdown,
                  win_rate: backtest.win_rate,
                  total_trades: backtest.total_trades,
                  backtest_status: backtest.status,
                })
              }
            }
          } else {
            // When sorting by backtest columns or no sort, iterate through backtest results
            // to preserve the sort order from the API
            const screeningMap = new Map(
              detail.screening_results.map(s => [s.symbol, s])
            )

            for (const backtest of detail.backtest_results) {
              const screening = screeningMap.get(backtest.symbol)
              if (screening) {
                combinedData.push({
                  date: summary.date,
                  symbol: backtest.symbol,
                  // Screening data
                  price: screening.price,
                  ma_20: screening.ma_20,
                  ma_50: screening.ma_50,
                  ma_200: screening.ma_200,
                  rsi_14: screening.rsi_14,
                  gap_percent: screening.gap_percent,
                  prev_day_dollar_volume: screening.prev_day_dollar_volume,
                  relative_volume: screening.relative_volume,
                  // Backtest data
                  pivot_bars: backtest.pivot_bars,
                  total_return: backtest.total_return,
                  sharpe_ratio: backtest.sharpe_ratio,
                  max_drawdown: backtest.max_drawdown,
                  win_rate: backtest.win_rate,
                  total_trades: backtest.total_trades,
                  backtest_status: backtest.status,
                })
              }
            }
          }
        } catch (err) {
          console.error(`Failed to load details for ${summary.date}:`, err)
        }
      }

      // If no server-side sorting is applied, default sort by date (desc), symbol, then pivot_bars
      if (!sortBy) {
        combinedData.sort((a, b) => {
          const dateCompare = b.date.localeCompare(a.date)
          if (dateCompare !== 0) return dateCompare
          const symbolCompare = a.symbol.localeCompare(b.symbol)
          if (symbolCompare !== 0) return symbolCompare
          return a.pivot_bars - b.pivot_bars
        })
      }

      setAllData(combinedData)
      setCurrentPage(1) // Reset to first page when new data is loaded
    } catch (err: any) {
      setError(err.message || 'Failed to load grid results')
    } finally {
      setLoading(false)
    }
  }

  // Calculate pagination values
  const totalPages = Math.ceil(allData.length / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const paginatedData = allData.slice(startIndex, endIndex)

  useEffect(() => {
    loadAllData()
  }, [sortBy, sortOrder])
  
  // Handle column header clicks for sorting
  const handleSort = (column: string) => {
    if (sortBy === column) {
      // Toggle sort order if clicking the same column
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      // Set new column and default to descending
      setSortBy(column)
      setSortOrder('desc')
    }
  }
  
  // Helper component for sortable table headers
  const SortableHeader = ({ column, children }: { column: string, children: React.ReactNode }) => {
    const isSorted = sortBy === column
    const isCenter = column === 'pivot_bars'
    const isLeft = column === 'symbol' || column === 'date'
    
    return (
      <TableHead 
        className={cn(
          "cursor-pointer hover:bg-muted/50 select-none", 
          isCenter ? 'text-center' : isLeft ? '' : 'text-right',
          column === 'date' ? 'sticky left-0 bg-background' : ''
        )}
        onClick={() => handleSort(column)}
      >
        <div className={cn(
          "flex items-center gap-1",
          isCenter ? 'justify-center' : isLeft ? '' : 'justify-end'
        )}>
          <span>{children}</span>
          {isSorted ? (
            sortOrder === 'asc' ? (
              <ArrowUp className="h-4 w-4" />
            ) : (
              <ArrowDown className="h-4 w-4" />
            )
          ) : (
            <ArrowUpDown className="h-4 w-4 opacity-50" />
          )}
        </div>
      </TableHead>
    )
  }

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }

  const formatDollarVolume = (value: number) => {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`
    return `$${(value / 1e3).toFixed(2)}K`
  }
  
  // Function to view trades
  const handleViewTrades = async (symbol: string, date: string, pivotBars: number) => {
    setSelectedTrade({ symbol, date, pivotBars })
    setShowTradesDialog(true)
    setLoadingTrades(true)
    
    try {
      const tradesData = await GridResultsService.getSymbolPivotTrades(date, symbol, pivotBars)
      setTrades(tradesData)
    } catch (error) {
      console.error('Failed to fetch trades:', error)
      setTrades([])
    } finally {
      setLoadingTrades(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart2 className="h-5 w-5" />
            Grid Backtest Results
          </CardTitle>
          <CardDescription>
            Combined screening and backtest results for all symbols across all dates
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex justify-between items-center mb-4">
            <Button onClick={loadAllData} disabled={loading} variant="outline">
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <div className="flex items-center gap-4">
              <div className="text-sm text-muted-foreground">
                Total Rows: {allData.length}
              </div>
              {totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    variant="outline"
                    size="sm"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <div className="text-sm text-muted-foreground">
                    Page {currentPage} of {totalPages}
                  </div>
                  <Button
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    variant="outline"
                    size="sm"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          </div>

          {error && (
            <Alert className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading && (
            <div className="text-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
              <p className="text-muted-foreground">Loading all grid backtest results...</p>
            </div>
          )}

          {!loading && allData.length > 0 && (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <SortableHeader column="date">Date</SortableHeader>
                    <SortableHeader column="symbol">Symbol</SortableHeader>
                    <SortableHeader column="price">Price</SortableHeader>
                    <SortableHeader column="ma_20">MA 20</SortableHeader>
                    <SortableHeader column="ma_50">MA 50</SortableHeader>
                    <SortableHeader column="ma_200">MA 200</SortableHeader>
                    <SortableHeader column="rsi_14">RSI 14</SortableHeader>
                    <SortableHeader column="gap_percent">Gap %</SortableHeader>
                    <SortableHeader column="prev_day_dollar_volume">Prev Day $Vol</SortableHeader>
                    <SortableHeader column="relative_volume">Rel Vol</SortableHeader>
                    <SortableHeader column="pivot_bars">Pivot Bars</SortableHeader>
                    <SortableHeader column="total_return">Return</SortableHeader>
                    <SortableHeader column="sharpe_ratio">Sharpe</SortableHeader>
                    <SortableHeader column="max_drawdown">Max DD</SortableHeader>
                    <SortableHeader column="win_rate">Win Rate</SortableHeader>
                    <SortableHeader column="total_trades">Trades</SortableHeader>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedData.map((row, index) => (
                    <TableRow key={`${row.date}_${row.symbol}_${row.pivot_bars}_${index}`}>
                      <TableCell className="sticky left-0 bg-background font-medium">
                        {format(new Date(row.date), 'MMM d, yyyy')}
                      </TableCell>
                      <TableCell className="font-medium">{row.symbol}</TableCell>
                      <TableCell className="text-right">{row.price != null ? `$${row.price.toFixed(2)}` : '-'}</TableCell>
                      <TableCell className="text-right">{row.ma_20 != null ? `$${row.ma_20.toFixed(2)}` : '-'}</TableCell>
                      <TableCell className="text-right">{row.ma_50 != null ? `$${row.ma_50.toFixed(2)}` : '-'}</TableCell>
                      <TableCell className="text-right">{row.ma_200 != null ? `$${row.ma_200.toFixed(2)}` : '-'}</TableCell>
                      <TableCell className="text-right">
                        {row.rsi_14 != null ? (
                          <Badge variant={row.rsi_14 > 70 ? 'destructive' : row.rsi_14 < 30 ? 'default' : 'secondary'}>
                            {row.rsi_14.toFixed(1)}
                          </Badge>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        {row.gap_percent != null ? (
                          <span className={row.gap_percent >= 0 ? 'text-green-600' : 'text-red-600'}>
                            {formatPercent(row.gap_percent)}
                          </span>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        {row.prev_day_dollar_volume != null ? formatDollarVolume(row.prev_day_dollar_volume) : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        {row.relative_volume != null ? (
                          <Badge variant={row.relative_volume > 1.5 ? 'default' : 'secondary'}>
                            {row.relative_volume.toFixed(2)}x
                          </Badge>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline">{row.pivot_bars}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {row.total_return != null ? (
                          <span className={row.total_return >= 0 ? 'text-green-600' : 'text-red-600'}>
                            {formatPercent(row.total_return)}
                          </span>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-right">{row.sharpe_ratio != null ? row.sharpe_ratio.toFixed(2) : '-'}</TableCell>
                      <TableCell className="text-right text-red-600">
                        {row.max_drawdown != null ? formatPercent(row.max_drawdown) : '-'}
                      </TableCell>
                      <TableCell className="text-right">{row.win_rate != null ? `${row.win_rate.toFixed(1)}%` : '-'}</TableCell>
                      <TableCell className="text-right">{row.total_trades != null ? row.total_trades : '-'}</TableCell>
                      <TableCell className="text-right">
                        {row.total_trades && row.total_trades > 0 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewTrades(row.symbol, row.date, row.pivot_bars)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          
          {/* Pagination controls at bottom */}
          {!loading && allData.length > itemsPerPage && (
            <div className="flex justify-center items-center gap-2 mt-4">
              <Button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                variant="outline"
                size="sm"
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              <div className="text-sm text-muted-foreground px-4">
                Page {currentPage} of {totalPages} | Showing {startIndex + 1}-{Math.min(endIndex, allData.length)} of {allData.length} results
              </div>
              <Button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                variant="outline"
                size="sm"
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}

          {!loading && allData.length === 0 && (
            <div className="text-center py-8">
              <p className="text-muted-foreground">No grid backtest results available</p>
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* Trades Dialog - exactly like in CombinedResultsView */}
      <Dialog open={showTradesDialog} onOpenChange={(open) => {
        setShowTradesDialog(open)
        if (!open) {
          setTrades([])
          setSelectedTrade(null)
        }
      }}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Trade History</DialogTitle>
            <DialogDescription>
              {selectedTrade && trades.length > 0 && (
                <span>
                  Showing {trades.length} trades for {selectedTrade.symbol} 
                  (Pivot Bars: {selectedTrade.pivotBars})
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          
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
                        <TableHead className="text-center">Type</TableHead>
                        <TableHead>Signal</TableHead>
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
                            <TableCell className="text-center">
                              <Badge variant="outline" className="text-xs">
                                {trade.tradeType || 'entry'}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground">
                              {trade.signalReason || '-'}
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
        </DialogContent>
      </Dialog>
    </div>
  )
}