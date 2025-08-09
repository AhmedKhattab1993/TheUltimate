import * as React from 'react'
import { Calendar, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { format } from 'date-fns'

interface DateFilterProps {
  availableDates: string[]
  selectedDate: string | null
  onDateChange: (date: string | null) => void
}

export function DateFilter({ availableDates, selectedDate, onDateChange }: DateFilterProps) {
  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <Calendar className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Select value={selectedDate || ''} onValueChange={(value) => onDateChange(value || null)}>
          <SelectTrigger className="w-[180px] pl-8">
            <SelectValue placeholder="Filter by date" />
          </SelectTrigger>
          <SelectContent>
            {availableDates.map((date) => (
              <SelectItem key={date} value={date}>
                {format(new Date(date + 'T00:00:00'), 'MMM d, yyyy')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      {selectedDate && (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onDateChange(null)}
          className="h-9 w-9"
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}