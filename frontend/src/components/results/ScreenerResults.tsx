import React, { useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Download, Search, Table, LayoutGrid } from 'lucide-react'
import { ResultsTable } from './ResultsTable'
import { PerformanceMetrics } from './PerformanceMetrics'
import { DateFilter } from './DateFilter'
import { useScreenerContext } from '@/contexts/ScreenerContext'
import { TableSkeleton } from '@/components/LoadingSkeleton'
import { format } from 'date-fns'

export function ScreenerResults() {
  const { state, dispatch } = useScreenerContext()
  const [searchTerm, setSearchTerm] = React.useState('')
  const [selectedDate, setSelectedDate] = React.useState<string | null>(null)
  
  const results = state.results.data

  // Get all unique qualifying dates from results
  const allQualifyingDates = useMemo(() => {
    if (!results?.results) return []
    const dateSet = new Set<string>()
    results.results.forEach((result: any) => {
      result.qualifying_dates.forEach((date: string) => dateSet.add(date))
    })
    return Array.from(dateSet).sort()
  }, [results?.results])

  // Filter results based on search and selected date
  const filteredResults = useMemo(() => {
    if (!results?.results) return []
    
    let filtered = results.results
    
    // Filter by search term
    if (searchTerm) {
      filtered = filtered.filter((result: any) =>
        result.symbol.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }
    
    // Filter by selected date
    if (selectedDate) {
      filtered = filtered.filter((result: any) =>
        result.qualifying_dates.includes(selectedDate)
      )
    }
    
    return filtered
  }, [results?.results, searchTerm, selectedDate])

  // Sort results
  const sortedResults = useMemo(() => {
    if (!filteredResults) return []
    
    const sorted = [...filteredResults]
    sorted.sort((a, b) => {
      const aVal = a.metrics[state.ui.sortColumn] || a[state.ui.sortColumn]
      const bVal = b.metrics[state.ui.sortColumn] || b[state.ui.sortColumn]
      
      if (state.ui.sortDirection === 'asc') {
        return aVal > bVal ? 1 : -1
      } else {
        return aVal < bVal ? 1 : -1
      }
    })
    
    return sorted
  }, [filteredResults, state.ui.sortColumn, state.ui.sortDirection])

  const handleExport = () => {
    if (!results) return
    
    const headers = ['Symbol']
    const rows = results.results.map((r: any) => [r.symbol])
    
    const csv = [
      headers.join(','),
      ...rows.map((row: any[]) => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')
    
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `screener-results-${format(new Date(), 'yyyy-MM-dd-HHmm')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!results && !state.results.loading) return null

  if (state.results.loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Screening Results</CardTitle>
          <p className="text-sm text-muted-foreground">
            Analyzing stocks...
          </p>
        </CardHeader>
        <CardContent>
          <TableSkeleton />
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>
                Screening Results
                {selectedDate && (
                  <span className="text-sm font-normal text-muted-foreground ml-2">
                    for {format(new Date(selectedDate + 'T00:00:00'), 'MMM d, yyyy')}
                  </span>
                )}
              </CardTitle>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">
                {results.execution_time_ms.toFixed(0)}ms
              </Badge>
              <Button size="sm" variant="outline" onClick={handleExport}>
                <Download className="h-4 w-4 mr-1" />
                Export
              </Button>
            </div>
          </div>
        </CardHeader>
        
        <CardContent>
          {results.results.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <p className="mb-2">No stocks matched your screening criteria.</p>
              <p className="text-sm">Try adjusting your filters or date range.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search symbols..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-9"
                  />
                </div>
                
                <DateFilter
                  availableDates={allQualifyingDates}
                  selectedDate={selectedDate}
                  onDateChange={setSelectedDate}
                />
                
                <Tabs
                  value={state.ui.resultsView}
                  onValueChange={(value) => dispatch({ 
                    type: 'SET_VIEW_MODE', 
                    mode: value as 'table' | 'cards' 
                  })}
                >
                  <TabsList>
                    <TabsTrigger value="table" className="gap-1">
                      <Table className="h-4 w-4" />
                      Table
                    </TabsTrigger>
                    <TabsTrigger value="cards" className="gap-1">
                      <LayoutGrid className="h-4 w-4" />
                      Cards
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>

              {(searchTerm || selectedDate) && (
                <div className="text-sm text-muted-foreground">
                  Showing {sortedResults.length} of {results.results.length} results
                  {selectedDate && ` (${allQualifyingDates.length} unique days)`}
                </div>
              )}
              
              <ResultsTable results={sortedResults} />
            </div>
          )}
        </CardContent>
      </Card>

      {results.performance_metrics && (
        <PerformanceMetrics metrics={results.performance_metrics} />
      )}
    </div>
  )
}