import React, { useState, useEffect, useMemo } from 'react'
import { format, parseISO } from 'date-fns'
import { Eye, Download, Filter, BarChart } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { useResultsContext } from '@/contexts/ResultsContext'
import { Pagination } from '@/components/ui/pagination'
import { cn } from '@/lib/utils'
import { getApiUrl } from '@/services/api'

interface CombinedResult {
  // Screener columns - ONLY columns from ScreenerResultsView table
  screener_session_id?: string
  screened_at?: string  // Created Date column in screener results
  screening_date?: string  // Screening Date column
  source?: string
  symbol: string
  company_name?: string
  
  // Screener Filter columns (as shown in the screener table)
  filter_min_price?: number
  filter_max_price?: number
  filter_price_vs_ma_enabled?: boolean
  filter_price_vs_ma_period?: number
  filter_price_vs_ma_condition?: string
  filter_rsi_enabled?: boolean
  filter_rsi_period?: number
  filter_rsi_threshold?: number
  filter_rsi_condition?: string
  filter_gap_enabled?: boolean
  filter_gap_threshold?: number
  filter_gap_direction?: string
  filter_prev_day_dollar_volume_enabled?: boolean
  filter_prev_day_dollar_volume?: number
  filter_relative_volume_enabled?: boolean
  filter_relative_volume_min_ratio?: number
  
  // Backtest columns - ONLY columns from BacktestResultsView table
  backtest_id?: string
  backtest_created_at?: string  // Date column in backtest results
  strategy_name?: string  // Strategy column
  backtest_start_date?: string
  backtest_end_date?: string
  pivot_bars?: number
  lower_timeframe?: string
  total_return?: number
  sharpe_ratio?: number
  max_drawdown?: number
  win_rate?: number
  total_trades?: number
  final_value?: number
}

