import React, { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Activity, AlertCircle } from 'lucide-react'
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

  const handleThresholdChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'rsi', field: 'threshold', value })
  }

  const handleConditionChange = (condition: 'above' | 'below') => {
    dispatch({ type: 'SET_FILTER', filter: 'rsi', field: 'condition', value: condition })
  }

  // Validation
  const period = parseInt(filter.period)
  const threshold = parseFloat(filter.threshold)
  const periodError = filter.enabled && (isNaN(period) || period < 2 || period > 50)
  const thresholdError = filter.enabled && (isNaN(threshold) || threshold < 0 || threshold > 100)

  const getDescription = () => {
    const condition = filter.condition === 'below' ? 'oversold' : 'overbought'
    const thresholdValue = filter.condition === 'below' ? '30' : '70'
    
    return (
      <div className="text-sm text-muted-foreground">
        Looking for {condition} stocks (RSI {filter.condition} {filter.threshold || thresholdValue})
      </div>
    )
  }

  const getMarketConditionBadge = () => {
    if (filter.condition === 'below' && threshold <= 30) {
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full">
          Oversold
        </span>
      )
    }
    if (filter.condition === 'above' && threshold >= 70) {
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
                <Label htmlFor="rsi-threshold">Threshold</Label>
                <Input
                  id="rsi-threshold"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  placeholder="30"
                  value={filter.threshold}
                  onChange={(e) => handleThresholdChange(e.target.value)}
                  className={thresholdError ? 'border-red-500' : ''}
                />
                {thresholdError && (
                  <p className="text-xs text-red-600">Threshold must be between 0 and 100</p>
                )}
              </div>
            </div>

            <div className="space-y-3">
              <Label>Condition</Label>
              <div className="flex gap-2">
                <Button
                  variant={filter.condition === 'below' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleConditionChange('below')}
                  className="flex-1"
                >
                  Below (Oversold)
                </Button>
                <Button
                  variant={filter.condition === 'above' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleConditionChange('above')}
                  className="flex-1"
                >
                  Above (Overbought)
                </Button>
              </div>
            </div>


            {getDescription()}
          </div>
        )}
      </CardContent>
    </Card>
  )
})