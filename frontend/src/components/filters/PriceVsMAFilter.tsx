import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { TrendingUp } from 'lucide-react'
import { HelpTooltip } from '@/components/HelpTooltip'
import { useScreenerContext } from '@/contexts/ScreenerContext'

export const PriceVsMAFilter = memo(() => {
  const { state, dispatch } = useScreenerContext()
  const filter = state.filters.priceVsMA

  const handleToggle = () => {
    dispatch({ type: 'TOGGLE_FILTER', filter: 'priceVsMA' })
  }

  const handlePeriodChange = (period: 20 | 50 | 200) => {
    dispatch({ type: 'SET_FILTER', filter: 'priceVsMA', field: 'period', value: period })
  }

  const handleMinRatioChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'priceVsMA', field: 'minRatio', value })
  }

  const handleMaxRatioChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'priceVsMA', field: 'maxRatio', value })
  }

  const minRatio = parseFloat(filter.minRatio)
  const maxRatio = parseFloat(filter.maxRatio)
  const hasError = filter.enabled
    && !Number.isNaN(minRatio)
    && !Number.isNaN(maxRatio)
    && minRatio > maxRatio

  return (
    <Card className={`transition-opacity ${filter.enabled ? 'opacity-100' : 'opacity-75'}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-muted-foreground" />
            <h3 className="font-medium">Price vs Moving Average</h3>
            <HelpTooltip content="Compare the stock's opening price to its moving average. MA20 = short-term trend, MA50 = medium-term trend, MA200 = long-term trend. Useful for identifying trend direction." />
          </div>
          <Switch
            checked={filter.enabled}
            onCheckedChange={handleToggle}
            aria-label="Toggle price vs MA filter"
          />
        </div>

        {filter.enabled && (
          <div className="space-y-4">
            <div className="space-y-3">
              <Label>MA Period</Label>
              <div className="flex gap-2">
                {([20, 50, 200] as const).map((period) => (
                  <Button
                    key={period}
                    variant={filter.period === period ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handlePeriodChange(period)}
                    className="flex-1"
                  >
                    {period} MA
                  </Button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="min-ratio">Min Open/MA Ratio</Label>
                <Input
                  id="min-ratio"
                  type="number"
                  step="0.05"
                  min="0"
                  placeholder="1.00"
                  value={filter.minRatio}
                  onChange={(e) => handleMinRatioChange(e.target.value)}
                  className={hasError ? 'border-red-500' : ''}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="max-ratio">Max Open/MA Ratio</Label>
                <Input
                  id="max-ratio"
                  type="number"
                  step="0.05"
                  min="0"
                  placeholder=""
                  value={filter.maxRatio}
                  onChange={(e) => handleMaxRatioChange(e.target.value)}
                  className={hasError ? 'border-red-500' : ''}
                />
              </div>
            </div>

            {hasError && (
              <div className="text-sm text-red-600">
                Minimum ratio must be less than or equal to maximum ratio
              </div>
            )}

            <div className="text-sm text-muted-foreground">
              Ratios above 1.0 indicate the open price is greater than the moving average.
              Configure minimum and/or maximum bounds to target specific setups.
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
})
