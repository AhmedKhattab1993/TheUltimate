"""
Data collection service for fetching and storing stock data from Polygon.io
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple, Any
from decimal import Decimal
import pytz

from app.services.polygon_client import PolygonClient, PolygonAPIError
from app.services.database import db_pool, convert_to_et, DatabaseTransaction
from app.models.stock import StockData, StockBar
from app.config import settings

logger = logging.getLogger(__name__)

ET = pytz.timezone('US/Eastern')


class DataValidationError(Exception):
    """Exception raised when data validation fails"""
    pass


class DataCollector:
    """
    Handles data collection from Polygon.io and storage in TimescaleDB
    """
    
    def __init__(self, polygon_client: Optional[PolygonClient] = None):
        self.polygon_client = polygon_client
        self.batch_size = settings.data_collection_batch_size
        self.max_concurrent = settings.data_collection_max_concurrent
        self.retry_attempts = settings.data_collection_retry_attempts
        self.retry_delay = settings.data_collection_retry_delay
        
    async def __aenter__(self):
        if not self.polygon_client:
            self.polygon_client = PolygonClient()
            await self.polygon_client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.polygon_client:
            await self.polygon_client.__aexit__(exc_type, exc_val, exc_tb)
            
    def _validate_ohlc(self, bar: StockBar) -> bool:
        """
        Validate OHLC data
        
        Returns:
            True if valid, raises DataValidationError if invalid
        """
        # Check basic OHLC constraints
        if bar.high < bar.low:
            raise DataValidationError(f"High ({bar.high}) is less than low ({bar.low})")
            
        if bar.high < bar.open or bar.high < bar.close:
            raise DataValidationError(f"High ({bar.high}) is less than open ({bar.open}) or close ({bar.close})")
            
        if bar.low > bar.open or bar.low > bar.close:
            raise DataValidationError(f"Low ({bar.low}) is greater than open ({bar.open}) or close ({bar.close})")
            
        if bar.volume < 0:
            raise DataValidationError(f"Volume ({bar.volume}) is negative")
            
        return True
        
    def _calculate_vwap_if_missing(self, bar: StockBar) -> float:
        """Calculate VWAP if missing using typical price"""
        if bar.vwap is None or bar.vwap == 0:
            if bar.volume > 0:
                # Use typical price as approximation
                return (bar.high + bar.low + bar.close) / 3
            else:
                return bar.close
        return bar.vwap
        
    async def _store_daily_bars(self, bars: List[StockBar], conn=None) -> int:
        """
        Store daily bars in database using bulk COPY
        
        Returns:
            Number of bars stored
        """
        if not bars:
            return 0
            
        # Prepare records for bulk insert
        records = []
        for bar in bars:
            try:
                # Validate data
                self._validate_ohlc(bar)
                
                # Convert date to Eastern Time timestamp
                et_time = ET.localize(datetime.combine(bar.date, datetime.min.time()))
                
                # Calculate VWAP if missing
                vwap = self._calculate_vwap_if_missing(bar)
                
                records.append((
                    et_time,
                    bar.symbol,
                    Decimal(str(bar.open)),
                    Decimal(str(bar.high)),
                    Decimal(str(bar.low)),
                    Decimal(str(bar.close)),
                    bar.volume,
                    Decimal(str(vwap)) if vwap else None,
                    None,  # transactions
                    True,  # adjusted
                    datetime.now(pytz.UTC)  # created_at
                ))
                
            except DataValidationError as e:
                logger.warning(f"Validation error for {bar.symbol} on {bar.date}: {e}")
                await self._log_error(bar.symbol, "validation_error", str(e), bar.date, bar.date)
                continue
                
        if not records:
            return 0
            
        # Use provided connection or get new one
        if conn:
            await self._bulk_insert_daily_bars(conn, records)
        else:
            async with db_pool.acquire() as conn:
                await self._bulk_insert_daily_bars(conn, records)
                
        return len(records)
        
    async def _bulk_insert_daily_bars(self, conn, records: List[tuple]):
        """Perform bulk insert of daily bars"""
        # Use ON CONFLICT to handle duplicates
        await conn.executemany('''
            INSERT INTO daily_bars (time, symbol, open, high, low, close, volume, vwap, transactions, adjusted, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (symbol, time) 
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                vwap = EXCLUDED.vwap,
                transactions = EXCLUDED.transactions,
                adjusted = EXCLUDED.adjusted,
                created_at = EXCLUDED.created_at
        ''', records)
        
    async def _log_error(
        self,
        symbol: str,
        error_type: str,
        error_message: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ):
        """Log data fetch error to database"""
        try:
            await db_pool.execute('''
                INSERT INTO data_fetch_errors (symbol, error_type, error_message, start_date, end_date)
                VALUES ($1, $2, $3, $4, $5)
            ''', symbol, error_type, error_message, start_date, end_date)
        except Exception as e:
            logger.error(f"Failed to log error to database: {e}")
            
    async def _update_data_coverage(self, symbol: str, data_type: str, start_date: date, end_date: date):
        """Update data coverage tracking"""
        await db_pool.execute('''
            INSERT INTO data_coverage (symbol, data_type, start_date, end_date, last_updated)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (symbol, data_type)
            DO UPDATE SET
                start_date = LEAST(data_coverage.start_date, EXCLUDED.start_date),
                end_date = GREATEST(data_coverage.end_date, EXCLUDED.end_date),
                last_updated = EXCLUDED.last_updated
        ''', symbol, data_type, start_date, end_date, datetime.now(pytz.UTC))
        
    async def collect_daily_data_for_date(
        self,
        target_date: date,
        symbols: Optional[List[str]] = None,
        use_bulk_endpoint: bool = True
    ) -> Dict[str, int]:
        """
        Collect daily data for a specific date
        
        Args:
            target_date: Date to collect data for
            symbols: Optional list of symbols to filter (None = all symbols)
            use_bulk_endpoint: Whether to use bulk endpoint
            
        Returns:
            Dictionary with collection statistics
        """
        start_time = datetime.now()
        stats = {
            "total_symbols": 0,
            "bars_stored": 0,
            "errors": 0,
            "duration_seconds": 0
        }
        
        try:
            if use_bulk_endpoint:
                logger.info(f"Collecting bulk daily data for {target_date}")
                
                # Define streaming callback for processing data as it arrives
                bars_buffer = []
                
                async def streaming_callback(symbol: str, stock_data: StockData):
                    """Process data as it streams in"""
                    nonlocal bars_buffer
                    
                    # Filter by symbols if specified
                    if symbols and symbol not in symbols:
                        return
                        
                    bars_buffer.extend(stock_data.bars)
                    
                    # Store in batches
                    if len(bars_buffer) >= self.batch_size:
                        stored = await self._store_daily_bars(bars_buffer)
                        stats["bars_stored"] += stored
                        bars_buffer = []
                        
                # Fetch data with streaming
                all_data = await self.polygon_client.fetch_bulk_daily_data(
                    target_date,
                    streaming_callback=streaming_callback
                )
                
                # Store any remaining bars
                if bars_buffer:
                    stored = await self._store_daily_bars(bars_buffer)
                    stats["bars_stored"] += stored
                    
                stats["total_symbols"] = len(all_data)
                
            else:
                # Use individual calls for specific symbols
                if not symbols:
                    raise ValueError("Symbols list required when not using bulk endpoint")
                    
                logger.info(f"Collecting daily data for {len(symbols)} symbols on {target_date}")
                
                # Fetch data in batches
                for i in range(0, len(symbols), self.max_concurrent):
                    batch_symbols = symbols[i:i + self.max_concurrent]
                    
                    batch_data = await self.polygon_client.fetch_batch_historical_data(
                        symbols=batch_symbols,
                        start_date=target_date,
                        end_date=target_date,
                        max_concurrent=self.max_concurrent
                    )
                    
                    # Store each symbol's data
                    for symbol, stock_data in batch_data.items():
                        try:
                            stored = await self._store_daily_bars(stock_data.bars)
                            stats["bars_stored"] += stored
                            
                            if stock_data.bars:
                                await self._update_data_coverage(
                                    symbol, "daily", target_date, target_date
                                )
                                
                        except Exception as e:
                            logger.error(f"Error storing data for {symbol}: {e}")
                            await self._log_error(symbol, "storage_error", str(e), target_date, target_date)
                            stats["errors"] += 1
                            
                stats["total_symbols"] = len(symbols)
                
        except Exception as e:
            logger.error(f"Error collecting daily data: {e}")
            stats["errors"] += 1
            raise
            
        finally:
            stats["duration_seconds"] = (datetime.now() - start_time).total_seconds()
            logger.info(f"Collection complete: {stats}")
            
        return stats
        
    async def collect_historical_data(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Collect historical data for multiple symbols and date range
        
        Args:
            symbols: List of symbols to collect
            start_date: Start date
            end_date: End date  
            skip_existing: Skip symbols that already have data
            
        Returns:
            Collection statistics
        """
        start_time = datetime.now()
        stats = {
            "total_symbols": len(symbols),
            "symbols_processed": 0,
            "bars_stored": 0,
            "symbols_skipped": 0,
            "errors": 0,
            "duration_seconds": 0
        }
        
        # Check existing coverage if skip_existing is True
        symbols_to_fetch = []
        
        if skip_existing:
            for symbol in symbols:
                coverage = await db_pool.fetchrow('''
                    SELECT start_date, end_date 
                    FROM data_coverage 
                    WHERE symbol = $1 AND data_type = 'daily'
                ''', symbol)
                
                if coverage:
                    # Check if we already have the data
                    if coverage['start_date'] <= start_date and coverage['end_date'] >= end_date:
                        stats["symbols_skipped"] += 1
                        continue
                        
                symbols_to_fetch.append(symbol)
        else:
            symbols_to_fetch = symbols
            
        logger.info(f"Collecting historical data for {len(symbols_to_fetch)} symbols from {start_date} to {end_date}")
        
        # Process in batches with retries
        for i in range(0, len(symbols_to_fetch), self.max_concurrent):
            batch_symbols = symbols_to_fetch[i:i + self.max_concurrent]
            
            for attempt in range(self.retry_attempts):
                try:
                    # Fetch batch data
                    batch_data = await self.polygon_client.fetch_batch_historical_data(
                        symbols=batch_symbols,
                        start_date=start_date,
                        end_date=end_date,
                        max_concurrent=self.max_concurrent
                    )
                    
                    # Store each symbol's data in a transaction
                    async with DatabaseTransaction() as conn:
                        for symbol, stock_data in batch_data.items():
                            try:
                                stored = await self._store_daily_bars(stock_data.bars, conn)
                                stats["bars_stored"] += stored
                                stats["symbols_processed"] += 1
                                
                                if stock_data.bars:
                                    await self._update_data_coverage(
                                        symbol, "daily", start_date, end_date
                                    )
                                    
                            except Exception as e:
                                logger.error(f"Error storing data for {symbol}: {e}")
                                await self._log_error(
                                    symbol, "storage_error", str(e), start_date, end_date
                                )
                                stats["errors"] += 1
                                
                    break  # Success, exit retry loop
                    
                except PolygonAPIError as e:
                    logger.warning(f"API error on attempt {attempt + 1}: {e}")
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        # Log errors for each symbol in the batch
                        for symbol in batch_symbols:
                            await self._log_error(
                                symbol, "api_error", str(e), start_date, end_date
                            )
                        stats["errors"] += len(batch_symbols)
                        
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    stats["errors"] += len(batch_symbols)
                    
            # Progress update
            processed = min(i + self.max_concurrent, len(symbols_to_fetch))
            logger.info(f"Progress: {processed}/{len(symbols_to_fetch)} symbols")
            
        stats["duration_seconds"] = (datetime.now() - start_time).total_seconds()
        logger.info(f"Historical data collection complete: {stats}")
        
        return stats
        
    async def get_missing_dates(self, symbols: List[str], start_date: date, end_date: date) -> Dict[str, List[date]]:
        """Get missing dates for symbols within a date range"""
        missing_dates = {}
        
        for symbol in symbols:
            # Get existing dates
            rows = await db_pool.fetch('''
                SELECT DISTINCT DATE(time) as date
                FROM daily_bars
                WHERE symbol = $1 
                AND time >= $2 
                AND time <= $3
                ORDER BY date
            ''', symbol, start_date, end_date)
            
            existing_dates = {row['date'] for row in rows}
            
            # Generate all trading days in range
            current = start_date
            all_dates = []
            while current <= end_date:
                # Skip weekends
                if current.weekday() < 5:
                    all_dates.append(current)
                current += timedelta(days=1)
                
            # Find missing dates
            symbol_missing = [d for d in all_dates if d not in existing_dates]
            if symbol_missing:
                missing_dates[symbol] = symbol_missing
                
        return missing_dates
        
    async def fill_missing_data(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Fill in missing data for symbols"""
        missing_dates = await self.get_missing_dates(symbols, start_date, end_date)
        
        stats = {
            "symbols_checked": len(symbols),
            "symbols_with_gaps": len(missing_dates),
            "dates_filled": 0,
            "bars_stored": 0
        }
        
        # Group by date for efficient bulk fetching
        date_symbols = {}
        for symbol, dates in missing_dates.items():
            for date in dates:
                if date not in date_symbols:
                    date_symbols[date] = []
                date_symbols[date].append(symbol)
                
        # Fetch and store missing data
        for target_date, symbols_list in sorted(date_symbols.items()):
            logger.info(f"Filling data for {len(symbols_list)} symbols on {target_date}")
            
            try:
                result = await self.collect_daily_data_for_date(
                    target_date,
                    symbols=symbols_list,
                    use_bulk_endpoint=True
                )
                
                stats["dates_filled"] += 1
                stats["bars_stored"] += result["bars_stored"]
                
            except Exception as e:
                logger.error(f"Error filling data for {target_date}: {e}")
                
        return stats
        
    async def update_symbols_table(self) -> int:
        """Update symbols table with latest ticker information"""
        updated_count = 0
        
        try:
            # Fetch all active US stocks
            all_tickers = []
            cursor = None
            
            while True:
                response = await self.polygon_client.fetch_tickers(
                    market="stocks",
                    active=True,
                    limit=1000,
                    cursor=cursor
                )
                
                tickers = response.get("results", [])
                all_tickers.extend(tickers)
                
                # Check for next page
                next_url = response.get("next_url")
                if not next_url:
                    break
                    
                # Extract cursor from next_url
                import urllib.parse
                parsed = urllib.parse.urlparse(next_url)
                params = urllib.parse.parse_qs(parsed.query)
                cursor = params.get("cursor", [None])[0]
                
                if not cursor:
                    break
                    
            logger.info(f"Fetched {len(all_tickers)} tickers from Polygon")
            
            # Bulk insert/update symbols
            async with DatabaseTransaction() as conn:
                for ticker in all_tickers:
                    try:
                        await conn.execute('''
                            INSERT INTO symbols (
                                symbol, name, type, exchange, primary_exchange,
                                currency, market_cap, active
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (symbol) 
                            DO UPDATE SET
                                name = EXCLUDED.name,
                                type = EXCLUDED.type,
                                exchange = EXCLUDED.exchange,
                                primary_exchange = EXCLUDED.primary_exchange,
                                currency = EXCLUDED.currency,
                                market_cap = EXCLUDED.market_cap,
                                active = EXCLUDED.active,
                                updated_at = NOW()
                        ''',
                            ticker.get("ticker"),
                            ticker.get("name"),
                            ticker.get("type"),
                            ticker.get("exchange"),
                            ticker.get("primary_exchange"),
                            ticker.get("currency_name"),
                            ticker.get("market_cap"),
                            ticker.get("active", True)
                        )
                        updated_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error updating symbol {ticker.get('ticker')}: {e}")
                        
            logger.info(f"Updated {updated_count} symbols in database")
            
        except Exception as e:
            logger.error(f"Error updating symbols table: {e}")
            
        return updated_count