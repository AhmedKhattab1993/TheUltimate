import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Activity } from 'lucide-react'
import { HelpTooltip } from '@/components/HelpTooltip'
import { useScreenerContext } from '@/contexts/ScreenerContext'

export const RSIFilter = memo(() => {
  const { state, dispatch } = useScreenerContext()
  const filter = state.filters.rsi

  const handleToggle = () => {
    dispatch({ type: 'TOGGLE_FILTER', filter: 'rsi' })
  }

  const handlePeriodChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'rsi', field: 'period', value })
  }

  const handleMinValueChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'rsi', field: 'minValue', value })
  }

  const handleMaxValueChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'rsi', field: 'maxValue', value })
  }

  // Validation
  const period = parseInt(filter.period)
  const minValue = parseFloat(filter.minValue)
  const maxValue = parseFloat(filter.maxValue)
  const periodError = filter.enabled && (isNaN(period) || period < 2 || period > 50)
  const minError = filter.enabled && !isNaN(minValue) && (minValue < 0 || minValue > 100)
  const maxError = filter.enabled && !isNaN(maxValue) && (maxValue < 0 || maxValue > 100)
  const rangeError = filter.enabled
    && !isNaN(minValue)
    && !isNaN(maxValue)
    && minValue > maxValue

  const getMarketConditionBadge = () => {
    if (!Number.isNaN(maxValue) && maxValue <= 30) {
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full">
          Oversold
        </span>
      )
    }
    if (!Number.isNaN(minValue) && minValue >= 70) {
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">
          Overbought
        </span>
      )
    }
    return null
  }

  return (
    <Card className={`transition-opacity ${filter.enabled ? 'opacity-100' : 'opacity-75'}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-muted-foreground" />
            <h3 className="font-medium">RSI Filter</h3>
            <HelpTooltip content="Relative Strength Index measures momentum. RSI < 30 = potentially oversold (buy signal), RSI > 70 = potentially overbought (sell signal). Period of 14 is standard." />
            {filter.enabled && getMarketConditionBadge()}
          </div>
          <Switch
            checked={filter.enabled}
            onCheckedChange={handleToggle}
            aria-label="Toggle RSI filter"
          />
        </div>

        {filter.enabled && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="rsi-period">RSI Period</Label>
                <Input
                  id="rsi-period"
                  type="number"
                  min="2"
                  max="50"
                  placeholder="14"
                  value={filter.period}
                  onChange={(e) => handlePeriodChange(e.target.value)}
                  className={periodError ? 'border-red-500' : ''}
                />
                {periodError && (
                  <p className="text-xs text-red-600">Period must be between 2 and 50</p>
                )}
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="rsi-min">Min RSI</Label>
                <Input
                  id="rsi-min"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  placeholder="Optional"
                  value={filter.minValue}
                  onChange={(e) => handleMinValueChange(e.target.value)}
                  className={minError ? 'border-red-500' : ''}
                />
                {minError && (
                  <p className="text-xs text-red-600">Value must be between 0 and 100</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="rsi-max">Max RSI</Label>
                <Input
                  id="rsi-max"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  placeholder="Optional"
                  value={filter.maxValue}
                  onChange={(e) => handleMaxValueChange(e.target.value)}
                  className={maxError ? 'border-red-500' : ''}
                />
                {maxError && (
                  <p className="text-xs text-red-600">Value must be between 0 and 100</p>
                )}
              </div>
            </div>

            {rangeError && (
              <div className="text-sm text-red-600">
                Minimum RSI must be less than or equal to maximum RSI
              </div>
            )}

            <div className="text-sm text-muted-foreground">
              Provide lower and/or upper RSI bounds to target oversold ({'<'}30) or overbought ({'>'}70) conditions.
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
})
