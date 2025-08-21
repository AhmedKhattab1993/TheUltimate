# Combined Screener + Backtest Results Implementation Plan (Day-by-Day)

## Updated Implementation Plan

### Current System Understanding:
1. **UI Screener**: Saves results day-by-day with `session_id` and `data_date`
2. **Pipeline**: Also processes day-by-day with `pipeline_session_id` and `data_date`
3. **Both Sources**: Each day's screening results are saved separately in `screener_results` table
4. **Caching**: Same backtest can be linked to multiple screener sessions

### What Needs to Be Done:

#### 1. **Database Changes** ✓ (Updated)
- Junction table `screener_backtest_links` with `data_date` column to track day-level relationships
- View `combined_screener_backtest_results` that groups by date for day-by-day display
- Added index on `data_date` for efficient querying

#### 2. **Backend Modifications Needed**:
- **Capture screener session ID AND date** when backtests are triggered
- **Store links** in junction table with the screening date
- **API endpoint** for combined results that returns day-by-day data

#### 3. **Data Structure for Combined View (Flat Table)**:
```typescript
interface CombinedScreenerBacktestRow {
  // Screener columns
  screenerSessionId: string
  screeningDate: string
  source: 'ui' | 'pipeline'
  symbol: string
  companyName?: string
  screenedAt: string
  
  // All screener filter parameters
  filterMinPrice?: number
  filterMaxPrice?: number
  filterPriceVsMaEnabled: boolean
  filterPriceVsMaPeriod?: number
  filterPriceVsMaCondition?: 'above' | 'below'
  filterRsiEnabled: boolean
  filterRsiPeriod?: number
  filterRsiThreshold?: number
  filterRsiCondition?: 'above' | 'below'
  filterGapEnabled: boolean
  filterGapThreshold?: number
  filterGapDirection?: 'up' | 'down' | 'any'
  filterPrevDayDollarVolumeEnabled: boolean
  filterPrevDayDollarVolume?: number
  filterRelativeVolumeEnabled: boolean
  filterRelativeVolumeRecentDays?: number
  filterRelativeVolumeLookbackDays?: number
  filterRelativeVolumeMinRatio?: number
  
  // Backtest columns
  backtestId?: string
  cacheHash?: string
  backtestStartDate?: string
  backtestEndDate?: string
  
  // All backtest performance metrics
  totalReturn?: number
  netProfit?: number
  netProfitCurrency?: number
  compoundingAnnualReturn?: number
  finalValue?: number
  startEquity?: number
  endEquity?: number
  
  // Risk metrics
  sharpeRatio?: number
  sortinoRatio?: number
  maxDrawdown?: number
  probabilisticSharpeRatio?: number
  annualStandardDeviation?: number
  annualVariance?: number
  beta?: number
  alpha?: number
  
  // Trading statistics
  totalTrades?: number
  winningTrades?: number
  losingTrades?: number
  winRate?: number
  lossRate?: number
  averageWin?: number
  averageLoss?: number
  profitFactor?: number
  profitLossRatio?: number
  expectancy?: number
  totalOrders?: number
  
  // Advanced metrics
  informationRatio?: number
  trackingError?: number
  treynorRatio?: number
  totalFees?: number
  estimatedStrategyCapacity?: number
  lowestCapacityAsset?: string
  portfolioTurnover?: number
  
  // Strategy-specific metrics
  pivotHighsDetected?: number
  pivotLowsDetected?: number
  bosSignalsGenerated?: number
  positionFlips?: number
  liquidationEvents?: number
  
  // Algorithm parameters
  initialCash?: number
  pivotBars?: number
  lowerTimeframe?: string
  strategyName?: string
  
  // Timestamps
  backtestCreatedAt?: string
}
```

#### 4. **Key Implementation Considerations**:
- Each row represents one symbol's screening and backtest results
- One row per symbol per day (flat table structure)
- All screener filter columns + all backtest result columns in same row
- Supports sorting and filtering on any column
- Easy to export to CSV/Excel for analysis
- Frontend can display this in a standard data table with all columns visible

#### 5. **Frontend Display**:
- Use a data table component (like AG Grid or similar) to display all columns
- Allow column hiding/showing for better UX
- Support sorting on any column
- Filter by date range, symbol, or performance metrics
- Export functionality for the combined data