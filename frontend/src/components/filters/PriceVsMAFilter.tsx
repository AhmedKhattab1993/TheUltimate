import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { TrendingUp } from 'lucide-react'
import { HelpTooltip } from '@/components/HelpTooltip'
import { useScreenerContext } from '@/contexts/ScreenerContext'

const maPresets = [20, 50, 200] as const

export const PriceVsMAFilter = memo(() => {
  const { state, dispatch } = useScreenerContext()
  const filter = state.filters.priceVsMA

  const hasActiveSetup = filter.enabled

  const handleToggle = (period: typeof maPresets[number]) => {
    dispatch({ type: 'TOGGLE_MA_PERIOD', period })
  }

  const handleRatioChange = (
    period: typeof maPresets[number],
    field: 'minRatio' | 'maxRatio',
    value: string,
  ) => {
    dispatch({ type: 'SET_MA_RATIO', period, field, value })
  }

  const getErrors = (min: number, max: number) => ({
    minError: !Number.isNaN(min) && min < 0,
    maxError: !Number.isNaN(max) && max < 0,
    rangeError: !Number.isNaN(min) && !Number.isNaN(max) && min > max,
  })

  return (
    <Card className={`transition-opacity ${hasActiveSetup ? 'opacity-100' : 'opacity-75'}`}>
      <CardContent className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-muted-foreground" />
            <h3 className="font-medium">Price vs Moving Average</h3>
            <HelpTooltip content="Compare the stock's opening price to key moving averages. Enable one or more presets to check short, mid, or long-term trend alignment." />
          </div>
        </div>

        {maPresets.map((period) => {
          const config = filter.setups[period]
          const minRatio = parseFloat(config.minRatio)
          const maxRatio = parseFloat(config.maxRatio)
          const { minError, maxError, rangeError } = getErrors(minRatio, maxRatio)

          return (
            <div key={period} className={`space-y-3 rounded-lg border p-4 ${config.enabled ? 'bg-muted/30' : ''}`}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{period}-Day MA</div>
                  <p className="text-sm text-muted-foreground">
                    {period === 20 && 'Capture short-term momentum shifts'}
                    {period === 50 && 'Track intermediate trend direction'}
                    {period === 200 && 'Focus on long-term trend alignment'}
                  </p>
                </div>
                <Switch
                  checked={config.enabled}
                  onCheckedChange={() => handleToggle(period)}
                  aria-label={`Toggle moving average ${period}`}
                />
              </div>

              {config.enabled && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor={`ma-${period}-min`}>Min Open/MA Ratio</Label>
                    <Input
                      id={`ma-${period}-min`}
                      type="number"
                      step="0.05"
                      min="0"
                      placeholder="1.00"
                      value={config.minRatio}
                      onChange={(e) => handleRatioChange(period, 'minRatio', e.target.value)}
                      className={minError || rangeError ? 'border-red-500' : ''}
                    />
                    {minError && (
                      <p className="text-xs text-red-600">Minimum ratio must be zero or greater</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`ma-${period}-max`}>Max Open/MA Ratio</Label>
                    <Input
                      id={`ma-${period}-max`}
                      type="number"
                      step="0.05"
                      min="0"
                      placeholder="Optional"
                      value={config.maxRatio}
                      onChange={(e) => handleRatioChange(period, 'maxRatio', e.target.value)}
                      className={maxError || rangeError ? 'border-red-500' : ''}
                    />
                    {maxError && (
                      <p className="text-xs text-red-600">Maximum ratio must be zero or greater</p>
                    )}
                  </div>
                  {rangeError && (
                    <div className="md:col-span-2 text-sm text-red-600">
                      Minimum ratio must be less than or equal to maximum ratio
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}

        <div className="text-sm text-muted-foreground">
          Ratios above 1.0 indicate the open price is trading above the selected moving average. Enable multiple periods to require confluence across timeframes.
        </div>
      </CardContent>
    </Card>
  )
})
