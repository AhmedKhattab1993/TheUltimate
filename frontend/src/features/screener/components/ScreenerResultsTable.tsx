import type { ScreenerResponse } from '@/types/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface Props {
  response?: ScreenerResponse
}

export function ScreenerResultsTable({ response }: Props) {
  if (!response) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Results — {response.totalQualifyingStocks} matches ({response.totalSymbolsScreened} scanned)
        </CardTitle>
      </CardHeader>
      <CardContent>
        {response.results.length === 0 ? (
          <p className="text-sm text-muted-foreground">No symbols matched the selected filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Qualifying Days</TableHead>
                  <TableHead>Latest Metrics</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {response.results.map((row) => (
                  <TableRow key={row.symbol}>
                    <TableCell className="font-medium">{row.symbol}</TableCell>
                    <TableCell>{row.qualifyingDates.length}</TableCell>
                    <TableCell>
                      <div className="text-xs text-muted-foreground space-y-1">
                        {Object.entries(row.metrics).map(([key, value]) => (
                          <div key={key}>
                            <span className="font-semibold mr-2 uppercase tracking-wide">{key}</span>
                            <span>{typeof value === 'number' ? value.toFixed(2) : String(value)}</span>
                          </div>
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
