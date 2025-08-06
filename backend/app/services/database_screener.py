"""
Database-based screener engine that reads from TimescaleDB
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Set, Any, Tuple
import pytz
from decimal import Decimal

from app.services.database import db_pool, ET
from app.models.stock import StockData, StockBar
from app.services.screener import ScreenerEngine
from app.core.filters import BaseFilter, FilterResult
from app.core.filter_analyzer import FilterRequirementAnalyzer

logger = logging.getLogger(__name__)


class DatabaseScreenerEngine(ScreenerEngine):
    """
    Screener engine that reads data from TimescaleDB instead of API
    """
    
    def __init__(self):
        super().__init__(polygon_client=None)  # No polygon client needed
        self.db_pool = db_pool
        
    async def screen_stocks(
        self,
        symbols: List[str],
        filters: List[BaseFilter],
        start_date: date,
        end_date: date,
        max_workers: int = 100
    ) -> Dict[str, Dict[str, Any]]:
        """
        Screen stocks using data from database
        
        Args:
            symbols: List of symbols to screen
            filters: List of filters to apply
            start_date: Start date for screening
            end_date: End date for screening
            max_workers: Maximum concurrent database queries
            
        Returns:
            Dictionary of screening results
        """
        logger.info(f"Starting database screening for {len(symbols)} symbols with {len(filters)} filters")
        start_time = datetime.now()
        
        # Analyze filter requirements
        analyzer = FilterRequirementAnalyzer()
        filter_requirements = []
        for filter_instance in filters:
            requirements = analyzer.analyze_filter(filter_instance)
            filter_requirements.extend(requirements)
            
        # Calculate extended date range if needed
        if filter_requirements:
            max_lookback = max(req.lookback_days for req in filter_requirements)
            extended_start_date = start_date - timedelta(days=max_lookback + 7)  # Add buffer for weekends
        else:
            extended_start_date = start_date
            
        logger.info(f"Fetching data from {extended_start_date} to {end_date} (extended by {(start_date - extended_start_date).days} days)")
        
        # Create semaphore for concurrent control
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_symbol(symbol: str) -> Tuple[str, Optional[Dict[str, Any]]]:
            """Process a single symbol"""
            async with semaphore:
                try:
                    # Fetch data from database
                    stock_data = await self._fetch_stock_data(
                        symbol, extended_start_date, end_date
                    )
                    
                    if not stock_data or not stock_data.bars:
                        logger.debug(f"No data found for {symbol}")
                        return symbol, None
                        
                    # Apply filters
                    results = {}
                    all_passed = True
                    
                    for filter_instance in filters:
                        filter_name = filter_instance.__class__.__name__
                        
                        try:
                            result = filter_instance.apply(stock_data)
                            results[filter_name] = {
                                "passed": result.passed,
                                "value": result.value,
                                "metadata": result.metadata
                            }
                            
                            if not result.passed:
                                all_passed = False
                                
                        except Exception as e:
                            logger.error(f"Error applying {filter_name} to {symbol}: {e}")
                            results[filter_name] = {
                                "passed": False,
                                "value": None,
                                "metadata": {"error": str(e)}
                            }
                            all_passed = False
                            
                    # Only include if all filters passed
                    if all_passed:
                        # Trim bars to requested date range
                        trimmed_bars = [
                            bar for bar in stock_data.bars
                            if start_date <= bar.date <= end_date
                        ]
                        
                        if trimmed_bars:
                            latest_bar = trimmed_bars[-1]
                            
                            return symbol, {
                                "symbol": symbol,
                                "filters": results,
                                "latest_price": float(latest_bar.close),
                                "latest_volume": latest_bar.volume,
                                "date": latest_bar.date.isoformat()
                            }
                            
                    return symbol, None
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    return symbol, None
                    
        # Process all symbols concurrently
        tasks = [process_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        
        # Build final results
        screened_stocks = {}
        passed_count = 0
        
        for symbol, result in results:
            if result:
                screened_stocks[symbol] = result
                passed_count += 1
                
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(
            f"Database screening complete: {passed_count}/{len(symbols)} stocks passed "
            f"in {duration:.2f} seconds ({len(symbols)/duration:.2f} symbols/sec)"
        )
        
        return screened_stocks
        
    async def _fetch_stock_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> Optional[StockData]:
        """Fetch stock data from database"""
        try:
            # Convert dates to timestamps
            start_ts = ET.localize(datetime.combine(start_date, datetime.min.time()))
            end_ts = ET.localize(datetime.combine(end_date, datetime.max.time()))
            
            # Fetch bars from database
            rows = await self.db_pool.fetch('''
                SELECT 
                    DATE(time) as date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    vwap
                FROM daily_bars
                WHERE symbol = $1
                AND time >= $2
                AND time <= $3
                ORDER BY time ASC
            ''', symbol, start_ts, end_ts)
            
            if not rows:
                return None
                
            # Convert to StockBar objects
            bars = []
            for row in rows:
                bar = StockBar(
                    symbol=symbol,
                    date=row['date'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=row['volume'],
                    vwap=float(row['vwap']) if row['vwap'] else None
                )
                bars.append(bar)
                
            return StockData(symbol=symbol, bars=bars)
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
            
    async def fetch_previous_close(
        self,
        symbol: str,
        target_date: date
    ) -> Optional[float]:
        """
        Fetch previous trading day close from database
        
        Args:
            symbol: Stock symbol
            target_date: Date to get previous close for
            
        Returns:
            Previous close price or None
        """
        try:
            # Convert date to timestamp
            target_ts = ET.localize(datetime.combine(target_date, datetime.min.time()))
            
            # Query for the most recent close before target date
            row = await self.db_pool.fetchrow('''
                SELECT close
                FROM daily_bars
                WHERE symbol = $1
                AND time < $2
                ORDER BY time DESC
                LIMIT 1
            ''', symbol, target_ts)
            
            if row:
                return float(row['close'])
                
            return None
            
        except Exception as e:
            logger.error(f"Error fetching previous close for {symbol}: {e}")
            return None
            
    async def fetch_previous_closes_bulk(
        self,
        symbols: List[str],
        target_date: date
    ) -> Dict[str, Optional[float]]:
        """
        Fetch previous trading day closes for multiple symbols efficiently
        
        Args:
            symbols: List of symbols
            target_date: Date to get previous closes for
            
        Returns:
            Dictionary mapping symbol to previous close
        """
        try:
            # Convert date to timestamp
            target_ts = ET.localize(datetime.combine(target_date, datetime.min.time()))
            
            # Use a single query with lateral join for efficiency
            query = '''
                SELECT DISTINCT ON (s.symbol) 
                    s.symbol,
                    d.close
                FROM unnest($1::text[]) AS s(symbol)
                LEFT JOIN LATERAL (
                    SELECT close
                    FROM daily_bars
                    WHERE symbol = s.symbol
                    AND time < $2
                    ORDER BY time DESC
                    LIMIT 1
                ) d ON true
                ORDER BY s.symbol
            '''
            
            rows = await self.db_pool.fetch(query, symbols, target_ts)
            
            # Build results dictionary
            results = {}
            for row in rows:
                results[row['symbol']] = float(row['close']) if row['close'] else None
                
            # Add None for any missing symbols
            for symbol in symbols:
                if symbol not in results:
                    results[symbol] = None
                    
            return results
            
        except Exception as e:
            logger.error(f"Error fetching bulk previous closes: {e}")
            return {symbol: None for symbol in symbols}
            
    async def get_data_coverage(
        self,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get data coverage information for symbols
        
        Args:
            symbols: Optional list of symbols (None = all)
            
        Returns:
            Dictionary with coverage information
        """
        try:
            if symbols:
                # Get coverage for specific symbols
                query = '''
                    SELECT 
                        symbol,
                        data_type,
                        start_date,
                        end_date,
                        last_updated
                    FROM data_coverage
                    WHERE symbol = ANY($1)
                    ORDER BY symbol, data_type
                '''
                rows = await self.db_pool.fetch(query, symbols)
            else:
                # Get all coverage
                query = '''
                    SELECT 
                        symbol,
                        data_type,
                        start_date,
                        end_date,
                        last_updated
                    FROM data_coverage
                    ORDER BY symbol, data_type
                '''
                rows = await self.db_pool.fetch(query)
                
            # Build coverage dictionary
            coverage = {}
            for row in rows:
                symbol = row['symbol']
                if symbol not in coverage:
                    coverage[symbol] = {}
                    
                coverage[symbol][row['data_type']] = {
                    'start_date': row['start_date'].isoformat(),
                    'end_date': row['end_date'].isoformat(),
                    'last_updated': row['last_updated'].isoformat()
                }
                
            return coverage
            
        except Exception as e:
            logger.error(f"Error getting data coverage: {e}")
            return {}
            
    async def get_available_symbols(
        self,
        min_bars: int = 1,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[str]:
        """
        Get list of symbols with available data
        
        Args:
            min_bars: Minimum number of bars required
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of available symbols
        """
        try:
            # Build query based on filters
            conditions = []
            params = []
            
            if start_date:
                start_ts = ET.localize(datetime.combine(start_date, datetime.min.time()))
                conditions.append(f"time >= ${len(params) + 1}")
                params.append(start_ts)
                
            if end_date:
                end_ts = ET.localize(datetime.combine(end_date, datetime.max.time()))
                conditions.append(f"time <= ${len(params) + 1}")
                params.append(end_ts)
                
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            query = f'''
                SELECT symbol, COUNT(*) as bar_count
                FROM daily_bars
                {where_clause}
                GROUP BY symbol
                HAVING COUNT(*) >= ${len(params) + 1}
                ORDER BY symbol
            '''
            
            params.append(min_bars)
            
            rows = await self.db_pool.fetch(query, *params)
            
            return [row['symbol'] for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return []
            
    async def check_data_quality(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[str, Dict[str, Any]]:
        """
        Check data quality for symbols in date range
        
        Returns information about gaps, invalid data, etc.
        """
        quality_report = {}
        
        for symbol in symbols:
            try:
                # Get all dates with data
                start_ts = ET.localize(datetime.combine(start_date, datetime.min.time()))
                end_ts = ET.localize(datetime.combine(end_date, datetime.max.time()))
                
                rows = await self.db_pool.fetch('''
                    SELECT 
                        DATE(time) as date,
                        open, high, low, close, volume, vwap,
                        CASE 
                            WHEN high < low THEN true
                            WHEN high < open OR high < close THEN true
                            WHEN low > open OR low > close THEN true
                            ELSE false
                        END as invalid_ohlc
                    FROM daily_bars
                    WHERE symbol = $1
                    AND time >= $2
                    AND time <= $3
                    ORDER BY time
                ''', symbol, start_ts, end_ts)
                
                if not rows:
                    quality_report[symbol] = {
                        'has_data': False,
                        'bar_count': 0
                    }
                    continue
                    
                # Check for gaps and invalid data
                dates = [row['date'] for row in rows]
                invalid_bars = sum(1 for row in rows if row['invalid_ohlc'])
                missing_vwap = sum(1 for row in rows if not row['vwap'])
                
                # Find gaps
                gaps = []
                for i in range(1, len(dates)):
                    days_diff = (dates[i] - dates[i-1]).days
                    if days_diff > 1:
                        # Check if there are trading days in between
                        current = dates[i-1] + timedelta(days=1)
                        while current < dates[i]:
                            if current.weekday() < 5:  # Weekday
                                gaps.append(current.isoformat())
                            current += timedelta(days=1)
                            
                quality_report[symbol] = {
                    'has_data': True,
                    'bar_count': len(rows),
                    'date_range': {
                        'start': dates[0].isoformat(),
                        'end': dates[-1].isoformat()
                    },
                    'gaps': gaps,
                    'gap_count': len(gaps),
                    'invalid_bars': invalid_bars,
                    'missing_vwap': missing_vwap,
                    'data_quality_score': (1 - (invalid_bars + len(gaps)) / max(len(rows), 1)) * 100
                }
                
            except Exception as e:
                logger.error(f"Error checking data quality for {symbol}: {e}")
                quality_report[symbol] = {
                    'has_data': False,
                    'error': str(e)
                }
                
        return quality_report