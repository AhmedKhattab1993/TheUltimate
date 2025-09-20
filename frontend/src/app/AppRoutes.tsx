import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Suspense } from 'react'

import { AppLayout } from './AppLayout'
import { ScreenerPage } from '@/features/screener/ScreenerPage'
import { BacktestsPage } from '@/features/backtests/BacktestsPage'
import { GridPage } from '@/features/grid/GridPage'
import { GridResultsPage } from '@/features/grid/GridResultsPage'
import { OptimizerPage } from '@/features/optimizer/OptimizerPage'
import { IngestionPage } from '@/features/data/IngestionPage'
import { CombinedResultsPage } from '@/features/results/CombinedResultsPage'
import { LoadingSkeleton } from '@/components/LoadingSkeleton'

export function AppRoutes() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingSkeleton />}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Navigate to="/screener" replace />} />
            <Route path="/screener" element={<ScreenerPage />} />
            <Route path="/backtests" element={<BacktestsPage />} />
            <Route path="/grid" element={<GridPage />} />
            <Route path="/grid/results" element={<GridResultsPage />} />
            <Route path="/optimizer" element={<OptimizerPage />} />
            <Route path="/data" element={<IngestionPage />} />
            <Route path="/results/combined" element={<CombinedResultsPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
