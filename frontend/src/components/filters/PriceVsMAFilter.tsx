import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { TrendingUp, TrendingDown } from 'lucide-react'
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

  const handleConditionChange = (condition: 'above' | 'below') => {
    dispatch({ type: 'SET_FILTER', filter: 'priceVsMA', field: 'condition', value: condition })
  }

  const getDescription = () => {
    const icon = filter.condition === 'above' 
      ? <TrendingUp className="h-4 w-4 text-green-600" />
      : <TrendingDown className="h-4 w-4 text-red-600" />
    
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {icon}
        <span>
          Looking for stocks trading {filter.condition} their {filter.period}-day moving average
        </span>
      </div>
    )
  }

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

            <div className="space-y-3">
              <Label>Price Condition</Label>
              <div className="flex gap-2">
                <Button
                  variant={filter.condition === 'above' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleConditionChange('above')}
                  className="flex-1"
                >
                  <TrendingUp className="h-4 w-4 mr-1" />
                  Above MA
                </Button>
                <Button
                  variant={filter.condition === 'below' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleConditionChange('below')}
                  className="flex-1"
                >
                  <TrendingDown className="h-4 w-4 mr-1" />
                  Below MA
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
