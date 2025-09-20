import { useState, useEffect } from 'react'
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
import { Switch } from '@/components/ui/switch'
import { 
  TrendingUp, Settings, AlertCircle, RefreshCw, Search, 
  Download, BarChart3, Target
} from 'lucide-react'
import { format, subDays } from 'date-fns'
import { filterOptimizerService } from '@/services/filterOptimizer'
import type { 
  OptimizationRequest,
  OptimizationResponse,
  SuggestedRanges,
  FilterSearchSpace,
  OptimizationResult
} from '@/types/filterOptimizer'
import { OptimizationTarget } from '@/types/filterOptimizer'

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
  const [minSymbols, setMinSymbols] = useState(1)
  const [maxResults, setMaxResults] = useState(20)
  
  // Search space state
  const [searchSpace, setSearchSpace] = useState<FilterSearchSpace>({
    price_range: { min_value: 1, max_value: 20, step: 10 },
    rsi_range: undefined,
    gap_range: undefined,
    volume_range: undefined,
    rel_volume_range: undefined,
    pivot_bars_range: undefined,
    ma_periods: [],
    ma_conditions: []
  })
  
  // Filter enabled state
  const [filtersEnabled, setFiltersEnabled] = useState({
    price: true,
    rsi: false,
    gap: false,
    volume: false,
    relVolume: false,
    pivotBars: false,
    movingAverage: false
  })
  
  // Calculate total combinations
  const calculateTotalCombinations = () => {
    let totalCombinations = 1
    
    // Helper function to calculate number of sliding windows
    const calculateWindows = (min: number, max: number, step: number) => {
      const windows = []
      let current = min
      while (current < max) {
        windows.push(1)
        current += step
      }
      return windows.length
    }
    
    // Price range sliding windows
    if (filtersEnabled.price && searchSpace.price_range) {
      const priceWindows = calculateWindows(
        searchSpace.price_range.min_value, 
        searchSpace.price_range.max_value, 
        searchSpace.price_range.step
      )
      if (priceWindows > 0) totalCombinations *= priceWindows
    }
    
    // RSI range sliding windows
    if (filtersEnabled.rsi && searchSpace.rsi_range) {
      const rsiWindows = calculateWindows(
        searchSpace.rsi_range.min_value,
        searchSpace.rsi_range.max_value,
        searchSpace.rsi_range.step
      )
      if (rsiWindows > 0) totalCombinations *= rsiWindows
    }
    
    // Gap range sliding windows
    if (filtersEnabled.gap && searchSpace.gap_range) {
      const gapWindows = calculateWindows(
        searchSpace.gap_range.min_value,
        searchSpace.gap_range.max_value,
        searchSpace.gap_range.step
      )
      if (gapWindows > 0) totalCombinations *= gapWindows
    }
    
    // Volume range sliding windows
    if (filtersEnabled.volume && searchSpace.volume_range) {
      const volumeWindows = calculateWindows(
        searchSpace.volume_range.min_value,
        searchSpace.volume_range.max_value,
        searchSpace.volume_range.step
      )
      if (volumeWindows > 0) totalCombinations *= volumeWindows
    }
    
    // Relative volume range sliding windows
    if (filtersEnabled.relVolume && searchSpace.rel_volume_range) {
      const relVolumeWindows = calculateWindows(
        searchSpace.rel_volume_range.min_value,
        searchSpace.rel_volume_range.max_value,
        searchSpace.rel_volume_range.step
      )
      if (relVolumeWindows > 0) totalCombinations *= relVolumeWindows
    }
    
    // Pivot bars range sliding windows
    if (filtersEnabled.pivotBars && searchSpace.pivot_bars_range) {
      const pivotWindows = calculateWindows(
        searchSpace.pivot_bars_range.min_value,
        searchSpace.pivot_bars_range.max_value,
        searchSpace.pivot_bars_range.step
      )
      if (pivotWindows > 0) totalCombinations *= pivotWindows
    }
    
    // MA periods and conditions
    if (filtersEnabled.movingAverage && searchSpace.ma_periods && searchSpace.ma_periods.length > 0 && 
        searchSpace.ma_conditions && searchSpace.ma_conditions.length > 0) {
      totalCombinations *= searchSpace.ma_periods.length * searchSpace.ma_conditions.length
    }
    
    return totalCombinations
  }
  
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
      // Clean up search space - only include enabled filters
      const cleanedSearchSpace = {
        price_range: filtersEnabled.price ? searchSpace.price_range : undefined,
        rsi_range: filtersEnabled.rsi ? searchSpace.rsi_range : undefined,
        gap_range: filtersEnabled.gap ? searchSpace.gap_range : undefined,
        volume_range: filtersEnabled.volume ? searchSpace.volume_range : undefined,
        rel_volume_range: filtersEnabled.relVolume ? searchSpace.rel_volume_range : undefined,
        pivot_bars_range: filtersEnabled.pivotBars ? searchSpace.pivot_bars_range : undefined,
        ma_periods: filtersEnabled.movingAverage && searchSpace.ma_periods && searchSpace.ma_periods.length > 0 ? searchSpace.ma_periods : undefined,
        ma_conditions: filtersEnabled.movingAverage && searchSpace.ma_conditions && searchSpace.ma_conditions.length > 0 ? searchSpace.ma_conditions : undefined
      }
      
      const request: OptimizationRequest = {
        start_date: format(startDate, 'yyyy-MM-dd'),
        end_date: format(endDate, 'yyyy-MM-dd'),
        target,
        custom_formula: target === OptimizationTarget.CUSTOM ? customFormula : undefined,
        search_space: cleanedSearchSpace,
        max_results: maxResults,
        min_symbols_required: minSymbols
      }
      
      console.log('Sending optimization request:', JSON.stringify(request, null, 2))
      
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
      price_range: {
        min_value: suggested.price_range.min.suggested_min,
        max_value: suggested.price_range.max.suggested_max,
        step: 10 // Reasonable step for sliding window
      },
      rsi_range: {
        min_value: 0,
        max_value: 100,
        step: 10
      },
      gap_range: {
        min_value: -10,
        max_value: 10,
        step: 2
      },
      volume_range: suggested.volume?.min ? {
        min_value: suggested.volume.min.suggested_min,
        max_value: suggested.volume.min.suggested_max * 10, // Expand range for sliding window
        step: suggested.volume.min.suggested_step * 2
      } : {
        min_value: 1000000,
        max_value: 50000000,
        step: 5000000
      },
      rel_volume_range: suggested.relative_volume?.min ? {
        min_value: suggested.relative_volume.min.suggested_min,
        max_value: suggested.relative_volume.min.suggested_max,
        step: suggested.relative_volume.min.suggested_step
      } : {
        min_value: 1.0,
        max_value: 5.0,
        step: 0.5
      },
      pivot_bars_range: { min_value: 4, max_value: 12, step: 1 },
      ma_periods: [20, 50, 200],
      ma_conditions: ['above', 'below']
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
            Grid Parameters Tuning
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
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">Analysis Configuration</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
                  <div className="space-y-2">
                    <Label>Optimization Target</Label>
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
                  </div>
                </div>
                {target === OptimizationTarget.CUSTOM && (
                  <div className="space-y-2">
                    <Label>Custom Formula</Label>
                    <Input
                      placeholder="e.g., 0.4*sharpe + 0.3*win_rate - 0.3*drawdown"
                      value={customFormula}
                      onChange={(e) => setCustomFormula(e.target.value)}
                    />
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Minimum Symbols Required</Label>
                    <Input
                      type="number"
                      min="1"
                      value={minSymbols}
                      onChange={(e) => setMinSymbols(Math.max(1, Number(e.target.value) || 1))}
                    />
                    <p className="text-xs text-muted-foreground">
                      Only keep combinations that match at least this many symbols.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label>Maximum Results</Label>
                    <Input
                      type="number"
                      min="1"
                      value={maxResults}
                      onChange={(e) => setMaxResults(Math.max(1, Number(e.target.value) || 1))}
                    />
                    <p className="text-xs text-muted-foreground">
                      Limit the number of optimized combinations returned.
                    </p>
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
                  <Card className={!filtersEnabled.price ? 'opacity-50' : ''}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">Price Range ($)</CardTitle>
                        <Switch
                          checked={filtersEnabled.price}
                          onCheckedChange={(checked) => setFiltersEnabled({...filtersEnabled, price: checked})}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <Label className="text-muted-foreground">Min Price ($)</Label>
                        <Label className="text-muted-foreground">Max Price ($)</Label>
                        <Label className="text-muted-foreground">Step Size ($)</Label>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <Input
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={searchSpace.price_range?.min_value || 1}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            price_range: {
                              ...searchSpace.price_range!,
                              min_value: parseFloat(e.target.value) || 1
                            }
                          })}
                          className="h-8 text-sm"
                        />
                        <Input
                          type="number"
                          min="1"
                          value={searchSpace.price_range?.max_value || 100}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            price_range: {
                              ...searchSpace.price_range!,
                              max_value: parseFloat(e.target.value) || 100
                            }
                          })}
                          className="h-8 text-sm"
                        />
                        <Input
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={searchSpace.price_range?.step || 10}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            price_range: {
                              ...searchSpace.price_range!,
                              step: parseFloat(e.target.value) || 10
                            }
                          })}
                          className="h-8 text-sm"
                        />
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Tests sliding windows: [$1-$11], [$11-$21], [$21-$31], etc.
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* RSI Range */}
                  <Card className={!filtersEnabled.rsi ? 'opacity-50' : ''}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">RSI Range</CardTitle>
                        <Switch
                          checked={filtersEnabled.rsi}
                          onCheckedChange={(checked) => {
                            setFiltersEnabled({...filtersEnabled, rsi: checked})
                            if (checked && !searchSpace.rsi_range) {
                              setSearchSpace({
                                ...searchSpace,
                                rsi_range: { min_value: 0, max_value: 100, step: 10 }
                              })
                            }
                          }}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <Label className="text-muted-foreground">Min RSI</Label>
                        <Label className="text-muted-foreground">Max RSI</Label>
                        <Label className="text-muted-foreground">Step Size</Label>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <Input
                          type="number"
                          min="0"
                          max="100"
                          value={searchSpace.rsi_range?.min_value || 0}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            rsi_range: {
                              ...searchSpace.rsi_range!,
                              min_value: parseFloat(e.target.value) || 0
                            }
                          })}
                          className="h-8 text-sm"
                        />
                        <Input
                          type="number"
                          min="0"
                          max="100"
                          value={searchSpace.rsi_range?.max_value || 100}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            rsi_range: {
                              ...searchSpace.rsi_range!,
                              max_value: parseFloat(e.target.value) || 100
                            }
                          })}
                          className="h-8 text-sm"
                        />
                        <Input
                          type="number"
                          min="1"
                          value={searchSpace.rsi_range?.step || 10}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            rsi_range: {
                              ...searchSpace.rsi_range!,
                              step: parseFloat(e.target.value) || 10
                            }
                          })}
                          className="h-8 text-sm"
                        />
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Tests sliding windows: [0-10], [10-20], [20-30], etc.
                      </div>
                    </CardContent>
                  </Card>

                  {/* Gap Range */}
                  <Card className={!filtersEnabled.gap ? 'opacity-50' : ''}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">Gap Range (%)</CardTitle>
                        <Switch
                          checked={filtersEnabled.gap}
                          onCheckedChange={(checked) => {
                            setFiltersEnabled({...filtersEnabled, gap: checked})
                            if (checked && !searchSpace.gap_range) {
                              setSearchSpace({
                                ...searchSpace,
                                gap_range: { min_value: -10, max_value: 10, step: 2 }
                              })
                            }
                          }}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <Label className="text-muted-foreground">Min Gap %</Label>
                        <Label className="text-muted-foreground">Max Gap %</Label>
                        <Label className="text-muted-foreground">Step Size</Label>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <Input
                          type="number"
                          value={searchSpace.gap_range?.min_value || -10}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            gap_range: {
                              ...searchSpace.gap_range!,
                              min_value: parseFloat(e.target.value) || -10
                            }
                          })}
                          className="h-8 text-sm"
                        />
                        <Input
                          type="number"
                          value={searchSpace.gap_range?.max_value || 10}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            gap_range: {
                              ...searchSpace.gap_range!,
                              max_value: parseFloat(e.target.value) || 10
                            }
                          })}
                          className="h-8 text-sm"
                        />
                        <Input
                          type="number"
                          min="0.1"
                          step="0.1"
                          value={searchSpace.gap_range?.step || 2}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            gap_range: {
                              ...searchSpace.gap_range!,
                              step: parseFloat(e.target.value) || 2
                            }
                          })}
                          className="h-8 text-sm"
                        />
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Tests sliding windows: [-10 to -8], [-8 to -6], [-6 to -4], etc.
                      </div>
                    </CardContent>
                  </Card>

                  {/* Volume Filters */}
                  <Card className={!filtersEnabled.volume && !filtersEnabled.relVolume ? 'opacity-50' : ''}>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Volume Filters</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {/* Dollar Volume */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <Label className="text-sm font-medium">Dollar Volume Range</Label>
                          <Switch
                            checked={filtersEnabled.volume}
                            onCheckedChange={(checked) => {
                              setFiltersEnabled({...filtersEnabled, volume: checked})
                              if (checked && !searchSpace.volume_range) {
                                setSearchSpace({
                                  ...searchSpace,
                                  volume_range: { min_value: 1000000, max_value: 50000000, step: 5000000 }
                                })
                              }
                            }}
                          />
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <Label className="text-xs text-muted-foreground">Min ($)</Label>
                            <Input
                              type="number"
                              value={searchSpace.volume_range?.min_value || 1000000}
                              onChange={(e) => setSearchSpace({
                                ...searchSpace,
                                volume_range: {
                                  ...searchSpace.volume_range!,
                                  min_value: parseFloat(e.target.value) || 1000000
                                }
                              })}
                              className="h-8 text-sm"
                            />
                          </div>
                          <div>
                            <Label className="text-xs text-muted-foreground">Max ($)</Label>
                            <Input
                              type="number"
                              value={searchSpace.volume_range?.max_value || 50000000}
                              onChange={(e) => setSearchSpace({
                                ...searchSpace,
                                volume_range: {
                                  ...searchSpace.volume_range!,
                                  max_value: parseFloat(e.target.value) || 50000000
                                }
                              })}
                              className="h-8 text-sm"
                            />
                          </div>
                          <div>
                            <Label className="text-xs text-muted-foreground">Step ($)</Label>
                            <Input
                              type="number"
                              value={searchSpace.volume_range?.step || 5000000}
                              onChange={(e) => setSearchSpace({
                                ...searchSpace,
                                volume_range: {
                                  ...searchSpace.volume_range!,
                                  step: parseFloat(e.target.value) || 5000000
                                }
                              })}
                              className="h-8 text-sm"
                            />
                          </div>
                        </div>
                      </div>
                      
                      {/* Relative Volume */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <Label className="text-sm font-medium">Relative Volume Range</Label>
                          <Switch
                            checked={filtersEnabled.relVolume}
                            onCheckedChange={(checked) => {
                              setFiltersEnabled({...filtersEnabled, relVolume: checked})
                              if (checked && !searchSpace.rel_volume_range) {
                                setSearchSpace({
                                  ...searchSpace,
                                  rel_volume_range: { min_value: 1, max_value: 5, step: 0.5 }
                                })
                              }
                            }}
                          />
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <Label className="text-xs text-muted-foreground">Min Ratio</Label>
                            <Input
                              type="number"
                              step="0.1"
                              value={searchSpace.rel_volume_range?.min_value || 1}
                              onChange={(e) => setSearchSpace({
                                ...searchSpace,
                                rel_volume_range: {
                                  ...searchSpace.rel_volume_range!,
                                  min_value: parseFloat(e.target.value) || 1
                                }
                              })}
                              className="h-8 text-sm"
                            />
                          </div>
                          <div>
                            <Label className="text-xs text-muted-foreground">Max Ratio</Label>
                            <Input
                              type="number"
                              step="0.1"
                              value={searchSpace.rel_volume_range?.max_value || 5}
                              onChange={(e) => setSearchSpace({
                                ...searchSpace,
                                rel_volume_range: {
                                  ...searchSpace.rel_volume_range!,
                                  max_value: parseFloat(e.target.value) || 5
                                }
                              })}
                              className="h-8 text-sm"
                            />
                          </div>
                          <div>
                            <Label className="text-xs text-muted-foreground">Step</Label>
                            <Input
                              type="number"
                              step="0.1"
                              value={searchSpace.rel_volume_range?.step || 0.5}
                              onChange={(e) => setSearchSpace({
                                ...searchSpace,
                                rel_volume_range: {
                                  ...searchSpace.rel_volume_range!,
                                  step: parseFloat(e.target.value) || 0.5
                                }
                              })}
                              className="h-8 text-sm"
                            />
                          </div>
                        </div>
                      </div>
                      
                      <div className="text-sm text-muted-foreground">
                        Tests sliding windows for both dollar volume and relative volume ratios.
                      </div>
                    </CardContent>
                  </Card>

                  {/* Moving Average Filter */}
                  <Card className={!filtersEnabled.movingAverage ? 'opacity-50' : ''}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">Moving Average Filter</CardTitle>
                        <Switch
                          checked={filtersEnabled.movingAverage}
                          onCheckedChange={(checked) => {
                            setFiltersEnabled({...filtersEnabled, movingAverage: checked})
                            if (checked && (!searchSpace.ma_periods || searchSpace.ma_periods.length === 0)) {
                              setSearchSpace({
                                ...searchSpace,
                                ma_periods: [20, 50, 200],
                                ma_conditions: ['above', 'below']
                              })
                            }
                          }}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="space-y-3">
                        <div>
                          <Label className="text-sm text-muted-foreground">MA Periods to Test</Label>
                          <div className="flex gap-2 mt-2">
                            {[20, 50, 200].map((period) => (
                              <label key={period} className="flex items-center space-x-2">
                                <input
                                  type="checkbox"
                                  checked={searchSpace.ma_periods?.includes(period) || false}
                                  onChange={(e) => {
                                    const current = searchSpace.ma_periods || []
                                    const updated = e.target.checked
                                      ? [...current, period]
                                      : current.filter(p => p !== period)
                                    setSearchSpace({
                                      ...searchSpace,
                                      ma_periods: updated
                                    })
                                  }}
                                  className="rounded"
                                />
                                <span className="text-sm">{period} MA</span>
                              </label>
                            ))}
                          </div>
                        </div>
                        <div>
                          <Label className="text-sm text-muted-foreground">Conditions to Test</Label>
                          <div className="flex gap-2 mt-2">
                            {['above', 'below'].map((condition) => (
                              <label key={condition} className="flex items-center space-x-2">
                                <input
                                  type="checkbox"
                                  checked={searchSpace.ma_conditions?.includes(condition) || false}
                                  onChange={(e) => {
                                    const current = searchSpace.ma_conditions || []
                                    const updated = e.target.checked
                                      ? [...current, condition]
                                      : current.filter(c => c !== condition)
                                    setSearchSpace({
                                      ...searchSpace,
                                      ma_conditions: updated
                                    })
                                  }}
                                  className="rounded"
                                />
                                <span className="text-sm capitalize">{condition}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Pivot Bars */}
                  <Card className={!filtersEnabled.pivotBars ? 'opacity-50' : ''}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">Pivot Bars Range</CardTitle>
                        <Switch
                          checked={filtersEnabled.pivotBars}
                          onCheckedChange={(checked) => {
                            setFiltersEnabled({...filtersEnabled, pivotBars: checked})
                            if (checked && !searchSpace.pivot_bars_range) {
                              setSearchSpace({
                                ...searchSpace,
                                pivot_bars_range: { min_value: 4, max_value: 12, step: 1 }
                              })
                            }
                          }}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <Label className="text-muted-foreground">Min Bars</Label>
                        <Label className="text-muted-foreground">Max Bars</Label>
                        <Label className="text-muted-foreground">Step Size</Label>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <Input
                          type="number"
                          min="1"
                          value={searchSpace.pivot_bars_range?.min_value || 4}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            pivot_bars_range: {
                              ...searchSpace.pivot_bars_range!,
                              min_value: parseFloat(e.target.value) || 4
                            }
                          })}
                          className="h-8 text-sm"
                        />
                        <Input
                          type="number"
                          min="1"
                          value={searchSpace.pivot_bars_range?.max_value || 12}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            pivot_bars_range: {
                              ...searchSpace.pivot_bars_range!,
                              max_value: parseFloat(e.target.value) || 12
                            }
                          })}
                          className="h-8 text-sm"
                        />
                        <Input
                          type="number"
                          min="1"
                          value={searchSpace.pivot_bars_range?.step || 1}
                          onChange={(e) => setSearchSpace({
                            ...searchSpace,
                            pivot_bars_range: {
                              ...searchSpace.pivot_bars_range!,
                              step: parseFloat(e.target.value) || 1
                            }
                          })}
                          className="h-8 text-sm"
                        />
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Tests sliding windows: [4-5], [5-6], [6-7], etc. for pattern recognition.
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
              
              {/* Combinations Summary */}
              <div className="flex justify-center">
                <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2 text-sm">
                    <BarChart3 className="h-4 w-4 text-blue-600" />
                    <span className="text-blue-800">
                      <strong>{calculateTotalCombinations().toLocaleString()}</strong> combinations will be tested
                    </span>
                  </div>
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
