import React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

export function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="h-6 w-48 bg-gray-200 animate-pulse rounded" />
          <div className="h-4 w-64 bg-gray-200 animate-pulse rounded mt-2" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="h-4 w-24 bg-gray-200 animate-pulse rounded" />
                <div className="h-4 w-32 bg-gray-200 animate-pulse rounded" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export function TableSkeleton() {
  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-50 p-4">
        <div className="flex items-center justify-between">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="h-4 w-20 bg-gray-200 animate-pulse rounded" />
          ))}
        </div>
      </div>
      <div className="divide-y">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="p-4">
            <div className="flex items-center justify-between">
              {[...Array(7)].map((_, j) => (
                <div key={j} className="h-4 w-16 bg-gray-200 animate-pulse rounded" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}