import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { ArrowUpDown } from 'lucide-react'
import { useScreenerContext } from '@/contexts/ScreenerContext'

interface ResultsTableProps {
  results: any[]
}

export function ResultsTable({ results }: ResultsTableProps) {
  const { state, dispatch } = useScreenerContext()

  const handleSort = (column: string) => {
    dispatch({ type: 'SORT_RESULTS', column })
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
