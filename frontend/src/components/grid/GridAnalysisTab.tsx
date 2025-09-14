import React, { useState, useEffect } from 'react'
import { format } from 'date-fns'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { RefreshCw, BarChart2, AlertCircle } from 'lucide-react'
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

export function GridAnalysisTab() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [allData, setAllData] = useState<CombinedGridRow[]>([])

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
          const detail = await GridResultsService.getResultDetail(summary.date)
          
          // Create a map of screening results by symbol for easy lookup
          const screeningMap = new Map(
            detail.screening_results.map(s => [s.symbol, s])
          )

          // For each backtest result, create a combined row
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
        } catch (err) {
          console.error(`Failed to load details for ${summary.date}:`, err)
        }
      }

      // Sort by date (desc), symbol, then pivot_bars
      combinedData.sort((a, b) => {
        const dateCompare = b.date.localeCompare(a.date)
        if (dateCompare !== 0) return dateCompare
        const symbolCompare = a.symbol.localeCompare(b.symbol)
        if (symbolCompare !== 0) return symbolCompare
        return a.pivot_bars - b.pivot_bars
      })

      setAllData(combinedData)
    } catch (err: any) {
      setError(err.message || 'Failed to load grid results')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAllData()
  }, [])

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }

  const formatDollarVolume = (value: number) => {
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`
    return `$${(value / 1e3).toFixed(2)}K`
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart2 className="h-5 w-5" />
            Grid Analysis Results
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
            <div className="text-sm text-muted-foreground">
              Total Rows: {allData.length}
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
              <p className="text-muted-foreground">Loading all grid analysis data...</p>
            </div>
          )}

          {!loading && allData.length > 0 && (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="sticky left-0 bg-background">Date</TableHead>
                    <TableHead>Symbol</TableHead>
                    <TableHead className="text-right">Price</TableHead>
                    <TableHead className="text-right">MA 20</TableHead>
                    <TableHead className="text-right">MA 50</TableHead>
                    <TableHead className="text-right">MA 200</TableHead>
                    <TableHead className="text-right">RSI 14</TableHead>
                    <TableHead className="text-right">Gap %</TableHead>
                    <TableHead className="text-right">Prev Day $Vol</TableHead>
                    <TableHead className="text-right">Rel Vol</TableHead>
                    <TableHead className="text-center">Pivot Bars</TableHead>
                    <TableHead className="text-right">Return</TableHead>
                    <TableHead className="text-right">Sharpe</TableHead>
                    <TableHead className="text-right">Max DD</TableHead>
                    <TableHead className="text-right">Win Rate</TableHead>
                    <TableHead className="text-right">Trades</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allData.map((row, index) => (
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
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {!loading && allData.length === 0 && (
            <div className="text-center py-8">
              <p className="text-muted-foreground">No grid analysis results available</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}