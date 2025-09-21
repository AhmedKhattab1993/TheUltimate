import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Activity } from 'lucide-react'
import { HelpTooltip } from '@/components/HelpTooltip'
import { useScreenerContext } from '@/contexts/ScreenerContext'

const rsiPresets = [3, 14, 21] as const

export const RSIFilter = memo(() => {
  const { state, dispatch } = useScreenerContext()
  const filter = state.filters.rsi

  const togglePeriod = (period: typeof rsiPresets[number]) => {
    dispatch({ type: 'TOGGLE_RSI_PERIOD', period })
  }

  const handleValueChange = (
    period: typeof rsiPresets[number],
    field: 'minValue' | 'maxValue',
    value: string,
  ) => {
    dispatch({ type: 'SET_RSI_VALUE', period, field, value })
  }

  const hasActive = filter.enabled

  const getErrors = (min: number, max: number) => ({
    minError: !Number.isNaN(min) && (min < 0 || min > 100),
    maxError: !Number.isNaN(max) && (max < 0 || max > 100),
    rangeError: !Number.isNaN(min) && !Number.isNaN(max) && min > max,
  })

  return (
    <Card className={`transition-opacity ${hasActive ? 'opacity-100' : 'opacity-75'}`}>
      <CardContent className="p-4 space-y-4">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-muted-foreground" />
          <h3 className="font-medium">RSI Filter</h3>
          <HelpTooltip content="Relative Strength Index measures momentum. Enable fixed-period presets to target oversold (<30) or overbought (>70) conditions across different timeframes." />
        </div>

        {rsiPresets.map((period) => {
          const config = filter.periods[period]
          const minValue = parseFloat(config.minValue)
          const maxValue = parseFloat(config.maxValue)
          const { minError, maxError, rangeError } = getErrors(minValue, maxValue)

          return (
            <div key={period} className={`space-y-3 rounded-lg border p-4 ${config.enabled ? 'bg-muted/30' : ''}`}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">RSI ({period})</div>
                  <p className="text-sm text-muted-foreground">
                    {period === 3 && 'Ultra-short lookback for fast moves'}
                    {period === 14 && 'Classic RSI lookback'}
                    {period === 21 && 'Smoother momentum read'}
                  </p>
                </div>
                <Switch
                  checked={config.enabled}
                  onCheckedChange={() => togglePeriod(period)}
                  aria-label={`Toggle RSI period ${period}`}
                />
              </div>

              {config.enabled && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor={`rsi-${period}-min`}>Min RSI</Label>
                    <Input
                      id={`rsi-${period}-min`}
                      type="number"
                      min="0"
                      max="100"
                      step="1"
                      placeholder="Optional"
                      value={config.minValue}
                      onChange={(e) => handleValueChange(period, 'minValue', e.target.value)}
                      className={minError || rangeError ? 'border-red-500' : ''}
                    />
                    {minError && (
                      <p className="text-xs text-red-600">Value must be between 0 and 100</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`rsi-${period}-max`}>Max RSI</Label>
                    <Input
                      id={`rsi-${period}-max`}
                      type="number"
                      min="0"
                      max="100"
                      step="1"
                      placeholder="Optional"
                      value={config.maxValue}
                      onChange={(e) => handleValueChange(period, 'maxValue', e.target.value)}
                      className={maxError || rangeError ? 'border-red-500' : ''}
                    />
                    {maxError && (
                      <p className="text-xs text-red-600">Value must be between 0 and 100</p>
                    )}
                  </div>
                  {rangeError && (
                    <div className="md:col-span-2 text-sm text-red-600">
                      Minimum RSI must be less than or equal to maximum RSI
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}

        <div className="text-sm text-muted-foreground">
          Combine multiple RSI windows to find agreement across short and longer-term momentum.
        </div>
      </CardContent>
    </Card>
  )
})
