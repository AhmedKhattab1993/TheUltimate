# Screener Results Schema - Implementation Documentation

## Overview

This document provides comprehensive documentation for the new screener_results schema that has been successfully implemented and tested. The schema has been redesigned to align with the pipeline configuration, providing better query performance and data integrity through individual typed columns instead of JSON storage.

## Current Implementation Status

### ✅ Successfully Implemented:
- **Database Schema**: Migration 004 has been applied - screener_results table uses new column-based schema
- **Pipeline Configuration**: Complete filter system with enable/disable flags for all filter types
- **Backend APIs**: Updated to work with new schema and maintain frontend compatibility
- **Cache Service**: Updated to use individual columns for better query performance
- **Pipeline Storage**: Updated to populate all new filter columns correctly

### 🔄 Migration State:
- **Migration 003**: Not applied (cached_screener_results and cached_backtest_results tables do not exist)
- **Migration 004**: Applied (screener_results table has new schema with all pipeline filter columns)
- **Current Active Tables**: `screener_results` (new schema), `market_structure_results` (backtest results)

## Database Schema

### Screener Results Table Structure

The `screener_results` table now contains individual columns for all pipeline filters:

```sql
CREATE TABLE screener_results (
    -- Core Identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(10) NOT NULL,
    company_name VARCHAR(255),
    session_id UUID,  -- Groups results from same screening run
    
    -- Timestamps
    screened_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_date DATE NOT NULL,  -- Date of stock data used
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Price Range Filter
    filter_min_price NUMERIC,
    filter_max_price NUMERIC,
    
    -- Price vs Moving Average Filter (NEW)
    filter_price_vs_ma_enabled BOOLEAN,
    filter_price_vs_ma_period INTEGER,        -- e.g., 20 for SMA20
    filter_price_vs_ma_condition VARCHAR(10), -- 'above' or 'below'
    
    -- RSI Filter (NEW)
    filter_rsi_enabled BOOLEAN,
    filter_rsi_period INTEGER,                -- e.g., 14
    filter_rsi_threshold NUMERIC(5, 2),      -- e.g., 30.0
    filter_rsi_condition VARCHAR(10),        -- 'above' or 'below'
    
    -- Gap Filter (ENHANCED)
    filter_gap_enabled BOOLEAN,
    filter_gap_threshold NUMERIC(5, 2),      -- Minimum gap percentage
    filter_gap_direction VARCHAR(10),        -- 'up', 'down', or 'any'
    
    -- Previous Day Dollar Volume Filter (NEW)
    filter_prev_day_dollar_volume_enabled BOOLEAN,
    filter_prev_day_dollar_volume NUMERIC(15, 2),
    
    -- Relative Volume Filter (NEW)
    filter_relative_volume_enabled BOOLEAN,
    filter_relative_volume_recent_days INTEGER,
    filter_relative_volume_lookback_days INTEGER,
    filter_relative_volume_min_ratio NUMERIC(5, 2)
);
```

### Key Schema Changes Made

#### ✅ Added Columns (NEW):
1. **Price vs MA Details**: 
   - `filter_price_vs_ma_enabled`, `filter_price_vs_ma_period`, `filter_price_vs_ma_condition`
   - Replaces generic `filter_above_sma20` with configurable period and condition

2. **RSI Filter Support**:
   - `filter_rsi_enabled`, `filter_rsi_period`, `filter_rsi_threshold`, `filter_rsi_condition`
   - Complete RSI filter support matching pipeline configuration

3. **Enhanced Gap Filter**:
   - `filter_gap_enabled`, `filter_gap_threshold`, `filter_gap_direction`
   - Added direction support (up/down/any) and enabled flag

4. **Previous Day Dollar Volume**:
   - `filter_prev_day_dollar_volume_enabled`, `filter_prev_day_dollar_volume`
   - Replaces simple volume filter with dollar volume

5. **Relative Volume Filter**:
   - `filter_relative_volume_enabled`, `filter_relative_volume_recent_days`
   - `filter_relative_volume_lookback_days`, `filter_relative_volume_min_ratio`
   - Complete relative volume analysis support

#### ❌ Removed Columns (from original design):
1. **Market Data**: `price`, `volume`, `market_cap` (not needed for cache)
2. **Unused Filters**: `filter_min_volume`, `filter_min_market_cap`, `filter_max_market_cap`
3. **Legacy Filters**: `filter_min_change`, `filter_max_change`, `filter_min_atr`, `filter_above_vwap`
4. **Metric Columns**: `daily_change_percent`, `atr_value`, `gap_percent`, distance metrics

## Pipeline Configuration Mapping

### Complete Filter Mapping: Pipeline Config → Database Columns

