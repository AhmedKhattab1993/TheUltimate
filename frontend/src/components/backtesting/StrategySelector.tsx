import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { useBacktestContext } from '@/contexts/BacktestContext'
import { FileCode, Info } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'

export function StrategySelector() {
  const { state, dispatch } = useBacktestContext()
  const { strategies, parameters } = state

  const handleStrategyChange = (value: string) => {
    dispatch({ type: 'SET_PARAMETER', field: 'strategy', value })
  }

  if (!strategies || strategies.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Select Strategy</CardTitle>
          <CardDescription>
            Choose a LEAN strategy to backtest
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              No strategies found. Please ensure strategies are available in the backend/lean/ directory.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Select Strategy</CardTitle>
        <CardDescription>
          Choose a LEAN strategy to backtest from available algorithms
        </CardDescription>
      </CardHeader>
      <CardContent>
        <RadioGroup
          value={parameters.strategy || ''}
          onValueChange={handleStrategyChange}
          className="space-y-3"
        >
          {strategies.map((strategy) => (
            <div
              key={strategy.file_path}
              className="flex items-start space-x-3 rounded-lg border p-4 hover:bg-accent/50 transition-colors"
            >
              <RadioGroupItem value={strategy.file_path} id={strategy.file_path} />
              <Label
                htmlFor={strategy.file_path}
                className="flex-1 cursor-pointer space-y-1"
              >
                <div className="flex items-center gap-2">
                  <FileCode className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{strategy.name}</span>
                </div>
                {strategy.description && (
                  <p className="text-sm text-muted-foreground">
                    {strategy.description}
                  </p>
                )}
                <p className="text-xs text-muted-foreground font-mono">
                  {strategy.file_path}
                </p>
              </Label>
            </div>
          ))}
        </RadioGroup>
      </CardContent>
    </Card>
  )
}
