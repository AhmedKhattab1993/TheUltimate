import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { DollarSign, AlertCircle } from 'lucide-react'
import { HelpTooltip } from '@/components/HelpTooltip'
import { useScreenerContext } from '@/contexts/ScreenerContext'

export const SimplePriceRangeFilter = memo(() => {
  const { state, dispatch } = useScreenerContext()
  const filter = state.filters.simplePriceRange

  const handleToggle = () => {
    dispatch({ type: 'TOGGLE_FILTER', filter: 'simplePriceRange' })
  }

  const handleMinChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'simplePriceRange', field: 'minPrice', value })
  }

  const handleMaxChange = (value: string) => {
    dispatch({ type: 'SET_FILTER', filter: 'simplePriceRange', field: 'maxPrice', value })
  }

  // Validation
  const minPrice = parseFloat(filter.minPrice)
  const maxPrice = parseFloat(filter.maxPrice)
  const hasError = filter.enabled && (!isNaN(minPrice) && !isNaN(maxPrice) && minPrice >= maxPrice)

  return (
    <Card className={`transition-opacity ${filter.enabled ? 'opacity-100' : 'opacity-75'}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <DollarSign className="h-5 w-5 text-muted-foreground" />
            <h3 className="font-medium">Price Range Filter</h3>
            <HelpTooltip content="Filter stocks by their opening price on each trading day. This is useful for finding stocks within your budget or excluding penny stocks." />
          </div>
          <Switch
            checked={filter.enabled}
            onCheckedChange={handleToggle}
            aria-label="Toggle price range filter"
          />
        </div>

        {filter.enabled && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="min-price">Minimum Price ($)</Label>
                <Input
                  id="min-price"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="1.00"
                  value={filter.minPrice}
                  onChange={(e) => handleMinChange(e.target.value)}
                  className={hasError ? 'border-red-500' : ''}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="max-price">Maximum Price ($)</Label>
                <Input
                  id="max-price"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="100.00"
                  value={filter.maxPrice}
                  onChange={(e) => handleMaxChange(e.target.value)}
                  className={hasError ? 'border-red-500' : ''}
                />
              </div>
            </div>

            {hasError && (
              <div className="flex items-center gap-2 text-sm text-red-600">
                <AlertCircle className="h-4 w-4" />
                <span>Maximum price must be greater than minimum price</span>
              </div>
            )}

            <div className="text-sm text-muted-foreground">
              Filters stocks by OPEN price on the current trading day
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
})