| Pipeline Configuration | Database Column | Type | Description |
|------------------------|-----------------|------|-------------|
| **Price Range** |
| `price_range.enabled` | Derived from non-NULL price columns | Boolean | Filter enabled if min/max price set |
| `price_range.min_price` | `filter_min_price` | NUMERIC | Minimum opening price |
| `price_range.max_price` | `filter_max_price` | NUMERIC | Maximum opening price |
| **Price vs MA** |
| `price_vs_ma.enabled` | `filter_price_vs_ma_enabled` | BOOLEAN | Price vs MA filter enabled |
| `price_vs_ma.ma_period` | `filter_price_vs_ma_period` | INTEGER | Moving average period (20, 50, 200) |
| `price_vs_ma.condition` | `filter_price_vs_ma_condition` | VARCHAR(10) | 'above' or 'below' |
| **RSI Filter** |
| `rsi.enabled` | `filter_rsi_enabled` | BOOLEAN | RSI filter enabled |
| `rsi.rsi_period` | `filter_rsi_period` | INTEGER | RSI calculation period (default: 14) |
| `rsi.threshold` | `filter_rsi_threshold` | NUMERIC(5,2) | RSI threshold value |
| `rsi.condition` | `filter_rsi_condition` | VARCHAR(10) | 'above' or 'below' |
| **Gap Filter** |
| `gap.enabled` | `filter_gap_enabled` | BOOLEAN | Gap filter enabled |
| `gap.gap_threshold` | `filter_gap_threshold` | NUMERIC(5,2) | Minimum gap percentage |
| `gap.direction` | `filter_gap_direction` | VARCHAR(10) | 'up', 'down', or 'both' |
| **Previous Day Dollar Volume** |
| `prev_day_dollar_volume.enabled` | `filter_prev_day_dollar_volume_enabled` | BOOLEAN | Dollar volume filter enabled |
| `prev_day_dollar_volume.min_dollar_volume` | `filter_prev_day_dollar_volume` | NUMERIC(15,2) | Minimum dollar volume |
| **Relative Volume** |
| `relative_volume.enabled` | `filter_relative_volume_enabled` | BOOLEAN | Relative volume filter enabled |
| `relative_volume.recent_days` | `filter_relative_volume_recent_days` | INTEGER | Recent days for volume calculation |
| `relative_volume.lookback_days` | `filter_relative_volume_lookback_days` | INTEGER | Historical days for comparison |
| `relative_volume.min_ratio` | `filter_relative_volume_min_ratio` | NUMERIC(5,2) | Minimum volume ratio |

### Example Pipeline Configuration

```yaml
screening:
  filters:
    price_range:
      enabled: true
      min_price: 5
      max_price: 1000
    
    price_vs_ma:
      enabled: true
      ma_period: 20
      condition: "above"
    
    rsi:
      enabled: false
      rsi_period: 14
      threshold: 30.0
      condition: "below"
    
    gap:
      enabled: true
      gap_threshold: 2.0
      direction: "up"
    
    prev_day_dollar_volume:
      enabled: true
      min_dollar_volume: 10000000
    
    relative_volume:
      enabled: true
      recent_days: 2
      lookback_days: 20
      min_ratio: 1.5
```

## API Changes and Response Format

### Backend API Updates

The backend APIs have been updated to work with the new schema while maintaining frontend compatibility:

#### List Endpoint (`GET /api/v2/screener/results`)
- **Groups by `session_id`**: Each screening run creates one session with multiple symbols
- **Filter Reconstruction**: Rebuilds filter objects from individual columns
- **Maintains Response Format**: Frontend receives same structure as before

#### Detail Endpoint (`GET /api/v2/screener/results/{session_id}`)
- **Symbol Aggregation**: Returns all symbols from the screening session
- **Complete Filter Information**: Shows all applied filters with their parameters
- **Enhanced Descriptions**: User-friendly filter descriptions (e.g., "RSI(14) < 30")

#### Example API Response Format:
```json
{
  "items": [
    {
      "id": "uuid",
      "screened_at": "2025-08-17T10:30:00Z",
      "data_date": "2025-08-16",
      "result_count": 15,
      "execution_time_ms": 2500,
      "filters": {
        "price_range": {
          "enabled": true,
          "min_price": 5.0,
          "max_price": 1000.0
        },
        "price_vs_ma": {
          "enabled": true,
          "ma_period": 20,
          "condition": "above"
        },
        "gap": {
          "enabled": true,
          "gap_threshold": 2.0,
          "direction": "up"
        }
      },
      "filter_description": "Price: $5.00 - $1000.00; Price above SMA20; Gap up ≥ 2%"
    }
  ]
}
```

### Cache Service Integration

The cache service has been updated to:
1. **Column-Based Matching**: Uses individual filter columns for precise cache matching
2. **Session Management**: Groups results by session_id for efficient retrieval
3. **Performance Optimization**: Direct column queries instead of JSON extraction

## Migration Process and History

### Applied Migrations

#### Migration 004: Align Screener Results Schema ✅ APPLIED
- **Purpose**: Align screener_results table with pipeline configuration
- **Changes Made**:
  1. Added new columns for all pipeline-specific filters
  2. Migrated existing data where possible
  3. Removed unused columns
  4. Updated indexes for performance
