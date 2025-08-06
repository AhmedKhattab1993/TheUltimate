import { useState } from 'react'
import { format } from 'date-fns'
import { Download, Search, Loader2, Calendar, TrendingUp, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DatePicker } from '@/components/ui/date-picker'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { stockScreenerApi } from '@/services/api'
import type { ScreenerRequest, ScreenerResponse } from '@/types/api'

export function StockScreener() {
  const [startDate, setStartDate] = useState<Date>()
  const [endDate, setEndDate] = useState<Date>()
  const [minVolume, setMinVolume] = useState<string>('')
  const [minPriceChange, setMinPriceChange] = useState<string>('')
  const [maxPriceChange, setMaxPriceChange] = useState<string>('')
  const [maPeriod, setMaPeriod] = useState<string>('')
  const [maPricePosition, setMaPricePosition] = useState<string>('')
  const [useAllUsStocks, setUseAllUsStocks] = useState(false)
  const [customSymbols, setCustomSymbols] = useState<string>('')
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<ScreenerResponse | null>(null)
  const [filterText, setFilterText] = useState<string>('')
  const [viewMode, setViewMode] = useState<'by-stock' | 'by-date'>('by-date')

  const handleSubmit = async () => {
    if (!startDate || !endDate) {
      setError('Please select both start and end dates')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const filters: any = {}
      
      // Add volume filter if provided
      if (minVolume) {
        filters.volume = {
          min_average: parseInt(minVolume),
          lookback_days: 20  // Default lookback period
        }
      }
      
      // Add price change filter if provided
      if (minPriceChange || maxPriceChange) {
        filters.price_change = {}
        if (minPriceChange) filters.price_change.min_change = parseFloat(minPriceChange)
        if (maxPriceChange) filters.price_change.max_change = parseFloat(maxPriceChange)
        filters.price_change.period_days = 1  // Default to daily change
      }
      
      // Add moving average filter if provided
      if (maPeriod && maPricePosition) {
        filters.moving_average = {
          period: parseInt(maPeriod),
          condition: maPricePosition
        }
      }
      
      const request: ScreenerRequest = {
        start_date: format(startDate, 'yyyy-MM-dd'),
        end_date: format(endDate, 'yyyy-MM-dd'),
        filters: filters
      }
      
      // Add either use_all_us_stocks or specific symbols
      if (useAllUsStocks) {
        request.use_all_us_stocks = true
      } else if (customSymbols.trim()) {
        // Parse custom symbols (comma or space separated)
        const symbols = customSymbols
          .split(/[,\s]+/)
          .map(s => s.trim().toUpperCase())
          .filter(s => s.length > 0)
        if (symbols.length > 0) {
          request.symbols = symbols
        }
      }

      const data = await stockScreenerApi.screen(request)
      setResponse(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  // Process results for display
  const processResultsByDate = () => {
    if (!response?.results) return {}
    
    const byDate: Record<string, string[]> = {}
    
    response.results.forEach(stock => {
      stock.qualifying_dates.forEach(date => {
        if (!byDate[date]) {
          byDate[date] = []
        }
        byDate[date].push(stock.symbol)
      })
    })
    
    // Sort dates in descending order
    const sortedDates = Object.keys(byDate).sort((a, b) => b.localeCompare(a))
    const sortedByDate: Record<string, string[]> = {}
    sortedDates.forEach(date => {
      sortedByDate[date] = byDate[date].sort()
    })
    
    return sortedByDate
  }

  // Filter results based on search text
  const filterResults = (data: any) => {
    if (!filterText) return data
    
    const searchTerm = filterText.toUpperCase()
    
    if (viewMode === 'by-date') {
      const filtered: Record<string, string[]> = {}
      Object.entries(data).forEach(([date, symbols]) => {
        const filteredSymbols = (symbols as string[]).filter(symbol => 
          symbol.toUpperCase().includes(searchTerm)
        )
        if (filteredSymbols.length > 0) {
          filtered[date] = filteredSymbols
        }
      })
      return filtered
    } else {
      return response?.results.filter(stock => 
        stock.symbol.toUpperCase().includes(searchTerm)
      ) || []
    }
  }

  const exportResults = () => {
    if (!response || !response.results.length) return

    let csv = ''
    
    if (viewMode === 'by-date') {
      const byDate = processResultsByDate()
      csv = 'Date,Symbols\n'
      Object.entries(byDate).forEach(([date, symbols]) => {
        csv += `${date},"${symbols.join(', ')}"\n`
      })
    } else {
      csv = 'Symbol,Qualifying Dates\n'
      response.results.forEach(r => {
        csv += `${r.symbol},"${r.qualifying_dates.join(', ')}"\n`
      })
    }

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `stock-screener-results-${viewMode}-${format(new Date(), 'yyyy-MM-dd')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-4xl font-bold mb-8">Stock Screener</h1>
      
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Filter Criteria</CardTitle>
          <CardDescription>
            Set your screening parameters to find stocks that match your criteria
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Stock Selection Toggle */}
            <div className="col-span-full space-y-4 pb-4 border-b">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="all-stocks">Screen All US Common Stocks</Label>
                  <p className="text-sm text-muted-foreground">
                    {useAllUsStocks 
                      ? "Screening 5000+ US common stocks (this may take longer)"
                      : "Enter specific stock symbols below"}
                  </p>
                </div>
                <Switch
                  id="all-stocks"
                  checked={useAllUsStocks}
                  onCheckedChange={setUseAllUsStocks}
                />
              </div>
              
              {!useAllUsStocks && (
                <div className="space-y-2">
                  <Label>Stock Symbols</Label>
                  <Input
                    placeholder="e.g., AAPL, MSFT, GOOGL (comma or space separated)"
                    value={customSymbols}
                    onChange={(e) => setCustomSymbols(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Leave empty to use default watchlist, or enter specific symbols
                  </p>
                </div>
              )}
              
              {useAllUsStocks && (
                <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-950/20 rounded-md border border-amber-200 dark:border-amber-800">
                  <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-500 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
                      Performance Notice
                    </p>
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                      Screening all US stocks may take 30-60 seconds depending on your criteria and date range.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Date Range */}
            <div className="space-y-2">
              <Label>Start Date</Label>
              <DatePicker
                date={startDate}
                onDateChange={setStartDate}
                placeholder="Select start date"
              />
            </div>
            
            <div className="space-y-2">
              <Label>End Date</Label>
              <DatePicker
                date={endDate}
                onDateChange={setEndDate}
                placeholder="Select end date"
              />
            </div>

            {/* Volume Filters */}
            <div className="space-y-2">
              <Label>Min Volume</Label>
              <Input
                type="number"
                placeholder="e.g., 1000000"
                value={minVolume}
                onChange={(e) => setMinVolume(e.target.value)}
              />
            </div>


            {/* Price Change Filters */}
            <div className="space-y-2">
              <Label>Min Price Change %</Label>
              <Input
                type="number"
                step="0.1"
                placeholder="e.g., 5.0"
                value={minPriceChange}
                onChange={(e) => setMinPriceChange(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Max Price Change %</Label>
              <Input
                type="number"
                step="0.1"
                placeholder="e.g., 20.0"
                value={maxPriceChange}
                onChange={(e) => setMaxPriceChange(e.target.value)}
              />
            </div>

            {/* Moving Average Filters */}
            <div className="space-y-2">
              <Label>MA Period</Label>
              <Input
                type="number"
                placeholder="e.g., 20"
                value={maPeriod}
                onChange={(e) => setMaPeriod(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Price Position</Label>
              <Select value={maPricePosition} onValueChange={setMaPricePosition}>
                <SelectTrigger>
                  <SelectValue placeholder="Select position" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="above">Above MA</SelectItem>
                  <SelectItem value="below">Below MA</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="mt-6 flex gap-4">
            <Button onClick={handleSubmit} disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {useAllUsStocks ? 'Screening all US stocks...' : 'Screening...'}
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Run Screener
                </>
              )}
            </Button>
            
            {response && response.results.length > 0 && (
              <Button variant="outline" onClick={exportResults}>
                <Download className="mr-2 h-4 w-4" />
                Export CSV
              </Button>
            )}
          </div>

          {error && (
            <div className="mt-4 p-4 bg-destructive/10 border border-destructive rounded-md">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {response && (
        <Card>
          <CardHeader>
            <CardTitle>Results</CardTitle>
            <CardDescription>
              Found {response.total_qualifying_stocks} qualifying stocks from {response.total_symbols_screened} screened • 
              Execution time: {(response.execution_time_ms / 1000).toFixed(2)}s
            </CardDescription>
          </CardHeader>
          <CardContent>
            {response.results.length === 0 ? (
              <p className="text-center py-8 text-muted-foreground">
                No stocks found matching your criteria
              </p>
            ) : (
              <div className="space-y-4">
                {/* Filter Input */}
                <div className="flex items-center space-x-2">
                  <Search className="h-4 w-4 text-muted-foreground" />
                  <Input
                    type="text"
                    placeholder="Filter stocks by symbol..."
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    className="max-w-sm"
                  />
                </div>

                {/* View Mode Tabs */}
                <Tabs value={viewMode} onValueChange={(value: string) => setViewMode(value as 'by-stock' | 'by-date')}>
                  <TabsList>
                    <TabsTrigger value="by-date">
                      <Calendar className="h-4 w-4 mr-2" />
                      By Date
                    </TabsTrigger>
                    <TabsTrigger value="by-stock">
                      <TrendingUp className="h-4 w-4 mr-2" />
                      By Stock
                    </TabsTrigger>
                  </TabsList>

                  {/* By Date View */}
                  <TabsContent value="by-date" className="mt-4">
                    <div className="space-y-4">
                      {Object.entries(filterResults(processResultsByDate())).map(([date, symbols]) => (
                        <Card key={date}>
                          <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                              <CardTitle className="text-lg">
                                {format(new Date(date), 'MMMM dd, yyyy')}
                              </CardTitle>
                              <Badge variant="secondary">
                                {(symbols as string[]).length} stocks
                              </Badge>
                            </div>
                          </CardHeader>
                          <CardContent>
                            <div className="flex flex-wrap gap-2">
                              {(symbols as string[]).map(symbol => (
                                <Badge key={symbol} variant="outline" className="font-mono">
                                  {symbol}
                                </Badge>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </TabsContent>

                  {/* By Stock View */}
                  <TabsContent value="by-stock" className="mt-4">
                    <div className="space-y-4">
                      {(filterResults(response.results) as typeof response.results).map((stock) => (
                        <Card key={stock.symbol}>
                          <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                              <CardTitle className="text-lg font-mono">
                                {stock.symbol}
                              </CardTitle>
                              <Badge variant="secondary">
                                {stock.qualifying_dates.length} days
                              </Badge>
                            </div>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-2">
                              <p className="text-sm text-muted-foreground">Qualifying dates:</p>
                              <div className="flex flex-wrap gap-2">
                                {stock.qualifying_dates
                                  .sort((a, b) => b.localeCompare(a))
                                  .map(date => (
                                    <Badge key={date} variant="outline">
                                      {format(new Date(date), 'MMM dd, yyyy')}
                                    </Badge>
                                  ))}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </TabsContent>
                </Tabs>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}