export function CombinedResultsView() {
  const { state, dispatch } = useResultsContext()
  const [results, setResults] = useState<CombinedResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [totalCount, setTotalCount] = useState(0)
  
  // Filters
  const [sessionFilter, setSessionFilter] = useState<string>('')
  const [symbolFilter, setSymbolFilter] = useState<string>('')
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const limit = 50

  // Fetch combined results
  const fetchResults = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: ((currentPage - 1) * limit).toString()
      })
      
      if (sessionFilter) params.append('session_id', sessionFilter)
      if (symbolFilter) params.append('symbol', symbolFilter)
      if (sourceFilter !== 'all') params.append('source', sourceFilter)
      
      const response = await fetch(`${getApiUrl()}/api/v2/combined-results?${params}`)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch combined results: ${response.statusText}`)
      }
      
      const data = await response.json()
      setResults(data.results)
      setTotalCount(data.total_count)
    } catch (err) {
      console.error('Error fetching combined results:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch results')
    } finally {
      setLoading(false)
    }
  }

  // Fetch on mount and when filters change
  useEffect(() => {
    fetchResults()
  }, [currentPage, sessionFilter, symbolFilter, sourceFilter])

  // Calculate summary statistics
  const summaryStats = useMemo(() => {
    if (!results.length) return null
    
    const withBacktests = results.filter(r => r.total_return !== null && r.total_return !== undefined)
    if (!withBacktests.length) return null
    
    const returns = withBacktests.map(r => r.total_return || 0)
    const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length
    const positiveReturns = returns.filter(r => r > 0).length
    const winRate = (positiveReturns / returns.length) * 100
    
    return {
      totalSymbols: new Set(results.map(r => r.symbol)).size,
      totalBacktests: withBacktests.length,
      avgReturn: avgReturn.toFixed(2),
      winRate: winRate.toFixed(1),
      bestReturn: Math.max(...returns).toFixed(2),
      worstReturn: Math.min(...returns).toFixed(2)
    }
  }, [results])

  // Export to CSV
  const exportToCSV = () => {
    const headers = [
      // Screener columns
      'Created Date', 'Screening Date', 'Symbol', 'Source',
      'Price Range', 'Price vs MA', 'RSI', 'Gap', 'Volume', 'Rel Vol',
      // Backtest columns
      'Date', 'Strategy', 'Period', 'Pivots', 'Lower TF',
      'Return', 'Sharpe', 'Max DD', 'Win Rate', 
      'Trades', 'Final Value'
    ]
    
    const csvData = results.map(r => [
      // Screener data
      r.screened_at || '',
      r.screening_date || '',
      r.symbol,
      r.source || '',
      r.filter_min_price && r.filter_max_price ? `$${r.filter_min_price}-${r.filter_max_price}` : '',
      r.filter_price_vs_ma_enabled ? `${r.filter_price_vs_ma_condition || ''} MA${r.filter_price_vs_ma_period || ''}` : '',
      r.filter_rsi_enabled ? `${r.filter_rsi_condition || ''} ${r.filter_rsi_threshold || ''}` : '',
      r.filter_gap_enabled ? `${r.filter_gap_threshold || ''}% ${r.filter_gap_direction || ''}` : '',
      r.filter_prev_day_dollar_volume_enabled ? `$${(r.filter_prev_day_dollar_volume || 0) / 1000000}M` : '',
      r.filter_relative_volume_enabled ? `${r.filter_relative_volume_min_ratio || ''}x` : '',
      // Backtest data
      r.backtest_created_at || '',
      r.strategy_name || '',
      r.backtest_start_date && r.backtest_end_date ? 
        `${r.backtest_start_date} - ${r.backtest_end_date}` : '',
      r.pivot_bars || '',
      r.lower_timeframe || '',
      r.total_return?.toFixed(2) || '',
      r.sharpe_ratio?.toFixed(3) || '',
      r.max_drawdown?.toFixed(2) || '',
      r.win_rate?.toFixed(1) || '',
      r.total_trades || '',
      r.final_value || ''
    ])
    
    const csv = [
      headers.join(','),
      ...csvData.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')
    
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `combined_results_${format(new Date(), 'yyyy-MM-dd_HH-mm')}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
  }

  const totalPages = Math.ceil(totalCount / limit)

  return (
    <div className="space-y-6">
      {/* Summary Statistics */}
      {summaryStats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Total Symbols</p>
              <p className="text-2xl font-bold">{summaryStats.totalSymbols}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Total Backtests</p>
              <p className="text-2xl font-bold">{summaryStats.totalBacktests}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Avg Return</p>
              <p className={cn(
                "text-2xl font-bold",
                parseFloat(summaryStats.avgReturn) > 0 ? "text-green-600" : "text-red-600"
              )}>
                {summaryStats.avgReturn}%
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Win Rate</p>
              <p className="text-2xl font-bold">{summaryStats.winRate}%</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Best Return</p>
              <p className="text-2xl font-bold text-green-600">{summaryStats.bestReturn}%</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Worst Return</p>
              <p className="text-2xl font-bold text-red-600">{summaryStats.worstReturn}%</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Filter className="h-5 w-5" />
              Filters
            </CardTitle>
            <Button onClick={exportToCSV} variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-sm font-medium mb-1 block">Source</label>
              <Select value={sourceFilter} onValueChange={setSourceFilter}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sources</SelectItem>
                  <SelectItem value="ui">UI</SelectItem>
                  <SelectItem value="pipeline">Pipeline</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">Symbol</label>
              <Input
                placeholder="Filter by symbol..."
                value={symbolFilter}
                onChange={(e) => setSymbolFilter(e.target.value.toUpperCase())}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">Session ID</label>
              <Input
                placeholder="Filter by session ID..."
                value={sessionFilter}
                onChange={(e) => setSessionFilter(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart className="h-5 w-5" />
            Combined Screener & Backtest Results
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8">Loading...</div>
          ) : error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : results.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No results found. Try adjusting your filters.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {/* Screener columns - exactly as in ScreenerResultsView */}
                    <TableHead className="w-32">Created Date</TableHead>
                    <TableHead className="w-32">Screening Date</TableHead>
                    <TableHead>Symbol</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead className="w-24">Price Range</TableHead>
                    <TableHead className="w-24">Price vs MA</TableHead>
                    <TableHead className="w-20">RSI</TableHead>
                    <TableHead className="w-20">Gap</TableHead>
                    <TableHead className="w-24">Volume</TableHead>
                    <TableHead className="w-20">Rel Vol</TableHead>
                    {/* Backtest columns - exactly as in BacktestResultsView */}
                    <TableHead>Date</TableHead>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Period</TableHead>
                    <TableHead className="text-center">Pivots</TableHead>
                    <TableHead className="text-center">Lower TF</TableHead>
                    <TableHead className="text-center">Return</TableHead>
                    <TableHead className="text-center">Sharpe</TableHead>
                    <TableHead className="text-center">Max DD</TableHead>
                    <TableHead className="text-center">Win Rate</TableHead>
                    <TableHead className="text-center">Trades</TableHead>
                    <TableHead className="text-center">Final Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((result, index) => (
                    <TableRow key={index}>
                      {/* Screener columns */}
                      <TableCell>
                        {result.screened_at ? format(parseISO(result.screened_at), 'MMM dd, yyyy HH:mm') : '-'}
                      </TableCell>
                      <TableCell>
                        {result.screening_date ? format(parseISO(result.screening_date), 'MMM dd, yyyy') : '-'}
                      </TableCell>
                      <TableCell className="font-medium">{result.symbol}</TableCell>
                      <TableCell>
                        <Badge variant={result.source === 'ui' ? 'default' : 'secondary'}>
                          {result.source || '-'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {result.filter_min_price && result.filter_max_price ? 
                          `$${result.filter_min_price}-${result.filter_max_price}` : '-'}
                      </TableCell>
                      <TableCell>
                        {result.filter_price_vs_ma_enabled ? 
                          `${result.filter_price_vs_ma_condition || ''} MA${result.filter_price_vs_ma_period || ''}` : '-'}
                      </TableCell>
                      <TableCell>
                        {result.filter_rsi_enabled ? 
                          `${result.filter_rsi_condition || ''} ${result.filter_rsi_threshold || ''}` : '-'}
                      </TableCell>
                      <TableCell>
                        {result.filter_gap_enabled ? 
                          `${result.filter_gap_threshold || ''}% ${result.filter_gap_direction || ''}` : '-'}
                      </TableCell>
                      <TableCell>
                        {result.filter_prev_day_dollar_volume_enabled ? 
                          `$${(result.filter_prev_day_dollar_volume || 0) / 1000000}M` : '-'}
                      </TableCell>
                      <TableCell>
                        {result.filter_relative_volume_enabled ? 
                          `${result.filter_relative_volume_min_ratio || ''}x` : '-'}
                      </TableCell>
                      {/* Backtest columns */}
                      <TableCell>
                        {result.backtest_created_at ? format(parseISO(result.backtest_created_at), 'MMM dd, yyyy') : '-'}
                      </TableCell>
                      <TableCell>{result.strategy_name || '-'}</TableCell>
                      <TableCell>
                        {result.backtest_start_date && result.backtest_end_date ? 
                          `${format(parseISO(result.backtest_start_date), 'MMM dd')} - ${format(parseISO(result.backtest_end_date), 'MMM dd, yyyy')}` : '-'}
                      </TableCell>
                      <TableCell className="text-center">{result.pivot_bars || '-'}</TableCell>
                      <TableCell className="text-center">{result.lower_timeframe || '-'}</TableCell>
                      <TableCell className={cn(
                        "text-center font-medium",
                        result.total_return && result.total_return > 0 ? "text-green-600" : "text-red-600"
                      )}>
                        {result.total_return ? `${result.total_return.toFixed(2)}%` : '-'}
                      </TableCell>
                      <TableCell className="text-center">
                        {result.sharpe_ratio ? result.sharpe_ratio.toFixed(3) : '-'}
                      </TableCell>
                      <TableCell className="text-center text-red-600">
                        {result.max_drawdown ? `${result.max_drawdown.toFixed(2)}%` : '-'}
                      </TableCell>
                      <TableCell className="text-center">
                        {result.win_rate ? `${result.win_rate.toFixed(1)}%` : '-'}
                      </TableCell>
                      <TableCell className="text-center">
                        {result.total_trades || '-'}
                      </TableCell>
                      <TableCell className="text-center">
                        {result.final_value ? `$${result.final_value.toLocaleString()}` : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex justify-center">
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={setCurrentPage}
              />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}