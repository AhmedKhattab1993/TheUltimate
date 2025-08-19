import React from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Info } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface MarketStructureFormProps {
  parameters: Record<string, any>
  onParameterChange: (field: string, value: any) => void
}

export function MarketStructureForm({ parameters, onParameterChange }: MarketStructureFormProps) {
  const timeframeOptions = [
    { value: '1min', label: '1 Minute' },
    { value: '5min', label: '5 Minutes' },
    { value: '15min', label: '15 Minutes' },
    { value: '30min', label: '30 Minutes' },
    { value: '1hour', label: '1 Hour' },
    { value: 'daily', label: 'Daily' }
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Market Structure Parameters</CardTitle>
        <CardDescription>
          Configure Break of Structure (BOS) strategy settings
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription className="text-xs">
            This strategy identifies trend changes using pivot highs/lows and trades breakouts with intraday position management.
          </AlertDescription>
        </Alert>

        {/* Timeframe Settings */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="lower-timeframe">Lower Timeframe</Label>
            <Select
              value={parameters.lower_timeframe || '5min'}
              onValueChange={(value) => onParameterChange('lower_timeframe', value)}
            >
              <SelectTrigger id="lower-timeframe">
                <SelectValue placeholder="Select timeframe" />
              </SelectTrigger>
              <SelectContent>
                {timeframeOptions.slice(0, 5).map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Primary timeframe for pivot detection
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="higher-timeframe">Higher Timeframe</Label>
            <Select
              value={parameters.higher_timeframe || '1hour'}
              onValueChange={(value) => onParameterChange('higher_timeframe', value)}
            >
              <SelectTrigger id="higher-timeframe">
                <SelectValue placeholder="Select timeframe" />
              </SelectTrigger>
              <SelectContent>
                {timeframeOptions.slice(2).map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Higher timeframe for trend context
            </p>
          </div>
        </div>

        {/* Pivot Bars Setting */}
        <div className="space-y-2">
          <Label htmlFor="pivot-bars">Pivot Bars</Label>
          <Input
            id="pivot-bars"
            type="number"
            value={parameters.pivot_bars || 20}
            onChange={(e) => onParameterChange('pivot_bars', parseInt(e.target.value) || 20)}
            min="5"
            max="50"
            step="5"
          />
          <p className="text-xs text-muted-foreground">
            Number of bars to left and right for pivot detection (5-50)
          </p>
        </div>

        {/* Strategy Info */}
        <div className="space-y-2 pt-4 border-t">
          <h4 className="text-sm font-medium">Strategy Behavior</h4>
          <ul className="text-xs text-muted-foreground space-y-1">
            <li>• Enters long when price breaks above pivot highs</li>
            <li>• Enters short when price breaks below pivot lows</li>
            <li>• Always-in-market reversal system (flips positions)</li>
            <li>• No new entries after 3:59 PM</li>
            <li>• All positions liquidated at 3:59 PM (market close)</li>
            <li>• All pending orders cancelled at 3:59 PM</li>
            <li>• Equal position sizing across all symbols</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}