- **Data Migration**:
  - `filter_min_gap` → `filter_gap_threshold`
  - `filter_above_sma20` → `filter_price_vs_ma_*` columns
- **Rollback Available**: Backup table `screener_results_backup_004` created

#### Migration 003: Restructure Cache Tables ❌ NOT APPLIED
- **Purpose**: Create cached_screener_results and cached_backtest_results tables
- **Status**: Migration file exists but not executed
- **Note**: Current system uses direct screener_results table instead

### Migration Safety and Rollback

#### Rollback Capability
```sql
-- To rollback migration 004 if needed:
DROP TABLE IF EXISTS screener_results;
ALTER TABLE screener_results_backup_004 RENAME TO screener_results;
-- Recreate original indexes
```

#### Data Safety
- **Backup Created**: `screener_results_backup_004` contains pre-migration data
- **No Data Loss**: All existing data preserved during migration
- **Testing**: Migration tested and verified before production use

## Frontend Updates

### Display Changes
The frontend has been updated to:
1. **Enhanced Filter Display**: Shows detailed filter parameters instead of generic descriptions
2. **Comprehensive Tooltips**: Explains each filter type and its parameters
3. **Backward Compatibility**: Works seamlessly with new API format

### Filter Description Examples
- **Old**: "Price Filter, SMA Filter, Gap Filter"
- **New**: "Price: $5.00 - $1000.00; Price above SMA20; Gap up ≥ 2.0%; Volume ≥ $10.0M"

## Performance Benefits

### Query Performance Improvements
1. **Direct Column Access**: No JSON parsing required
2. **Better Indexing**: Individual columns can be indexed efficiently
3. **Optimized WHERE Clauses**: Database can use column statistics for query planning
4. **Reduced Data Transfer**: Only required columns are selected

### Cache Efficiency
1. **Precise Matching**: Exact filter parameter matching for better cache hit rates
2. **Session-Based Grouping**: Efficient retrieval of related results
3. **Column-Based Hashing**: More stable cache keys

## Testing and Validation

### Integration Testing Results ✅
- **Pipeline Execution**: Successfully tested with various filter combinations
- **Database Storage**: All filter parameters correctly stored
- **API Responses**: Frontend compatibility maintained
- **Cache Functionality**: Cache hit/miss logic working correctly

### Test Coverage
1. **All Filter Types**: Tested with each filter enabled/disabled independently
2. **Complex Combinations**: Multiple filters active simultaneously
3. **Edge Cases**: Empty results, all filters disabled, extreme parameter values
4. **Performance**: Query response times improved significantly

## Breaking Changes and Migration Notes

### Breaking Changes Made
1. **Removed Columns**: Market data and unused filter columns no longer available
2. **Changed Filter Names**: `filter_min_gap` → `filter_gap_threshold`
3. **New Required Fields**: Enabled flags for each filter type

### Backward Compatibility
- **API Contract**: Response format unchanged for frontend
- **Migration Path**: Automatic data migration for compatible fields
- **Graceful Degradation**: Missing filter data defaults to disabled

## Future Development Considerations

### Schema Extensibility
The new schema makes it easy to:
1. **Add New Filters**: Follow the `filter_[name]_enabled` + parameters pattern
2. **Enhance Existing Filters**: Add new parameter columns as needed
3. **Performance Tuning**: Add indexes on frequently queried columns

### Recommended Enhancements
1. **Additional Indexes**: Consider composite indexes for common filter combinations
2. **Data Archival**: Implement automated cleanup of old screening results
3. **Statistics Tracking**: Add columns for query performance metrics

## Operational Notes

### Database Maintenance
- **Regular Cleanup**: Remove screening results older than TTL period
- **Index Monitoring**: Monitor query performance and add indexes as needed
- **Backup Strategy**: Regular backups especially before schema changes

### Monitoring
- **Query Performance**: Monitor individual column query times
- **Cache Hit Rates**: Track improvements in cache efficiency
- **Storage Growth**: Monitor table size growth with new column structure

## Conclusion

The screener results schema migration has been successfully completed and tested. The new column-based approach provides:

1. **Better Performance**: Direct column queries instead of JSON extraction
2. **Complete Filter Support**: All pipeline filters properly represented
3. **Improved Maintainability**: Clear schema with proper data types
4. **Frontend Compatibility**: Seamless operation with existing UI

The implementation aligns perfectly with the pipeline configuration and provides a solid foundation for future enhancements to the screening and backtesting system.

### Success Criteria Met ✅
- ✅ All pipeline filters have corresponding database columns
- ✅ Frontend displays accurate and detailed filter information
- ✅ Cache functionality improved with column-based matching
- ✅ No data loss during migration
- ✅ Performance improvements in query execution
- ✅ System successfully tested end-to-end

The system is now ready for production use with the new schema and enhanced filtering capabilities.