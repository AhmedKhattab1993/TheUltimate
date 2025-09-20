import { useState } from 'react'
import type { ChangeEvent, KeyboardEvent } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { DatePicker } from '@/components/ui/date-picker'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { useBacktestContext } from '@/contexts/BacktestContext'
import { DollarSign, Plus, X, FileSearch } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ScreenerResultsPreviewDialog } from './ScreenerResultsPreviewDialog'

export function BacktestForm() {
  const { state, dispatch } = useBacktestContext()
  const { parameters } = state
  const [symbolInput, setSymbolInput] = useState('')
  const [showPreviewDialog, setShowPreviewDialog] = useState(false)

  const handleCashChange = (e: ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value) || 0
    dispatch({ type: 'SET_PARAMETER', field: 'initialCash', value })
  }

  const handleAddSymbol = () => {
    const symbol = symbolInput.trim().toUpperCase()
    if (symbol && !parameters.symbols.includes(symbol)) {
      dispatch({ type: 'SET_SYMBOLS', symbols: [...parameters.symbols, symbol] })
      setSymbolInput('')
    }
  }

  const handleRemoveSymbol = (symbol: string) => {
    dispatch({ 
      type: 'SET_SYMBOLS', 
      symbols: parameters.symbols.filter(s => s !== symbol) 
    })
  }

  const handleKeyPress = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAddSymbol()
    }
  }


  return (
    <>
      <Card>
        <CardHeader>
        <CardTitle>Backtest Parameters</CardTitle>
        <CardDescription>
          Configure your backtest settings
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Initial Cash */}
        <div className="space-y-2">
          <Label htmlFor="initial-cash">Initial Cash</Label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              id="initial-cash"
              type="number"
              value={parameters.initialCash}
              onChange={handleCashChange}
              className="pl-10"
              min="1000"
              step="1000"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Starting capital for the backtest
          </p>
        </div>

        {/* Date Range */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Start Date</Label>
            <DatePicker
              date={parameters.startDate || undefined}
              onDateChange={(date) => {
                dispatch({ 
                  type: 'SET_PARAMETER', 
                  field: 'startDate', 
                  value: date || null 
                })
              }}
              placeholder="Select start date"
            />
          </div>
          <div className="space-y-2">
            <Label>End Date</Label>
            <DatePicker
              date={parameters.endDate || undefined}
              onDateChange={(date) => {
                dispatch({ 
                  type: 'SET_PARAMETER', 
                  field: 'endDate', 
                  value: date || null 
                })
              }}
              placeholder="Select end date"
            />
          </div>
        </div>

        {/* Use Screener Results */}
        <div className="flex items-center space-x-2">
          <Checkbox
            id="use-screener"
            checked={parameters.useScreenerResults || false}
            onCheckedChange={(checked) => {
              if (checked === true) {
                // Show preview dialog when checking
                setShowPreviewDialog(true)
              } else {
                // Uncheck directly
                dispatch({ 
                  type: 'SET_PARAMETER', 
                  field: 'useScreenerResults', 
                  value: false 
                })
              }
            }}
          />
          <div className="flex-1">
            <Label 
              htmlFor="use-screener" 
              className="flex items-center gap-2 cursor-pointer"
            >
              <FileSearch className="h-4 w-4" />
              Use latest screener results
            </Label>
            <p className="text-xs text-muted-foreground mt-1">
              Use symbols from the latest UI screener session (each symbol backtested on its screening day)
            </p>
          </div>
        </div>

        {/* Symbols */}
        <div className={`space-y-2 ${parameters.useScreenerResults ? 'opacity-50' : ''}`}>
          <div className="flex items-center justify-between">
            <Label>Symbols</Label>
          </div>
          
          <div className="flex gap-2">
            <Input
              value={symbolInput}
              onChange={(e) => setSymbolInput(e.target.value.toUpperCase())}
              onKeyPress={handleKeyPress}
              placeholder="Enter symbol (e.g., AAPL)"
              className="flex-1"
              disabled={parameters.useScreenerResults}
            />
            <Button
              type="button"
              onClick={handleAddSymbol}
              size="icon"
              variant="outline"
              disabled={parameters.useScreenerResults}
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          {parameters.symbols.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {parameters.symbols.map((symbol) => (
                <Badge
                  key={symbol}
                  variant="secondary"
                  className="pl-3 pr-1 py-1 flex items-center gap-1"
                >
                  {symbol}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-4 w-4 p-0 hover:bg-transparent"
                    onClick={() => handleRemoveSymbol(symbol)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </Badge>
              ))}
            </div>
          )}

          {parameters.symbols.length === 0 && !parameters.useScreenerResults && (
            <Alert className="mt-3">
              <AlertDescription className="text-xs">
                Add symbols to backtest or use latest screener results
              </AlertDescription>
            </Alert>
          )}
        </div>
      </CardContent>
      </Card>

      {/* Screener Results Preview Dialog */}
      <ScreenerResultsPreviewDialog
        open={showPreviewDialog}
        onConfirm={() => {
          dispatch({ 
            type: 'SET_PARAMETER', 
            field: 'useScreenerResults', 
            value: true 
          })
          setShowPreviewDialog(false)
        }}
        onCancel={() => {
          setShowPreviewDialog(false)
        }}
      />
    </>
  )
}
