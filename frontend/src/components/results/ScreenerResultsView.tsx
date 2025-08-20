import React, { useState } from 'react'
import { format, parseISO } from 'date-fns'
import { Eye, Trash2, Clock, Filter, Hash } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useResultsContext } from '@/contexts/ResultsContext'
import { useResults } from '@/hooks/useResults'
import { Pagination } from '@/components/ui/pagination'

export function ScreenerResultsView() {
  const { state, dispatch } = useResultsContext()
  const { deleteScreenerResult, getScreenerResultDetails } = useResults()
  const [selectedResult, setSelectedResult] = useState<any>(null)
  const [showDetailsDialog, setShowDetailsDialog] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  const handleViewDetails = async (resultId: string) => {
    try {
      const details = await getScreenerResultDetails(resultId)
      setSelectedResult(details)
      setShowDetailsDialog(true)
    } catch (error) {
      console.error('Failed to fetch result details:', error)
    }
  }

  const handleDelete = async (resultId: string) => {
    try {
      await deleteScreenerResult(resultId)
      setDeleteConfirmId(null)
    } catch (error) {
      console.error('Failed to delete result:', error)
    }
  }

  const formatFilters = (filters: any) => {
    // Use the description from the API if available (new structure)
    if (filters.description) {
      return filters.description
    }

    // Fallback to detailed formatting for comprehensive display
    const descriptions = []
    
    // Price range
    if (filters.min_price !== undefined || filters.max_price !== undefined) {
      if (filters.min_price !== undefined && filters.max_price !== undefined) {
        descriptions.push(`Price: $${filters.min_price.toFixed(2)} - $${filters.max_price.toFixed(2)}`)
      } else if (filters.min_price !== undefined) {
        descriptions.push(`Price: ≥ $${filters.min_price.toFixed(2)}`)
      } else if (filters.max_price !== undefined) {
        descriptions.push(`Price: ≤ $${filters.max_price.toFixed(2)}`)
      }
    }
    
    // Price vs MA
    if (filters.price_vs_ma?.enabled) {
      const period = filters.price_vs_ma.ma_period || 20
      const condition = filters.price_vs_ma.condition || 'above'
      descriptions.push(`Price ${condition} SMA${period}`)
    }
    
    // Price vs VWAP
    if (filters.price_vs_vwap?.enabled) {
      const condition = filters.price_vs_vwap.condition || 'above'
      descriptions.push(`Price ${condition} VWAP`)
    }
    
    // Market Cap
    if (filters.market_cap?.enabled) {
      const mc = filters.market_cap
      if (mc.min_market_cap !== undefined && mc.max_market_cap !== undefined) {
        const minMc = mc.min_market_cap / 1_000_000 // Convert to millions
        const maxMc = mc.max_market_cap / 1_000_000
        descriptions.push(`Market Cap: $${minMc.toFixed(0)}M - $${maxMc.toFixed(0)}M`)
      } else if (mc.min_market_cap !== undefined) {
        const minMc = mc.min_market_cap / 1_000_000
        descriptions.push(`Market Cap: ≥ $${minMc.toFixed(0)}M`)
      } else if (mc.max_market_cap !== undefined) {
        const maxMc = mc.max_market_cap / 1_000_000
        descriptions.push(`Market Cap: ≤ $${maxMc.toFixed(0)}M`)
      }
    }
    
    // Change (Daily percentage change)
    if (filters.change?.enabled) {
      const change = filters.change
      if (change.min_change !== undefined && change.max_change !== undefined) {
        descriptions.push(`Change: ${change.min_change.toFixed(1)}% - ${change.max_change.toFixed(1)}%`)
      } else if (change.min_change !== undefined) {
        descriptions.push(`Change: ≥ ${change.min_change.toFixed(1)}%`)
      } else if (change.max_change !== undefined) {
        descriptions.push(`Change: ≤ ${change.max_change.toFixed(1)}%`)
      }
    }
    
    // ATR
    if (filters.atr?.enabled) {
      const minAtr = filters.atr.min_atr || 0
      descriptions.push(`ATR ≥ $${minAtr.toFixed(2)}`)
    }
    
    // RSI
    if (filters.rsi?.enabled) {
      const period = filters.rsi.rsi_period || 14
      const threshold = filters.rsi.threshold || 0
      const condition = filters.rsi.condition || 'below'
      descriptions.push(`RSI${period} ${condition} ${threshold}`)
    }
    
    // Gap
    if (filters.gap?.enabled) {
      const threshold = filters.gap.gap_threshold || 0
      const direction = filters.gap.direction || 'any'
      if (direction === 'any') {
        descriptions.push(`Gap ≥ ${threshold}%`)
      } else {
        descriptions.push(`Gap ${direction} ≥ ${threshold}%`)
      }
    }
    
    // Previous Day Dollar Volume
    if (filters.prev_day_dollar_volume?.enabled) {
      const minVol = filters.prev_day_dollar_volume.min_dollar_volume || 0
      if (minVol >= 1000000) {
        descriptions.push(`Volume ≥ $${(minVol / 1000000).toFixed(1)}M`)
      } else if (minVol >= 1000) {
        descriptions.push(`Volume ≥ $${(minVol / 1000).toFixed(0)}K`)
      } else {
        descriptions.push(`Volume ≥ $${minVol.toLocaleString()}`)
      }
    }
    
    // Relative Volume
    if (filters.relative_volume?.enabled) {
      const ratio = filters.relative_volume.min_ratio || 1.0
      descriptions.push(`RelVol ≥ ${ratio}x`)
    }
    
    return descriptions.length > 0 ? descriptions.join('; ') : 'No filters applied'
  }

  if (state.screenerResults.loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading screener results...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (state.screenerResults.error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{state.screenerResults.error}</AlertDescription>
      </Alert>
    )
  }

  if (state.screenerResults.data.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-8 text-center">
          <Filter className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Screener Results</h3>
          <p className="text-muted-foreground">
            Run a stock screener to see results here
          </p>
        </CardContent>
      </Card>
    )
  }

  const totalPages = Math.ceil(state.screenerResults.totalCount / state.screenerResults.pageSize)

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Screener Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">Created Date</TableHead>
                  <TableHead className="w-32">Screening Date</TableHead>
                  <TableHead className="w-24">Price Range</TableHead>
                  <TableHead className="w-24">Price vs MA</TableHead>
                  <TableHead className="w-20">RSI</TableHead>
                  <TableHead className="w-20">Gap</TableHead>
                  <TableHead className="w-24">Volume</TableHead>
                  <TableHead className="w-20">Rel Vol</TableHead>
                  <TableHead className="text-right w-24">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {state.screenerResults.data.map((result) => (
                  <TableRow key={result.id}>
                    <TableCell>
                      {/* Show created date from timestamp/created_at */}
                      <div className="text-sm">
                        {result.timestamp || result.created_at ? 
                          format(parseISO(result.timestamp || result.created_at), 'MMM d, yyyy HH:mm') : 
                          'N/A'
                        }
                      </div>
                    </TableCell>
                    
                    <TableCell>
                      {/* Show screening date from filters */}
                      <div className="text-sm">
                        {result.filters.start_date && result.filters.end_date ? (
                          result.filters.start_date === result.filters.end_date ? 
                            format(parseISO(result.filters.start_date), 'MMM d, yyyy') :
                            `${format(parseISO(result.filters.start_date), 'MMM d')} - ${format(parseISO(result.filters.end_date), 'MMM d, yyyy')}`
                        ) : result.filters.start_date ? 
                          `From ${format(parseISO(result.filters.start_date), 'MMM d, yyyy')}` :
                          result.filters.end_date ?
                          `Until ${format(parseISO(result.filters.end_date), 'MMM d, yyyy')}` :
                          'N/A'
                        }
                      </div>
                    </TableCell>
                    
                    {/* Price Range */}
                    <TableCell>
                      <div className="text-xs">
                        {result.filters.min_price !== undefined || result.filters.max_price !== undefined ? (
                          result.filters.min_price !== undefined && result.filters.max_price !== undefined ? 
                            `$${result.filters.min_price.toFixed(0)}-${result.filters.max_price.toFixed(0)}` :
                            result.filters.min_price !== undefined ? 
                              `≥$${result.filters.min_price.toFixed(0)}` :
                              `≤$${result.filters.max_price.toFixed(0)}`
                        ) : '-'}
                      </div>
                    </TableCell>
                    
                    {/* Price vs MA */}
                    <TableCell>
                      <div className="text-xs">
                        {result.filters.price_vs_ma?.enabled ? 
                          `${result.filters.price_vs_ma.condition === 'above' ? '>' : '<'} SMA${result.filters.price_vs_ma.ma_period || 20}` : 
                          '-'
                        }
                      </div>
                    </TableCell>
                    
                    {/* RSI */}
                    <TableCell>
                      <div className="text-xs">
                        {result.filters.rsi?.enabled ? 
                          `${result.filters.rsi.condition === 'above' ? '>' : '<'}${result.filters.rsi.threshold}` : 
                          '-'
                        }
                      </div>
                    </TableCell>
                    
                    {/* Gap */}
                    <TableCell>
                      <div className="text-xs">
                        {result.filters.gap?.enabled ? 
                          `${result.filters.gap.direction !== 'any' ? result.filters.gap.direction + ' ' : ''}≥${result.filters.gap.gap_threshold}%` : 
                          '-'
                        }
                      </div>
                    </TableCell>
                    
                    {/* Volume */}
                    <TableCell>
                      <div className="text-xs">
                        {result.filters.prev_day_dollar_volume?.enabled ? (
                          result.filters.prev_day_dollar_volume.min_dollar_volume >= 1_000_000 ? 
                            `≥$${(result.filters.prev_day_dollar_volume.min_dollar_volume / 1_000_000).toFixed(1)}M` :
                            `≥$${(result.filters.prev_day_dollar_volume.min_dollar_volume / 1_000).toFixed(0)}K`
                        ) : '-'}
                      </div>
                    </TableCell>
                    
                    {/* Relative Volume */}
                    <TableCell>
                      <div className="text-xs">
                        {result.filters.relative_volume?.enabled ? 
                          `≥${result.filters.relative_volume.min_ratio}x` : 
                          '-'
                        }
                      </div>
                    </TableCell>
                    
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewDetails(result.id)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteConfirmId(result.id)}
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
                currentPage={state.screenerResults.page}
                totalPages={totalPages}
                onPageChange={(page) => dispatch({ type: 'SET_SCREENER_PAGE', page })}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Details Dialog */}
      <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Screener Result Details</DialogTitle>
            <DialogDescription>
              {selectedResult && (selectedResult.timestamp || selectedResult.created_at) ? 
                format(parseISO(selectedResult.timestamp || selectedResult.created_at), 'PPPp') : 
                'Date not available'
              }
            </DialogDescription>
          </DialogHeader>
          {selectedResult && (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Filters Applied</h4>
                <div className="space-y-3">
                  {selectedResult.filters.description ? (
                    <div className="bg-muted p-3 rounded-md">
                      <p className="text-sm font-medium">{selectedResult.filters.description}</p>
                    </div>
                  ) : (
                    <div className="bg-muted p-3 rounded-md">
                      <p className="text-sm text-muted-foreground">No filter description available</p>
                    </div>
                  )}
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {/* Price Range */}
                    {(selectedResult.filters.min_price !== undefined || selectedResult.filters.max_price !== undefined) && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Price Range</h5>
                        <p className="text-sm text-muted-foreground">
                          {selectedResult.filters.min_price !== undefined && selectedResult.filters.max_price !== undefined
                            ? `$${selectedResult.filters.min_price.toFixed(2)} - $${selectedResult.filters.max_price.toFixed(2)}`
                            : selectedResult.filters.min_price !== undefined
                            ? `≥ $${selectedResult.filters.min_price.toFixed(2)}`
                            : `≤ $${selectedResult.filters.max_price.toFixed(2)}`
                          }
                        </p>
                      </div>
                    )}
                    
                    {/* Price vs MA */}
                    {selectedResult.filters.price_vs_ma?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Price vs Moving Average</h5>
                        <p className="text-sm text-muted-foreground">
                          Price {selectedResult.filters.price_vs_ma.condition || 'above'} SMA{selectedResult.filters.price_vs_ma.ma_period || 20}
                        </p>
                      </div>
                    )}
                    
                    {/* Price vs VWAP */}
                    {selectedResult.filters.price_vs_vwap?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Price vs VWAP</h5>
                        <p className="text-sm text-muted-foreground">
                          Price {selectedResult.filters.price_vs_vwap.condition || 'above'} VWAP
                        </p>
                      </div>
                    )}
                    
                    {/* Market Cap */}
                    {selectedResult.filters.market_cap?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Market Cap</h5>
                        <p className="text-sm text-muted-foreground">
                          {selectedResult.filters.market_cap.min_market_cap !== undefined && selectedResult.filters.market_cap.max_market_cap !== undefined
                            ? `$${(selectedResult.filters.market_cap.min_market_cap / 1_000_000).toFixed(0)}M - $${(selectedResult.filters.market_cap.max_market_cap / 1_000_000).toFixed(0)}M`
                            : selectedResult.filters.market_cap.min_market_cap !== undefined
                            ? `≥ $${(selectedResult.filters.market_cap.min_market_cap / 1_000_000).toFixed(0)}M`
                            : `≤ $${(selectedResult.filters.market_cap.max_market_cap / 1_000_000).toFixed(0)}M`
                          }
                        </p>
                      </div>
                    )}
                    
                    {/* Change */}
                    {selectedResult.filters.change?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Daily Change</h5>
                        <p className="text-sm text-muted-foreground">
                          {selectedResult.filters.change.min_change !== undefined && selectedResult.filters.change.max_change !== undefined
                            ? `${selectedResult.filters.change.min_change.toFixed(1)}% - ${selectedResult.filters.change.max_change.toFixed(1)}%`
                            : selectedResult.filters.change.min_change !== undefined
                            ? `≥ ${selectedResult.filters.change.min_change.toFixed(1)}%`
                            : `≤ ${selectedResult.filters.change.max_change.toFixed(1)}%`
                          }
                        </p>
                      </div>
                    )}
                    
                    {/* ATR */}
                    {selectedResult.filters.atr?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">ATR (Average True Range)</h5>
                        <p className="text-sm text-muted-foreground">
                          ≥ ${(selectedResult.filters.atr.min_atr || 0).toFixed(2)}
                        </p>
                      </div>
                    )}
                    
                    {/* RSI */}
                    {selectedResult.filters.rsi?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">RSI</h5>
                        <p className="text-sm text-muted-foreground">
                          RSI{selectedResult.filters.rsi.rsi_period || 14} {selectedResult.filters.rsi.condition || 'below'} {selectedResult.filters.rsi.threshold || 0}
                        </p>
                      </div>
                    )}
                    
                    {/* Gap */}
                    {selectedResult.filters.gap?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Gap Filter</h5>
                        <p className="text-sm text-muted-foreground">
                          Gap {selectedResult.filters.gap.direction === 'any' ? '' : selectedResult.filters.gap.direction + ' '}≥ {selectedResult.filters.gap.gap_threshold || 0}%
                        </p>
                      </div>
                    )}
                    
                    {/* Previous Day Dollar Volume */}
                    {selectedResult.filters.prev_day_dollar_volume?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Previous Day Volume</h5>
                        <p className="text-sm text-muted-foreground">
                          ≥ ${(selectedResult.filters.prev_day_dollar_volume.min_dollar_volume || 0).toLocaleString()}
                        </p>
                      </div>
                    )}
                    
                    {/* Relative Volume */}
                    {selectedResult.filters.relative_volume?.enabled && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Relative Volume</h5>
                        <p className="text-sm text-muted-foreground">
                          {selectedResult.filters.relative_volume.recent_days || 1}d vs {selectedResult.filters.relative_volume.lookback_days || 20}d ≥ {selectedResult.filters.relative_volume.min_ratio || 1.0}x
                        </p>
                      </div>
                    )}
                    
                    {/* Date Range */}
                    {(selectedResult.filters.start_date || selectedResult.filters.end_date) && (
                      <div className="bg-background border rounded-md p-3">
                        <h5 className="font-medium text-sm mb-1">Date Range</h5>
                        <p className="text-sm text-muted-foreground">
                          {selectedResult.filters.start_date && selectedResult.filters.end_date && selectedResult.filters.start_date === selectedResult.filters.end_date
                            ? format(parseISO(selectedResult.filters.start_date), 'PPP')
                            : selectedResult.filters.start_date && selectedResult.filters.end_date
                            ? `${format(parseISO(selectedResult.filters.start_date), 'PPP')} - ${format(parseISO(selectedResult.filters.end_date), 'PPP')}`
                            : selectedResult.filters.start_date
                            ? `From ${format(parseISO(selectedResult.filters.start_date), 'PPP')}`
                            : `Until ${format(parseISO(selectedResult.filters.end_date), 'PPP')}`
                          }
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div>
                <h4 className="font-semibold mb-2">
                  Symbols ({selectedResult.symbols.length})
                </h4>
                <div className="max-h-60 overflow-y-auto border rounded-md p-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                    {selectedResult.symbols.map((symbol: any) => (
                      <div key={symbol.symbol} className="flex items-center justify-between p-2 bg-muted rounded">
                        <span className="font-mono">{symbol.symbol}</span>
                        {symbol.latest_price !== undefined && symbol.latest_price !== null && (
                          <span className="text-sm text-muted-foreground">
                            ${symbol.latest_price.toFixed(2)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Screener Result?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The screener result will be permanently deleted.
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