import React, { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { DollarSign, Clock, AlertCircle } from 'lucide-react'
import { HelpTooltip } from '@/components/HelpTooltip'
import { useScreenerContext } from '@/contexts/ScreenerContext'

export const PreviousDayDollarVolumeFilter = memo(() => {
  const { state, dispatch } = useScreenerContext()
  const filter = state.filters.prevDayDollarVolume

  const handleToggle = () => {
    dispatch({ type: 'TOGGLE_FILTER', filter: 'prevDayDollarVolume' })
  }

  const handleChange = (value: string) => {
    dispatch({ 
      type: 'SET_FILTER', 
      filter: 'prevDayDollarVolume', 
      field: 'minDollarVolume', 
      value 
    })
  }

  // Validation
  const minVolume = parseFloat(filter.minDollarVolume)
  const hasError = filter.enabled && (isNaN(minVolume) || minVolume < 0)

  return (
    <Card className={`transition-opacity ${filter.enabled ? 'opacity-100' : 'opacity-75'}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="flex items-center">
              <DollarSign className="h-5 w-5 text-muted-foreground" />
              <Clock className="h-3 w-3 text-muted-foreground -ml-1" />
            </div>
            <h3 className="font-medium">Previous Day Dollar Volume</h3>
            <HelpTooltip content="Filter stocks based on yesterday's dollar volume (price × volume). Useful for finding liquid stocks before market open." />
          </div>
          <Switch
            checked={filter.enabled}
            onCheckedChange={handleToggle}
            aria-label="Toggle previous day dollar volume filter"
          />
        </div>

        {filter.enabled && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="min-dollar-volume">Minimum Dollar Volume ($)</Label>
              <Input
                id="min-dollar-volume"
                type="number"
                step="1000000"
                min="0"
                placeholder="10000000"
                value={filter.minDollarVolume}
                onChange={(e) => handleChange(e.target.value)}
                className={hasError ? 'border-red-500' : ''}
              />
              {hasError && (
                <div className="flex items-center gap-2 text-sm text-red-600">
                  <AlertCircle className="h-4 w-4" />
                  <span>Dollar volume must be a positive number</span>
                </div>
              )}
              <p className="text-sm text-muted-foreground">
                e.g., 10000000 = $10M, 50000000 = $50M
              </p>
            </div>

            <div className="text-sm text-muted-foreground">
              Filters based on the previous trading day's dollar volume only
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
})

PreviousDayDollarVolumeFilter.displayName = 'PreviousDayDollarVolumeFilter'