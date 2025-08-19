import * as React from 'react'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ArrowUpDown, TrendingUp, TrendingDown } from 'lucide-react'
import { useScreenerContext } from '@/contexts/ScreenerContext'

interface ResultsTableProps {
  results: any[]
}

export function ResultsTable({ results }: ResultsTableProps) {
  const { state, dispatch } = useScreenerContext()

  const handleSort = (column: string) => {
    dispatch({ type: 'SORT_RESULTS', column })
  }

  const formatNumber = (value: any, decimals = 2) => {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'number') {
      return value.toLocaleString(undefined, { 
        minimumFractionDigits: decimals, 
        maximumFractionDigits: decimals 
      })
    }
    return value
  }

  const formatVolume = (volume: number | null | undefined) => {
    if (!volume || volume === null || volume === undefined) return '-'
    if (volume >= 1000000) {
      return `${(volume / 1000000).toFixed(1)}M`
    }
    if (volume >= 1000) {
      return `${(volume / 1000).toFixed(1)}K`
    }
    return volume.toString()
  }

  const renderPriceVsMA = (value: number | undefined) => {
    if (value === undefined || value === null) return '-'
    
    const isPositive = value > 0
    const Icon = isPositive ? TrendingUp : TrendingDown
    const color = isPositive ? 'text-green-600' : 'text-red-600'
    
    return (
      <div className={`flex items-center gap-1 ${color}`}>
        <Icon className="h-3 w-3" />
        <span>{isPositive ? '+' : ''}{value.toFixed(2)}%</span>
      </div>
    )
  }

  const renderRSI = (value: number | undefined) => {
    if (value === undefined || value === null) return '-'
    
    let variant: 'default' | 'secondary' | 'destructive' = 'secondary'
    if (value < 30) variant = 'destructive'
    else if (value > 70) variant = 'default'
    
    return <Badge variant={variant}>{value.toFixed(1)}</Badge>
  }

  if (state.ui.resultsView === 'cards') {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {results.map((result) => (
          <div
            key={result.symbol}
            className="border rounded-lg p-4 hover:shadow-md transition-shadow text-center"
          >
            <h3 className="font-bold text-lg">{result.symbol}</h3>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleSort('symbol')}
                className="h-auto p-0 font-medium"
              >
                Symbol
                <ArrowUpDown className="ml-1 h-3 w-3" />
              </Button>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((result) => (
            <TableRow key={result.symbol}>
              <TableCell className="font-medium">{result.symbol}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}