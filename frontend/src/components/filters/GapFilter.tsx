import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { TrendingUp, AlertCircle } from 'lucide-react'
import { HelpTooltip } from '@/components/HelpTooltip'
import { useScreenerContext } from '@/contexts/ScreenerContext'

export const GapFilter = memo(() => {
  const { state, dispatch } = useScreenerContext()
  const filter = state.filters.gap

  const handleToggle = () => {
    dispatch({ type: 'TOGGLE_FILTER', filter: 'gap' })
  }

  const handleMinGapChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'gap', field: 'minGapPercent', value })
  }

  const handleMaxGapChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'gap', field: 'maxGapPercent', value })
  }

  const handleDirectionChange = (value: 'up' | 'down' | 'both') => {
    dispatch({ type: 'SET_FILTER', filter: 'gap', field: 'direction', value })
  }

  // Validation
  const minGap = parseFloat(filter.minGapPercent)
  const maxGap = parseFloat(filter.maxGapPercent)
  const minError = filter.enabled && !isNaN(minGap) && minGap < 0
  const maxError = filter.enabled && !isNaN(maxGap) && maxGap < 0
  const rangeError = filter.enabled
    && !isNaN(minGap)
    && !isNaN(maxGap)
    && minGap > maxGap

  return (
    <Card className={`transition-opacity ${filter.enabled ? 'opacity-100' : 'opacity-75'}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-muted-foreground" />
            <h3 className="font-medium">Gap Filter</h3>
            <HelpTooltip content="Filter stocks by the gap between today's open and yesterday's close. A gap occurs when the opening price differs significantly from the previous day's closing price, indicating overnight market sentiment." />
          </div>
          <Switch
            checked={filter.enabled}
            onCheckedChange={handleToggle}
            aria-label="Toggle gap filter"
          />
        </div>

        {filter.enabled && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="gap-min">Min Gap (%)</Label>
                <Input
                  id="gap-min"
                  type="number"
                  step="0.1"
                  placeholder="2.0"
                  value={filter.minGapPercent}
                  onChange={(e) => handleMinGapChange(e.target.value)}
                  className={minError ? 'border-red-500' : ''}
                />
                {minError && (
                  <div className="flex items-center gap-2 text-sm text-red-600">
                    <AlertCircle className="h-4 w-4" />
                    <span>Minimum gap must be zero or greater</span>
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="gap-max">Max Gap (%)</Label>
                <Input
                  id="gap-max"
                  type="number"
                  step="0.1"
                  placeholder="Optional"
                  value={filter.maxGapPercent}
                  onChange={(e) => handleMaxGapChange(e.target.value)}
                  className={maxError ? 'border-red-500' : ''}
                />
                {maxError && (
                  <div className="flex items-center gap-2 text-sm text-red-600">
                    <AlertCircle className="h-4 w-4" />
                    <span>Maximum gap must be zero or greater</span>
                  </div>
                )}
              </div>
            </div>

            {rangeError && (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <AlertCircle className="h-4 w-4" />
                <span>Minimum gap must be less than or equal to maximum gap</span>
              </div>
            )}

            <div className="space-y-2">
              <Label>Gap Direction</Label>
              <RadioGroup value={filter.direction} onValueChange={handleDirectionChange}>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="up" id="gap-up" />
                  <Label htmlFor="gap-up" className="font-normal cursor-pointer">
                    Gap Up (Open &gt; Previous Close)
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="down" id="gap-down" />
                  <Label htmlFor="gap-down" className="font-normal cursor-pointer">
                    Gap Down (Open &lt; Previous Close)
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="both" id="gap-both" />
                  <Label htmlFor="gap-both" className="font-normal cursor-pointer">
                    Both (Either Direction)
                  </Label>
                </div>
              </RadioGroup>
            </div>

            <div className="text-sm text-muted-foreground">
              Gap % = ((Today's Open - Yesterday's Close) / Yesterday's Close) × 100
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
})
