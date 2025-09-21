import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { TrendingUp, AlertCircle } from 'lucide-react'
import { HelpTooltip } from '@/components/HelpTooltip'
import { useScreenerContext } from '@/contexts/ScreenerContext'

export const RelativeVolumeFilter = memo(() => {
  const { state, dispatch } = useScreenerContext()
  const filter = state.filters.relativeVolume

  const handleToggle = () => {
    dispatch({ type: 'TOGGLE_FILTER', filter: 'relativeVolume' })
  }

  const handleChange = (field: string, value: string) => {
    dispatch({ 
      type: 'SET_FILTER', 
      filter: 'relativeVolume', 
      field, 
      value 
    })
  }

  // Validation
  const minRatio = parseFloat(filter.minRatio)
  const maxRatio = parseFloat(filter.maxRatio)
  const hasMinRatioError = filter.enabled && !Number.isNaN(minRatio) && minRatio <= 0
  const hasMaxRatioError = filter.enabled && !Number.isNaN(maxRatio) && maxRatio <= 0
  const hasRangeError = filter.enabled
    && !Number.isNaN(minRatio)
    && !Number.isNaN(maxRatio)
    && minRatio > maxRatio

  return (
    <Card className={`transition-opacity ${filter.enabled ? 'opacity-100' : 'opacity-75'}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-muted-foreground" />
            <h3 className="font-medium">Relative Volume Filter</h3>
            <HelpTooltip content="Compare recent average volume to historical average. Finds stocks with unusual volume activity." />
          </div>
          <Switch
            checked={filter.enabled}
            onCheckedChange={handleToggle}
            aria-label="Toggle relative volume filter"
          />
        </div>

        {filter.enabled && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="min-ratio">Minimum Ratio</Label>
                <Input
                  id="min-ratio"
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="10"
                  placeholder="1.5"
                  value={filter.minRatio}
                  onChange={(e) => handleChange('minRatio', e.target.value)}
                  className={hasMinRatioError ? 'border-red-500' : ''}
                />
                {hasMinRatioError && (
                  <div className="flex items-center gap-2 text-sm text-red-600">
                    <AlertCircle className="h-4 w-4" />
                    <span>Minimum ratio must be greater than 0</span>
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="max-ratio">Maximum Ratio</Label>
                <Input
                  id="max-ratio"
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="10"
                  placeholder="Optional"
                  value={filter.maxRatio}
                  onChange={(e) => handleChange('maxRatio', e.target.value)}
                  className={hasMaxRatioError ? 'border-red-500' : ''}
                />
                {hasMaxRatioError && (
                  <div className="flex items-center gap-2 text-sm text-red-600">
                    <AlertCircle className="h-4 w-4" />
                    <span>Maximum ratio must be greater than 0</span>
                  </div>
                )}
              </div>
            </div>

            {hasRangeError && (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <AlertCircle className="h-4 w-4" />
                <span>Min ratio must be less than or equal to max ratio</span>
              </div>
            )}
            <p className="text-sm text-muted-foreground">
              e.g., 1.5 = 50% higher, 2.0 = 100% higher
            </p>

            <div className="text-sm text-muted-foreground">
              Formula: avg(last {filter.recentDays} days) / avg(last {filter.lookbackDays} days) — values fixed to reduce configuration overhead
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
})

RelativeVolumeFilter.displayName = 'RelativeVolumeFilter'
