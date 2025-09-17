import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { DatePicker } from '@/components/ui/date-picker'
import { 
  TrendingUp, Settings, AlertCircle, RefreshCw, Search, 
  ChevronRight, Download, BarChart3, Target
} from 'lucide-react'
import { format, subDays } from 'date-fns'
import { filterOptimizerService } from '@/services/filterOptimizer'
import { 
  OptimizationTarget, 
  FilterSearchSpace,
  OptimizationResult,
  type OptimizationRequest,
  type OptimizationResponse,
  type SuggestedRanges
} from '@/types/filterOptimizer'

export function FilterOptimizerTab() {
  // State
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<OptimizationResponse | null>(null)
  const [suggestedRanges, setSuggestedRanges] = useState<SuggestedRanges | null>(null)
  
  // Form state
  const [startDate, setStartDate] = useState<Date>(subDays(new Date(), 30))
  const [endDate, setEndDate] = useState<Date>(new Date())
  const [target, setTarget] = useState<OptimizationTarget>(OptimizationTarget.SHARPE_RATIO)
  const [customFormula, setCustomFormula] = useState('')
  const [minSymbols, setMinSymbols] = useState(10)
  const [maxResults, setMaxResults] = useState(20)
  const [pivotBars, setPivotBars] = useState<number | undefined>(undefined)
  
  // Search space state
  const [searchSpace, setSearchSpace] = useState<FilterSearchSpace>({
    price_min: { min_value: 5, max_value: 50, step: 5 },
    price_max: { min_value: 20, max_value: 200, step: 10 },
    rsi_min: { min_value: 20, max_value: 40, step: 5 },
    rsi_max: { min_value: 60, max_value: 80, step: 5 },
    gap_min: { min_value: -5, max_value: 0, step: 1 },
    gap_max: { min_value: 0, max_value: 5, step: 1 },
    volume_min: { min_value: 1000000, max_value: 5000000, step: 1000000 },
    rel_volume_min: { min_value: 1.0, max_value: 3.0, step: 0.5 }
  })
  
  // Load suggested ranges when dates change
  useEffect(() => {
    if (startDate && endDate) {
      loadSuggestedRanges()
    }
  }, [startDate, endDate])
  
  const loadSuggestedRanges = async () => {
    try {
      const ranges = await filterOptimizerService.getSuggestedRanges(
        format(startDate, 'yyyy-MM-dd'),
        format(endDate, 'yyyy-MM-dd')
      )
      setSuggestedRanges(ranges)
    } catch (err: any) {
      console.error('Failed to load suggested ranges:', err)
    }
  }
  
  const handleOptimize = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const request: OptimizationRequest = {
        start_date: format(startDate, 'yyyy-MM-dd'),
        end_date: format(endDate, 'yyyy-MM-dd'),
        target,
        custom_formula: target === OptimizationTarget.CUSTOM ? customFormula : undefined,
        search_space: searchSpace,
        max_results: maxResults,
        min_symbols_required: minSymbols,
        pivot_bars: pivotBars
      }
      
      const response = await filterOptimizerService.optimizeFilters(request)
      setResults(response)
    } catch (err: any) {
      setError(err.message || 'Failed to optimize filters')
    } finally {
      setLoading(false)
    }
  }
  
  const applySuggestedRanges = () => {
    if (!suggestedRanges) return
    
    const suggested = suggestedRanges.suggested_ranges
    setSearchSpace({
      price_min: suggested.price_range.min,
      price_max: suggested.price_range.max,
      rsi_min: suggested.rsi_range.min,
      rsi_max: suggested.rsi_range.max,
      gap_min: suggested.gap_range.min,
      gap_max: suggested.gap_range.max,
      volume_min: suggested.volume.min,
      rel_volume_min: suggested.relative_volume.min
    })
  }
  
  const formatFilterCombination = (combo: OptimizationResult['filter_combination']) => {
    const parts: string[] = []
    
    if (combo.price_range) {
      const { min, max } = combo.price_range
      if (min !== undefined && max !== undefined) {
        parts.push(`Price: $${min}-$${max}`)
      }
    }
    
    if (combo.rsi_range) {
      const { min, max } = combo.rsi_range
      if (min !== undefined && max !== undefined) {
        parts.push(`RSI: ${min}-${max}`)
      }
    }
    
    if (combo.gap_range) {
      const { min, max } = combo.gap_range
      if (min !== undefined && max !== undefined) {
        parts.push(`Gap: ${min}%-${max}%`)
      }
    }
    
    if (combo.volume_min !== undefined) {
      parts.push(`Vol: $${(combo.volume_min / 1e6).toFixed(1)}M+`)
    }
    
    if (combo.rel_volume_min !== undefined) {
      parts.push(`RelVol: ${combo.rel_volume_min}x+`)
    }
    
    if (combo.ma_condition) {
      parts.push(`MA${combo.ma_condition.period}: ${combo.ma_condition.condition}`)
    }
    
    return parts.join(' | ')
  }
  
  const exportResults = () => {
    if (!results) return
    
    const csv = [
      ['Rank', 'Filters', 'Target Score', 'Sharpe', 'Return %', 'Win Rate %', 'Max DD %', 'Symbols', 'Backtests'],
      ...results.results.map(r => [
        r.rank,
        formatFilterCombination(r.filter_combination),
        r.target_score.toFixed(3),
        r.avg_sharpe_ratio.toFixed(2),
        r.avg_total_return.toFixed(2),
        r.avg_win_rate.toFixed(1),
        r.avg_max_drawdown.toFixed(2),
        r.total_symbols_matched,
        r.total_backtests
      ])
    ].map(row => row.join(',')).join('\n')
    
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `filter-optimization-${format(new Date(), 'yyyy-MM-dd')}.csv`
    a.click()
  }
  
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            Filter Optimizer
          </CardTitle>
          <CardDescription>
            Find optimal screener filter values based on historical backtest performance
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="configuration" className="space-y-4">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="configuration">Configuration</TabsTrigger>
              <TabsTrigger value="results" disabled={!results}>
                Results {results && `(${results.results.length})`}
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="configuration" className="space-y-6">
              {/* Date Range and Target */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Analysis Period</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Start Date</Label>
                      <DatePicker
                        date={startDate}
                        onDateChange={(date) => setStartDate(date || new Date())}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>End Date</Label>
                      <DatePicker
                        date={endDate}
                        onDateChange={(date) => setEndDate(date || new Date())}
                      />
                    </div>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Optimization Target</h3>
                  <div className="space-y-3">
                    <Select value={target} onValueChange={(v) => setTarget(v as OptimizationTarget)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={OptimizationTarget.SHARPE_RATIO}>Sharpe Ratio</SelectItem>
                        <SelectItem value={OptimizationTarget.TOTAL_RETURN}>Total Return</SelectItem>
                        <SelectItem value={OptimizationTarget.WIN_RATE}>Win Rate</SelectItem>
                        <SelectItem value={OptimizationTarget.PROFIT_FACTOR}>Profit Factor</SelectItem>
                        <SelectItem value={OptimizationTarget.MIN_DRAWDOWN}>Minimum Drawdown</SelectItem>
                        <SelectItem value={OptimizationTarget.CUSTOM}>Custom Formula</SelectItem>
                      </SelectContent>
                    </Select>
                    {target === OptimizationTarget.CUSTOM && (
                      <Input
                        placeholder="e.g., 0.4*sharpe + 0.3*win_rate - 0.3*drawdown"
                        value={customFormula}
                        onChange={(e) => setCustomFormula(e.target.value)}
                      />
                    )}
                  </div>
                </div>
              </div>
              
              {/* Additional Settings */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">Additional Settings</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label>Min Symbols Required</Label>
                    <Input
                      type="number"
                      min="1"
                      value={minSymbols}
                      onChange={(e) => setMinSymbols(parseInt(e.target.value) || 10)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Max Results to Show</Label>
                    <Input
                      type="number"
                      min="10"
                      max="100"
                      value={maxResults}
                      onChange={(e) => setMaxResults(parseInt(e.target.value) || 20)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Pivot Bars (Optional)</Label>
                    <Input
                      type="number"
                      min="1"
                      placeholder="All"
                      value={pivotBars || ''}
                      onChange={(e) => setPivotBars(e.target.value ? parseInt(e.target.value) : undefined)}
                    />
                  </div>
                </div>
              </div>
              
              {/* Search Space Configuration */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Filter Search Ranges</h3>
                  {suggestedRanges && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={applySuggestedRanges}
                    >
                      <Settings className="h-4 w-4 mr-2" />
                      Apply Suggested Ranges
                    </Button>
                  )}
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Price Range */}
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Price Range ($)</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <Label className="text-muted-foreground">Parameter</Label>
                        <Label className="text-muted-foreground">Min-Max</Label>
                        <Label className="text-muted-foreground">Step</Label>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <span className="text-sm">Min Price</span>
                        <div className="flex gap-1">
                          <Input
                            type="number"
                            value={searchSpace.price_min?.min_value || 0}
                            onChange={(e) => setSearchSpace({
                              ...searchSpace,
                              price_min: {
                                ...searchSpace.price_min!,
                                min_value: parseFloat(e.target.value) || 0
                              }
                            })}
                            className="h-8 text-sm"
                          />
                          <Input
                            type="number"
                            value={searchSpace.price_min?.max_value || 0}
                            onChange={(e) => setSearchSpace({
                              ...searchSpace,
                              price_min: {
                                ...searchSpace.price_min!,
                                max_value: parseFloat(e.target.value) || 0
                              }
                            })}
                            className="h-8 text-sm"
                          />
                        </div>
                        <Input
                          type="number"
                          value={searchSpace.price_min?.step || 0}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            price_min: {
                              ...searchSpace.price_min!,
                              step: parseFloat(e.target.value) || 1
                            }
                          })}
                          className="h-8 text-sm"
                        />
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <span className="text-sm">Max Price</span>
                        <div className="flex gap-1">
                          <Input
                            type="number"
                            value={searchSpace.price_max?.min_value || 0}
                            onChange={(e) => setSearchSpace({
                              ...searchSpace,
                              price_max: {
                                ...searchSpace.price_max!,
                                min_value: parseFloat(e.target.value) || 0
                              }
                            })}
                            className="h-8 text-sm"
                          />
                          <Input
                            type="number"
                            value={searchSpace.price_max?.max_value || 0}
                            onChange={(e) => setSearchSpace({
                              ...searchSpace,
                              price_max: {
                                ...searchSpace.price_max!,
                                max_value: parseFloat(e.target.value) || 0
                              }
                            })}
                            className="h-8 text-sm"
                          />
                        </div>
                        <Input
                          type="number"
                          value={searchSpace.price_max?.step || 0}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            price_max: {
                              ...searchSpace.price_max!,
                              step: parseFloat(e.target.value) || 1
                            }
                          })}
                          className="h-8 text-sm"
                        />
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* RSI Range */}
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">RSI Range</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <Label className="text-muted-foreground">Parameter</Label>
                        <Label className="text-muted-foreground">Min-Max</Label>
                        <Label className="text-muted-foreground">Step</Label>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <span className="text-sm">Min RSI</span>
                        <div className="flex gap-1">
                          <Input
                            type="number"
                            value={searchSpace.rsi_min?.min_value || 0}
                            onChange={(e) => setSearchSpace({
                              ...searchSpace,
                              rsi_min: {
                                ...searchSpace.rsi_min!,
                                min_value: parseFloat(e.target.value) || 0
                              }
                            })}
                            className="h-8 text-sm"
                          />
                          <Input
                            type="number"
                            value={searchSpace.rsi_min?.max_value || 0}
                            onChange={(e) => setSearchSpace({
                              ...searchSpace,
                              rsi_min: {
                                ...searchSpace.rsi_min!,
                                max_value: parseFloat(e.target.value) || 0
                              }
                            })}
                            className="h-8 text-sm"
                          />
                        </div>
                        <Input
                          type="number"
                          value={searchSpace.rsi_min?.step || 0}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            rsi_min: {
                              ...searchSpace.rsi_min!,
                              step: parseFloat(e.target.value) || 1
                            }
                          })}
                          className="h-8 text-sm"
                        />
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <span className="text-sm">Max RSI</span>
                        <div className="flex gap-1">
                          <Input
                            type="number"
                            value={searchSpace.rsi_max?.min_value || 0}
                            onChange={(e) => setSearchSpace({
                              ...searchSpace,
                              rsi_max: {
                                ...searchSpace.rsi_max!,
                                min_value: parseFloat(e.target.value) || 0
                              }
                            })}
                            className="h-8 text-sm"
                          />
                          <Input
                            type="number"
                            value={searchSpace.rsi_max?.max_value || 0}
                            onChange={(e) => setSearchSpace({
                              ...searchSpace,
                              rsi_max: {
                                ...searchSpace.rsi_max!,
                                max_value: parseFloat(e.target.value) || 0
                              }
                            })}
                            className="h-8 text-sm"
                          />
                        </div>
                        <Input
                          type="number"
                          value={searchSpace.rsi_max?.step || 0}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            rsi_max: {
                                ...searchSpace.rsi_max!,
                              step: parseFloat(e.target.value) || 1
                            }
                          })}
                          className="h-8 text-sm"
                        />
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
              
              {/* Action Buttons */}
              <div className="flex justify-center">
                <Button
                  size="lg"
                  onClick={handleOptimize}
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Optimizing...
                    </>
                  ) : (
                    <>
                      <Search className="h-4 w-4 mr-2" />
                      Run Optimization
                    </>
                  )}
                </Button>
              </div>
              
              {error && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
            </TabsContent>
            
            <TabsContent value="results" className="space-y-4">
              {results && (
                <>
                  {/* Summary */}
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Optimization Summary</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Combinations Tested:</span>
                          <p className="font-semibold">{results.total_combinations_tested}</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Optimization Target:</span>
                          <p className="font-semibold">{results.optimization_target.replace('_', ' ')}</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Date Range:</span>
                          <p className="font-semibold">
                            {format(new Date(results.date_range_analyzed.start), 'MMM d')} - 
                            {format(new Date(results.date_range_analyzed.end), 'MMM d, yyyy')}
                          </p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Execution Time:</span>
                          <p className="font-semibold">{(results.execution_time_ms / 1000).toFixed(1)}s</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Best Result Highlight */}
                  {results.best_combination && (
                    <Card className="border-green-200 bg-green-50/50">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center gap-2">
                          <TrendingUp className="h-4 w-4 text-green-600" />
                          Best Filter Combination
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm font-medium mb-2">
                          {formatFilterCombination(results.best_combination.filter_combination)}
                        </p>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                          <div>
                            <span className="text-muted-foreground">Sharpe:</span>
                            <p className="font-semibold">{results.best_combination.avg_sharpe_ratio.toFixed(2)}</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Return:</span>
                            <p className="font-semibold text-green-600">
                              +{results.best_combination.avg_total_return.toFixed(2)}%
                            </p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Win Rate:</span>
                            <p className="font-semibold">{results.best_combination.avg_win_rate.toFixed(1)}%</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Max DD:</span>
                            <p className="font-semibold text-red-600">
                              -{Math.abs(results.best_combination.avg_max_drawdown).toFixed(2)}%
                            </p>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Symbols:</span>
                            <p className="font-semibold">{results.best_combination.total_symbols_matched}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                  
                  {/* Results Table */}
                  <Card>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">All Results</CardTitle>
                        <Button variant="outline" size="sm" onClick={exportResults}>
                          <Download className="h-4 w-4 mr-2" />
                          Export CSV
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="p-0">
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead className="w-12">Rank</TableHead>
                              <TableHead>Filter Combination</TableHead>
                              <TableHead className="text-right">Score</TableHead>
                              <TableHead className="text-right">Sharpe</TableHead>
                              <TableHead className="text-right">Return</TableHead>
                              <TableHead className="text-right">Win Rate</TableHead>
                              <TableHead className="text-right">Max DD</TableHead>
                              <TableHead className="text-right">Symbols</TableHead>
                              <TableHead className="text-right">Tests</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {results.results.map((result) => (
                              <TableRow key={result.rank}>
                                <TableCell>
                                  <Badge variant={result.rank <= 3 ? "default" : "outline"}>
                                    #{result.rank}
                                  </Badge>
                                </TableCell>
                                <TableCell className="font-mono text-xs">
                                  {formatFilterCombination(result.filter_combination)}
                                </TableCell>
                                <TableCell className="text-right font-semibold">
                                  {result.target_score.toFixed(3)}
                                </TableCell>
                                <TableCell className="text-right">
                                  {result.avg_sharpe_ratio.toFixed(2)}
                                </TableCell>
                                <TableCell className="text-right">
                                  <span className={result.avg_total_return >= 0 ? 'text-green-600' : 'text-red-600'}>
                                    {result.avg_total_return >= 0 ? '+' : ''}{result.avg_total_return.toFixed(2)}%
                                  </span>
                                </TableCell>
                                <TableCell className="text-right">
                                  {result.avg_win_rate.toFixed(1)}%
                                </TableCell>
                                <TableCell className="text-right text-red-600">
                                  -{Math.abs(result.avg_max_drawdown).toFixed(2)}%
                                </TableCell>
                                <TableCell className="text-right">
                                  {result.total_symbols_matched}
                                </TableCell>
                                <TableCell className="text-right">
                                  {result.total_backtests}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </CardContent>
                  </Card>
                </>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}