import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { addDays, formatISO, subDays } from 'date-fns'
import type {
  FilterControl,
  FilterDefinition,
  FilterState,
  FilterStateMap,
  ScreenerRequestPayload,
} from '@/types/api'
import { registryApi, screenerApi } from '@/services/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DatePicker } from '@/components/ui/date-picker'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2 } from 'lucide-react'
import { LoadingSkeleton, TableSkeleton } from '@/components/LoadingSkeleton'
import { ScreenerResultsTable } from './components/ScreenerResultsTable'

function buildInitialFilterState(filters: FilterDefinition[]): FilterStateMap {
  const initial: FilterStateMap = {}
  for (const filter of filters) {
    const values: FilterState['values'] = {}
    for (const control of filter.controls) {
      if (control.controlType === 'toggle') {
        values[control.field] = Boolean(control.defaultValue)
      } else if (control.controlType === 'select') {
        if (control.defaultValue !== undefined) {
          values[control.field] = control.defaultValue
        } else if (control.options?.length) {
          values[control.field] = control.options[0]!.value
        }
      } else {
        values[control.field] = control.defaultValue ?? control.minValue ?? 0
      }
    }
    initial[filter.id] = {
      enabled: filter.defaultEnabled,
      values,
    }
  }
  return initial
}

function ControlField({
  filterId,
  control,
  value,
  onChange,
}: {
  filterId: string
  control: FilterControl
  value: string | number | boolean | undefined
  onChange: (field: string, value: string | number | boolean) => void
}) {
  if (control.controlType === 'toggle') {
    return (
      <div className="flex items-center justify-between gap-2">
        <div>
          <Label htmlFor={`${filterId}-${control.field}`}>{control.label}</Label>
          {control.description && (
            <p className="text-xs text-muted-foreground">{control.description}</p>
          )}
        </div>
        <Switch
          id={`${filterId}-${control.field}`}
          checked={Boolean(value)}
          onCheckedChange={(checked) => onChange(control.field, checked)}
        />
      </div>
    )
  }

  if (control.controlType === 'select' && control.options) {
    const stringValue = value !== undefined ? String(value) : String(control.options[0]?.value ?? '')
    return (
      <div className="space-y-1">
        <Label>{control.label}</Label>
        <Select
          value={stringValue}
          onValueChange={(selected) => {
            const option = control.options?.find((opt) => String(opt.value) === selected)
            onChange(control.field, option ? option.value : selected)
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder={control.placeholder ?? control.label} />
          </SelectTrigger>
          <SelectContent>
            {control.options.map((option) => (
              <SelectItem key={`${filterId}-${option.value}`} value={String(option.value)}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {control.description && (
          <p className="text-xs text-muted-foreground">{control.description}</p>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <Label>{control.label}</Label>
      <Input
        type="number"
        value={
          typeof value === 'number' || typeof value === 'string' ? value : ''
        }
        min={control.minValue}
        max={control.maxValue}
        step={control.step}
        onChange={(event) => {
          const rawValue = event.target.value
          if (rawValue === '') {
            onChange(control.field, '')
            return
          }
          const numeric = Number(rawValue)
          onChange(control.field, Number.isNaN(numeric) ? rawValue : numeric)
        }}
      />
      {control.description && (
        <p className="text-xs text-muted-foreground">{control.description}</p>
      )}
    </div>
  )
}

export function ScreenerPage() {
  const registryQuery = useQuery({ queryKey: ['registry'], queryFn: registryApi.fetch })
  const [filterState, setFilterState] = useState<FilterStateMap>({})
  const [startDate, setStartDate] = useState(() => subDays(new Date(), 30))
  const [endDate, setEndDate] = useState(() => new Date())
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (registryQuery.data && Object.keys(filterState).length === 0) {
      setFilterState(buildInitialFilterState(registryQuery.data.filters))
    }
  }, [registryQuery.data, filterState])

  const screenerMutation = useMutation({
    mutationFn: (payload: ScreenerRequestPayload) => screenerApi.run(payload),
  })

  const filters = useMemo(
    () => registryQuery.data?.filters ?? [],
    [registryQuery.data?.filters],
  )

  const handleToggleFilter = (filterId: string, enabled: boolean) => {
    setFilterState((prev) => ({
      ...prev,
      [filterId]: {
        ...(prev[filterId] ?? { enabled, values: {} }),
        enabled,
      },
    }))
  }

  const handleValueChange = (
    filterId: string,
    field: string,
    value: string | number | boolean,
  ) => {
    setFilterState((prev) => ({
      ...prev,
      [filterId]: {
        ...(prev[filterId] ?? { enabled: false, values: {} }),
        values: {
          ...(prev[filterId]?.values ?? {}),
          [field]: value,
        },
      },
    }))
  }

  const handleSubmit = () => {
    if (!startDate || !endDate) {
      setFormError('Please select a valid date range.')
      return
    }

    if (startDate > endDate) {
      setFormError('Start date must be before end date.')
      return
    }

    const activeFilters: FilterStateMap = {}
    for (const [filterId, state] of Object.entries(filterState)) {
      if (state.enabled) {
        activeFilters[filterId] = state
      }
    }

    if (Object.keys(activeFilters).length === 0) {
      setFormError('Enable at least one filter before running the screener.')
      return
    }

    setFormError(null)

    screenerMutation.mutate({
      startDate: formatISO(startDate, { representation: 'date' }),
      endDate: formatISO(endDate, { representation: 'date' }),
      useAllUsStocks: true,
      filters: activeFilters,
    })
  }

  if (registryQuery.isLoading) {
    return <LoadingSkeleton />
  }

  if (registryQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Failed to load registry metadata. Please retry later.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Screen Stocks</CardTitle>
          <CardDescription>Configure your filters and run the screener across daily data.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <DatePicker
                date={startDate}
                onDateChange={(date) => setStartDate(date ?? subDays(new Date(), 30))}
              />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <DatePicker
                date={endDate}
                onDateChange={(date) => setEndDate(date ?? addDays(startDate, 30))}
              />
            </div>
          </div>

          <div className="grid gap-4">
            {filters.map((filter) => {
              const state = filterState[filter.id] ?? { enabled: false, values: {} }
              return (
                <Card key={filter.id} className="border border-muted">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0">
                    <div>
                      <CardTitle className="text-base">{filter.label}</CardTitle>
                      <CardDescription>{filter.description}</CardDescription>
                    </div>
                    <Switch
                      checked={state.enabled}
                      onCheckedChange={(checked) => handleToggleFilter(filter.id, checked)}
                    />
                  </CardHeader>
                  {state.enabled && (
                    <CardContent className="grid gap-4 md:grid-cols-2">
                      {filter.controls.map((control) => (
                        <ControlField
                          key={`${filter.id}-${control.field}`}
                          filterId={filter.id}
                          control={control}
                          value={state.values[control.field]}
                          onChange={(field, value) => handleValueChange(filter.id, field, value)}
                        />
                      ))}
                    </CardContent>
                  )}
                </Card>
              )
            })}
          </div>

          {formError && (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          )}

          <Button onClick={handleSubmit} disabled={screenerMutation.isPending}>
            {screenerMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Run Screener
          </Button>
        </CardContent>
      </Card>

      {screenerMutation.isPending && <TableSkeleton />}

      <ScreenerResultsTable response={screenerMutation.data} />
    </div>
  )
}
