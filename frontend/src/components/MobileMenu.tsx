import React, { useState } from 'react'
import { Menu, X, Filter, Calendar, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'

interface MobileMenuProps {
  activeFilterCount: number
  onExport?: () => void
}

export function MobileMenu({ activeFilterCount, onExport }: MobileMenuProps) {
  const [open, setOpen] = useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="icon" className="md:hidden">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72">
        <SheetHeader>
          <SheetTitle>Menu</SheetTitle>
        </SheetHeader>
        <nav className="mt-6 space-y-4">
          <button className="flex items-center gap-3 w-full p-2 hover:bg-gray-100 rounded-md">
            <Filter className="h-5 w-5" />
            <span>Filters</span>
            {activeFilterCount > 0 && (
              <span className="ml-auto bg-primary text-primary-foreground text-xs px-2 py-1 rounded-full">
                {activeFilterCount}
              </span>
            )}
          </button>
          <button className="flex items-center gap-3 w-full p-2 hover:bg-gray-100 rounded-md">
            <Calendar className="h-5 w-5" />
            <span>Date Range</span>
          </button>
          {onExport && (
            <button 
              className="flex items-center gap-3 w-full p-2 hover:bg-gray-100 rounded-md"
              onClick={onExport}
            >
              <Download className="h-5 w-5" />
              <span>Export Results</span>
            </button>
          )}
        </nav>
      </SheetContent>
    </Sheet>
  )
}