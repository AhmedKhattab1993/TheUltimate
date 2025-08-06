import { useState } from 'react'
import { format } from 'date-fns'
import { Download, Search, Loader2, Calendar, TrendingUp, AlertCircle, DollarSign, Activity, BarChart3 } from 'lucide-react'
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
import type { ScreenerRequest, ScreenerResponse, Filters } from '@/types/api'

export function StockScreenerEnhanced() {
  const [startDate, setStartDate] = useState<Date>()
  const [endDate, setEndDate] = useState<Date>()
  
  // Basic filters
  const [minVolume, setMinVolume] = useState<string>('')
  const [minPriceChange, setMinPriceChange] = useState<string>('')
  const [maxPriceChange, setMaxPriceChange] = useState<string>('')
  const [maPeriod, setMaPeriod] = useState<string>('')
  const [maPricePosition, setMaPricePosition] = useState<string>('')
  
  // Day trading filters
  const [minGapPercent, setMinGapPercent] = useState<string>('4')
  const [maxGapPercent, setMaxGapPercent] = useState<string>('')
  const [minPrice, setMinPrice] = useState<string>('2')
  const [maxPrice, setMaxPrice] = useState<string>('10')
  const [maxFloat, setMaxFloat] = useState<string>('100000000')
  const [minRelativeVolume, setMinRelativeVolume] = useState<string>('2')
  const [relativeVolumeLookback, setRelativeVolumeLookback] = useState<string>('20')
  const [maxMarketCap, setMaxMarketCap] = useState<string>('300000000')
  const [minMarketCap, setMinMarketCap] = useState<string>('')
  
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
      const filters: Filters = {}
      
      // Add volume filter if provided
      if (minVolume) {
        filters.volume = {
          min_average: parseInt(minVolume),
          lookback_days: 20
        }
      }
      
      // Add price change filter if provided
      if (minPriceChange || maxPriceChange) {
        filters.price_change = {}
        if (minPriceChange) filters.price_change.min_change = parseFloat(minPriceChange)
        if (maxPriceChange) filters.price_change.max_change = parseFloat(maxPriceChange)
        filters.price_change.period_days = 1
      }
      
      // Add moving average filter if provided
      if (maPeriod && maPricePosition) {
        filters.moving_average = {
          period: parseInt(maPeriod),
          condition: maPricePosition as any
        }
      }
      
      // Add gap filter
      if (minGapPercent) {
        filters.gap = {
          min_gap_percent: parseFloat(minGapPercent)
        }
        if (maxGapPercent) {
          filters.gap.max_gap_percent = parseFloat(maxGapPercent)
        }
      }
      
      // Add price range filter
      if (minPrice || maxPrice) {
        filters.price_range = {}
        if (minPrice) filters.price_range.min_price = parseFloat(minPrice)
        if (maxPrice) filters.price_range.max_price = parseFloat(maxPrice)
      }
      
      // Add float filter
      if (maxFloat) {
        filters.float = {
          max_float: parseFloat(maxFloat)
        }
      }
      
      // Add relative volume filter
      if (minRelativeVolume) {
        filters.relative_volume = {
          min_relative_volume: parseFloat(minRelativeVolume),
          lookback_days: parseInt(relativeVolumeLookback) || 20
        }
      }
      
      // Add market cap filter
      if (maxMarketCap || minMarketCap) {
        filters.market_cap = {}
        if (maxMarketCap) filters.market_cap.max_market_cap = parseFloat(maxMarketCap)
        if (minMarketCap) filters.market_cap.min_market_cap = parseFloat(minMarketCap)
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
    if (!response?.results) return []
    
    const byDate: { [date: string]: string[] } = {}
    response.results.forEach(result => {
      result.qualifying_dates.forEach(date => {
        if (!byDate[date]) byDate[date] = []
        byDate[date].push(result.symbol)
      })
    })
    
    return Object.entries(byDate)
      .sort(([a], [b]) => b.localeCompare(a))
      .map(([date, symbols]) => ({ date, symbols }))
  }

  // Filter results based on search text
  const getFilteredResults = () => {
    if (!response?.results) return []
    if (!filterText) return response.results
    
    const searchTerm = filterText.toLowerCase()
    return response.results.filter(result => 
      result.symbol.toLowerCase().includes(searchTerm)
    )
  }

  const exportResults = () => {
    if (!response) return
    
    const csv = [
      ['Symbol', 'Qualifying Dates', 'Metrics'].join(','),
      ...response.results.map(r => 
        [r.symbol, r.qualifying_dates.join(';'), JSON.stringify(r.metrics)].join(',')
      )
    ].join('\n')
    
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `screener-results-${format(new Date(), 'yyyy-MM-dd')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Stock Screener</h1>
          <p className="text-muted-foreground">
            Find stocks that match your trading criteria
          </p>
        </div>
        <Badge variant="secondary" className="gap-1">
          <Calendar className="h-3 w-3" />
          {format(new Date(), 'PPP')}
        </Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filter Criteria</CardTitle>
          <CardDescription>
            Set your screening parameters to find stocks that match your criteria
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Stock Selection Toggle */}
          <div className="space-y-4 pb-6 border-b mb-6">
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
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
          </div>

          {/* Filter Tabs */}
          <Tabs defaultValue="day-trading" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="day-trading" className="gap-2">
                <Activity className="h-4 w-4" />
                Day Trading Filters
              </TabsTrigger>
              <TabsTrigger value="technical" className="gap-2">
                <BarChart3 className="h-4 w-4" />
                Technical Filters
              </TabsTrigger>
            </TabsList>

            <TabsContent value="day-trading" className="space-y-6 mt-6">
              {/* Gap Filter */}
              <div>
                <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Gap Filter
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Min Gap %</Label>
                    <Input
                      type="number"
                      step="0.1"
                      placeholder="e.g., 4.0"
                      value={minGapPercent}
                      onChange={(e) => setMinGapPercent(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Max Gap % (optional)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      placeholder="e.g., 20.0"
                      value={maxGapPercent}
                      onChange={(e) => setMaxGapPercent(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Price Range Filter */}
              <div>
                <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <DollarSign className="h-4 w-4" />
                  Price Range
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Min Price</Label>
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="e.g., 2.00"
                      value={minPrice}
                      onChange={(e) => setMinPrice(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Max Price</Label>
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="e.g., 10.00"
                      value={maxPrice}
                      onChange={(e) => setMaxPrice(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Float Filter */}
              <div>
                <h3 className="text-sm font-medium mb-3">Float Size</h3>
                <div className="space-y-2">
                  <Label>Max Float (shares outstanding)</Label>
                  <Input
                    type="number"
                    placeholder="e.g., 100000000"
                    value={maxFloat}
                    onChange={(e) => setMaxFloat(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum number of shares available for trading
                  </p>
                </div>
              </div>

              {/* Relative Volume Filter */}
              <div>
                <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  Relative Volume
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Min Relative Volume</Label>
                    <Input
                      type="number"
                      step="0.1"
                      placeholder="e.g., 2.0"
                      value={minRelativeVolume}
                      onChange={(e) => setMinRelativeVolume(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Lookback Days</Label>
                    <Input
                      type="number"
                      placeholder="e.g., 20"
                      value={relativeVolumeLookback}
                      onChange={(e) => setRelativeVolumeLookback(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Market Cap Filter */}
              <div>
                <h3 className="text-sm font-medium mb-3">Market Capitalization</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Max Market Cap</Label>
                    <Input
                      type="number"
                      placeholder="e.g., 300000000"
                      value={maxMarketCap}
                      onChange={(e) => setMaxMarketCap(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Min Market Cap (optional)</Label>
                    <Input
                      type="number"
                      placeholder="e.g., 10000000"
                      value={minMarketCap}
                      onChange={(e) => setMinMarketCap(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="technical" className="space-y-6 mt-6">
              {/* Volume Filters */}
              <div>
                <h3 className="text-sm font-medium mb-3">Volume Filter</h3>
                <div className="space-y-2">
                  <Label>Min Average Volume</Label>
                  <Input
                    type="number"
                    placeholder="e.g., 1000000"
                    value={minVolume}
                    onChange={(e) => setMinVolume(e.target.value)}
                  />
                </div>
              </div>

              {/* Price Change Filters */}
              <div>
                <h3 className="text-sm font-medium mb-3">Price Change Filter</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                </div>
              </div>

              {/* Moving Average Filters */}
              <div>
                <h3 className="text-sm font-medium mb-3">Moving Average Filter</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
              </div>
            </TabsContent>
          </Tabs>

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
                Export Results
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-red-200 dark:border-red-800">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
              <AlertCircle className="h-5 w-5" />
              <p className="font-medium">Error</p>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      )}

      {response && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Screening Results</CardTitle>
                <CardDescription>
                  Found {response.total_qualifying_stocks} qualifying stocks out of {response.total_symbols_screened} screened
                </CardDescription>
              </div>
              <Badge variant="secondary">
                {response.execution_time_ms.toFixed(0)}ms
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {response.results.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No stocks matched your screening criteria. Try adjusting your filters.
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <Input
                    placeholder="Filter results..."
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    className="max-w-sm"
                  />
                  <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as any)}>
                    <TabsList>
                      <TabsTrigger value="by-date">By Date</TabsTrigger>
                      <TabsTrigger value="by-stock">By Stock</TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>

                {viewMode === 'by-date' ? (
                  <div className="space-y-4">
                    {processResultsByDate().map(({ date, symbols }: { date: string; symbols: string[] }) => (
                      <div key={date} className="border rounded-lg p-4">
                        <h3 className="font-semibold mb-2">{date}</h3>
                        <div className="flex flex-wrap gap-2">
                          {symbols.map((symbol: string) => (
                            <Badge key={symbol} variant="secondary">
                              {symbol}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="text-left p-3">Symbol</th>
                          <th className="text-left p-3">Qualifying Days</th>
                          <th className="text-left p-3">First Date</th>
                          <th className="text-left p-3">Last Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {getFilteredResults().map((result, idx) => (
                          <tr key={result.symbol} className={idx % 2 === 0 ? 'bg-muted/20' : ''}>
                            <td className="p-3 font-medium">{result.symbol}</td>
                            <td className="p-3">{result.qualifying_dates.length}</td>
                            <td className="p-3">
                              {result.qualifying_dates.length > 0 ? result.qualifying_dates[0] : '-'}
                            </td>
                            <td className="p-3">
                              {result.qualifying_dates.length > 0 
                                ? result.qualifying_dates[result.qualifying_dates.length - 1] 
                                : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}