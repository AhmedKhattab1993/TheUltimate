import httpx
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any, Set, Tuple
from urllib.parse import urljoin
import time
from collections import deque

from app.models.stock import StockData, StockBar
from app.config import settings


# Configure logging
logger = logging.getLogger(__name__)


class PolygonAPIError(Exception):
    """Custom exception for Polygon API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class RateLimiter:
    """Simple rate limiter for API requests"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds (default: 60 for per-minute limiting)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
    
    async def acquire(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()
        
        # Remove old requests outside the time window
        while self.requests and self.requests[0] <= now - self.time_window:
            self.requests.popleft()
        
        # If we're at the limit, wait until the oldest request expires
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0]) + 0.1
            logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
            # Recursive call to clean up and check again
            await self.acquire()
        else:
            # Record this request
            self.requests.append(now)


class PolygonClient:
    """Async client for Polygon.io API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Polygon API client
        
        Args:
            api_key: Polygon API key. If not provided, uses from settings.
        """
        self.api_key = api_key or settings.polygon_api_key
        if not self.api_key:
            raise ValueError("Polygon API key is required. Set POLYGON_API_KEY environment variable.")
        
        self.base_url = settings.polygon_base_url
        
        # Only create rate limiter if rate limit is greater than 0
        self.rate_limiter = RateLimiter(settings.polygon_rate_limit) if settings.polygon_rate_limit > 0 else None
        
        # Configure HTTP client with enhanced connection pool limits for bulk operations
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=200, max_connections=500),
            headers={
                "User-Agent": "StockScreener/1.0",
                "Accept-Encoding": "gzip, deflate"  # Enable compression
            }
            # HTTP/2 disabled due to missing h2 package
        )
        
        # Simple in-memory cache for the current session
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self.cache_ttl = 300  # 5 minutes cache TTL
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close HTTP client"""
        await self.close()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL for API endpoint"""
        return urljoin(self.base_url, endpoint)
    
    def _add_auth_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add authentication parameters to request"""
        params["apiKey"] = self.api_key
        return params
    
    def _get_cache_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key from endpoint and params"""
        param_str = "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()) if k != "apiKey")
        return f"{endpoint}?{param_str}"
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make authenticated request to Polygon API with rate limiting
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            API response data
            
        Raises:
            PolygonAPIError: On API errors
        """
        # Check cache first
        cache_key = self._get_cache_key(endpoint, params)
        if cache_key in self._cache:
            cache_timestamp = self._cache_timestamps.get(cache_key, 0)
            if time.time() - cache_timestamp < self.cache_ttl:
                logger.debug(f"Cache hit for {endpoint}")
                return self._cache[cache_key]
        
        # Apply rate limiting if enabled
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        # Prepare request
        url = self._build_url(endpoint)
        params = self._add_auth_params(params or {})
        
        try:
            logger.debug(f"Making request to {endpoint}")
            response = await self.client.get(url, params=params)
            
            # Check for HTTP errors
            if response.status_code != 200:
                error_data = None
                try:
                    error_data = response.json()
                except:
                    pass
                
                error_message = f"Polygon API error: {response.status_code}"
                if error_data and "error" in error_data:
                    error_message = f"{error_message} - {error_data['error']}"
                
                logger.error(error_message)
                raise PolygonAPIError(error_message, response.status_code, error_data)
            
            data = response.json()
            
            # Check for API-level errors
            if data.get("status") == "ERROR":
                error_message = data.get("error", "Unknown API error")
                logger.error(f"API returned error: {error_message}")
                raise PolygonAPIError(f"API Error: {error_message}", response_data=data)
            
            # Cache successful responses
            self._cache[cache_key] = data
            self._cache_timestamps[cache_key] = time.time()
            
            return data
            
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise PolygonAPIError(f"Request timeout: {str(e)}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise PolygonAPIError(f"HTTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise PolygonAPIError(f"Unexpected error: {str(e)}")
    
    def _format_date(self, date_obj: date) -> str:
        """Format date for Polygon API (YYYY-MM-DD)"""
        return date_obj.strftime("%Y-%m-%d")
    
    def _parse_bar(self, symbol: str, bar_data: Dict[str, Any]) -> StockBar:
        """
        Parse Polygon bar data into StockBar model
        
        Args:
            symbol: Stock symbol
            bar_data: Raw bar data from Polygon API
            
        Returns:
            StockBar instance
        """
        # Convert timestamp to date
        timestamp_ms = bar_data["t"]
        bar_date = datetime.fromtimestamp(timestamp_ms / 1000).date()
        
        return StockBar(
            symbol=symbol,
            date=bar_date,
            open=bar_data["o"],
            high=bar_data["h"],
            low=bar_data["l"],
            close=bar_data["c"],
            volume=round(bar_data["v"]),  # Round fractional volumes to nearest integer
            vwap=bar_data.get("vw")  # VWAP might not always be present
        )
    
    async def fetch_historical_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjusted: bool = True
    ) -> StockData:
        """
        Fetch historical daily data for a single symbol
        
        Args:
            symbol: Stock symbol
            start_date: Start date for data
            end_date: End date for data
            adjusted: Whether to adjust for splits (default: True)
            
        Returns:
            StockData with historical bars
            
        Raises:
            PolygonAPIError: On API errors
        """
        endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{self._format_date(start_date)}/{self._format_date(end_date)}"
        
        params = {
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": 50000  # Max limit to get all data in one request
        }
        
        try:
            data = await self._make_request(endpoint, params)
            
            # Check if we got results
            if "results" not in data or not data["results"]:
                logger.warning(f"No data found for {symbol} between {start_date} and {end_date}")
                return StockData(symbol=symbol, bars=[])
            
            # Parse bars
            bars = [self._parse_bar(symbol, bar) for bar in data["results"]]
            
            logger.info(f"Fetched {len(bars)} bars for {symbol}")
            return StockData(symbol=symbol, bars=bars)
            
        except PolygonAPIError:
            # Re-raise Polygon errors
            raise
        except Exception as e:
            logger.error(f"Error parsing data for {symbol}: {e}")
            raise PolygonAPIError(f"Error parsing data for {symbol}: {str(e)}")
    
    async def fetch_batch_historical_data(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        adjusted: bool = True,
        continue_on_error: bool = True,
        max_concurrent: int = 100
    ) -> Dict[str, StockData]:
        """
        Fetch historical data for multiple symbols using parallel requests
        
        Args:
            symbols: List of stock symbols
            start_date: Start date for data
            end_date: End date for data
            adjusted: Whether to adjust for splits (default: True)
            continue_on_error: Whether to continue fetching if one symbol fails (default: True)
            max_concurrent: Maximum number of concurrent requests (default: 100)
            
        Returns:
            Dictionary mapping symbol to StockData
        """
        results = {}
        errors = {}
        
        logger.info(f"Starting parallel batch fetch for {len(symbols)} symbols with {max_concurrent} concurrent requests")
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(symbol: str) -> Optional[StockData]:
            """Fetch data for a single symbol with semaphore control"""
            async with semaphore:
                try:
                    logger.debug(f"Fetching data for {symbol}")
                    return await self.fetch_historical_data(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        adjusted=adjusted
                    )
                except PolygonAPIError as e:
                    logger.error(f"Failed to fetch {symbol}: {e}")
                    errors[symbol] = str(e)
                    if not continue_on_error:
                        raise
                    return None
                except Exception as e:
                    logger.error(f"Unexpected error fetching {symbol}: {e}")
                    errors[symbol] = f"Unexpected error: {str(e)}"
                    if not continue_on_error:
                        raise
                    return None
        
        # Create tasks for all symbols
        tasks = [fetch_with_semaphore(symbol) for symbol in symbols]
        
        # Execute all tasks concurrently
        start_time = time.time()
        stock_data_list = await asyncio.gather(*tasks, return_exceptions=continue_on_error)
        
        # Process results
        for symbol, stock_data in zip(symbols, stock_data_list):
            if isinstance(stock_data, Exception):
                errors[symbol] = str(stock_data)
            elif stock_data is not None:
                results[symbol] = stock_data
        
        elapsed_time = time.time() - start_time
        
        if errors:
            logger.warning(f"Failed to fetch {len(errors)} symbols: {list(errors.keys())}")
        
        logger.info(f"Successfully fetched {len(results)} out of {len(symbols)} symbols in {elapsed_time:.2f} seconds")
        return results
    
    async def get_symbol_details(self, symbol: str) -> Dict[str, Any]:
        """
        Get detailed information about a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Symbol details from Polygon API
        """
        endpoint = f"/v3/reference/tickers/{symbol}"
        
        try:
            data = await self._make_request(endpoint)
            return data.get("results", {})
        except PolygonAPIError:
            raise
        except Exception as e:
            logger.error(f"Error fetching symbol details for {symbol}: {e}")
            raise PolygonAPIError(f"Error fetching symbol details: {str(e)}")
    
    async def check_market_status(self) -> Dict[str, Any]:
        """
        Check if the market is open
        
        Returns:
            Market status information
        """
        endpoint = "/v1/marketstatus/now"
        
        try:
            data = await self._make_request(endpoint)
            return data
        except PolygonAPIError:
            raise
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            raise PolygonAPIError(f"Error checking market status: {str(e)}")
    
    def clear_cache(self):
        """Clear the in-memory cache"""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Cache cleared")
    
    async def fetch_tickers(
        self,
        market: str = "stocks",
        ticker_type: Optional[str] = None,
        active: bool = True,
        limit: int = 100,
        cursor: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch list of tickers from Polygon API v3.
        
        Args:
            market: Market type (stocks, crypto, fx, otc)
            ticker_type: Ticker type (CS for common stock, ADRC for ADR, etc.)
            active: Whether to only return active tickers
            limit: Number of results per page (max 1000)
            cursor: Pagination cursor from previous response
            exchange: Filter by exchange (e.g., XNAS, XNYS)
            
        Returns:
            API response with ticker list and pagination info
        """
        endpoint = "/v3/reference/tickers"
        
        params = {
            "market": market,
            "active": str(active).lower(),
            "limit": min(limit, 1000)  # API max is 1000
        }
        
        if ticker_type:
            params["type"] = ticker_type
        
        if cursor:
            params["cursor"] = cursor
            
        if exchange:
            params["exchange"] = exchange
        
        try:
            data = await self._make_request(endpoint, params)
            return data
        except PolygonAPIError:
            raise
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            raise PolygonAPIError(f"Error fetching tickers: {str(e)}")
    
    async def fetch_bulk_daily_data(
        self,
        date_obj: date,
        adjusted: bool = True,
        include_otc: bool = False,
        streaming_callback: Optional[callable] = None
    ) -> Dict[str, StockData]:
        """
        Fetch all US stock data for a specific date using Polygon's grouped aggregates endpoint.
        This is significantly faster than individual calls as it fetches ALL stocks in one request.
        
        Args:
            date_obj: Date to fetch data for
            adjusted: Whether to adjust for splits (default: True)
            include_otc: Whether to include OTC stocks (default: False)
            streaming_callback: Optional callback function for processing data as it arrives
            
        Returns:
            Dictionary mapping symbol to StockData
            
        Raises:
            PolygonAPIError: On API errors
        """
        start_time = time.time()
        endpoint = f"/v2/aggs/grouped/locale/us/market/stocks/{self._format_date(date_obj)}"
        
        params = {
            "adjusted": str(adjusted).lower(),
            "include_otc": str(include_otc).lower()
        }
        
        try:
            logger.info(f"Fetching bulk daily data for {date_obj} (adjusted={adjusted}, include_otc={include_otc})")
            data = await self._make_request(endpoint, params)
            
            # Check if we got results
            if "results" not in data or not data["results"]:
                logger.warning(f"No bulk data found for {date_obj}")
                return {}
            
            results = {}
            results_count = len(data["results"])
            logger.info(f"Processing {results_count} stocks from bulk response with streaming optimization")
            
            # Process data in streaming fashion with batching for better performance
            batch_size = 1000  # Process in batches to maintain good performance
            processed_count = 0
            
            for i in range(0, results_count, batch_size):
                batch = data["results"][i:i + batch_size]
                batch_results = {}
                
                # Process batch
                for stock_bar in batch:
                    try:
                        symbol = stock_bar["T"]  # Ticker symbol
                        
                        # Create a single bar for this stock
                        bar = StockBar(
                            symbol=symbol,
                            date=date_obj,
                            open=stock_bar["o"],
                            high=stock_bar["h"],
                            low=stock_bar["l"],
                            close=stock_bar["c"],
                            volume=round(stock_bar["v"]),  # Round fractional volumes to nearest integer
                            vwap=stock_bar.get("vw")  # VWAP might not always be present
                        )
                        
                        # Create StockData with single bar
                        stock_data = StockData(symbol=symbol, bars=[bar])
                        batch_results[symbol] = stock_data
                        
                        # Call streaming callback if provided
                        if streaming_callback:
                            await streaming_callback(symbol, stock_data)
                        
                    except KeyError as e:
                        logger.warning(f"Missing required field {e} in bulk data for stock: {stock_bar}")
                        continue
                    except Exception as e:
                        logger.warning(f"Error processing bulk data for stock {stock_bar.get('T', 'unknown')}: {e}")
                        continue
                
                # Add batch results to main results
                results.update(batch_results)
                processed_count += len(batch_results)
                
                # Log progress for large datasets
                if results_count > 1000 and i % (batch_size * 5) == 0:
                    logger.debug(f"Processed {processed_count}/{results_count} stocks ({(processed_count/results_count)*100:.1f}%)")
            
            elapsed_time = time.time() - start_time
            logger.info(f"Successfully processed {len(results)} stocks from bulk endpoint in {elapsed_time:.2f} seconds")
            
            return results
            
        except PolygonAPIError:
            # Re-raise Polygon errors
            raise
        except Exception as e:
            logger.error(f"Error fetching bulk daily data for {date_obj}: {e}")
            raise PolygonAPIError(f"Error fetching bulk daily data: {str(e)}")
    
    async def fetch_bulk_historical_data_with_fallback(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        adjusted: bool = True,
        prefer_bulk: bool = True,
        max_concurrent: int = 200
    ) -> Dict[str, StockData]:
        """
        Fetch historical data using bulk endpoint when possible, with fallback to individual calls.
        
        For single-day requests, uses the bulk grouped aggregates endpoint which is much faster.
        For multi-day requests, falls back to individual calls or uses bulk for each day.
        
        Args:
            symbols: List of stock symbols (used for filtering bulk results)
            start_date: Start date for data
            end_date: End date for data
            adjusted: Whether to adjust for splits (default: True)
            prefer_bulk: Whether to prefer bulk endpoint for single-day requests (default: True)
            max_concurrent: Maximum concurrent requests for individual calls (default: 200)
            
        Returns:
            Dictionary mapping symbol to StockData
        """
        start_time = time.time()
        logger.info(f"Fetching data for {len(symbols)} symbols from {start_date} to {end_date}")
        
        # Convert symbols to set for faster lookup
        symbol_set = set(symbols) if symbols else None
        
        # If single day and prefer_bulk is True, use bulk endpoint
        if start_date == end_date and prefer_bulk:
            try:
                logger.info(f"Using bulk endpoint for single day: {start_date}")
                bulk_results = await self.fetch_bulk_daily_data(start_date, adjusted=adjusted)
                
                # Filter results to only requested symbols if specified
                if symbol_set:
                    filtered_results = {
                        symbol: data for symbol, data in bulk_results.items() 
                        if symbol in symbol_set
                    }
                    logger.info(f"Filtered bulk results: {len(filtered_results)} out of {len(bulk_results)} stocks")
                    return filtered_results
                else:
                    return bulk_results
                    
            except PolygonAPIError as e:
                logger.warning(f"Bulk endpoint failed: {e}. Falling back to individual calls.")
                # Fall through to individual calls
            except Exception as e:
                logger.warning(f"Unexpected error with bulk endpoint: {e}. Falling back to individual calls.")
                # Fall through to individual calls
        
        # For multi-day requests or when bulk fails, use individual calls
        logger.info(f"Using individual calls for {len(symbols)} symbols")
        results = await self.fetch_batch_historical_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            adjusted=adjusted,
            max_concurrent=max_concurrent
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Completed data fetch in {elapsed_time:.2f} seconds using {'individual' if start_date != end_date or not prefer_bulk else 'fallback'} method")
        
        return results
    
    async def fetch_previous_day_close(self, symbol: str, target_date: date) -> Optional[float]:
        """
        Fetch the previous trading day close price for a single symbol.
        
        This method attempts to find the most recent trading day before the target date
        and returns the close price for that day.
        
        Args:
            symbol: Stock symbol
            target_date: Date to get previous trading day close for
            
        Returns:
            Previous day close price or None if not available
        """
        # Start looking from the day before target_date
        current_date = target_date - timedelta(days=1)
        max_lookback = 10  # Look back up to 10 days
        
        for _ in range(max_lookback):
            # Skip weekends (Saturday = 5, Sunday = 6)
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                try:
                    stock_data = await self.fetch_historical_data(
                        symbol=symbol,
                        start_date=current_date,
                        end_date=current_date,
                        adjusted=True
                    )
                    
                    if stock_data.bars:
                        return stock_data.bars[0].close
                        
                except PolygonAPIError:
                    # If this specific date failed, try the next day back
                    pass
            
            current_date -= timedelta(days=1)
        
        logger.warning(f"Could not find previous trading day close for {symbol} before {target_date}")
        return None
    
    async def fetch_previous_day_closes_bulk(
        self, 
        symbols: List[str], 
        target_date: date,
        use_bulk_endpoint: bool = True
    ) -> Dict[str, Optional[float]]:
        """
        Fetch previous trading day close prices for multiple symbols efficiently.
        
        Args:
            symbols: List of stock symbols
            target_date: Date to get previous trading day closes for
            use_bulk_endpoint: Whether to use bulk endpoint for efficiency (default: True)
            
        Returns:
            Dictionary mapping symbol to previous day close price (None if not available)
        """
        # Find the most likely previous trading day
        current_date = target_date - timedelta(days=1)
        max_lookback = 10
        
        for _ in range(max_lookback):
            # Skip weekends
            if current_date.weekday() < 5:
                try:
                    if use_bulk_endpoint:
                        # Try bulk endpoint first
                        bulk_data = await self.fetch_bulk_daily_data(current_date, adjusted=True)
                        
                        # Extract close prices for requested symbols
                        results = {}
                        for symbol in symbols:
                            if symbol in bulk_data and bulk_data[symbol].bars:
                                results[symbol] = bulk_data[symbol].bars[0].close
                            else:
                                results[symbol] = None
                        
                        # If we got data for any symbols, return results
                        if any(price is not None for price in results.values()):
                            return results
                    else:
                        # Use individual calls
                        batch_data = await self.fetch_batch_historical_data(
                            symbols=symbols,
                            start_date=current_date,
                            end_date=current_date,
                            adjusted=True
                        )
                        
                        results = {}
                        for symbol in symbols:
                            if symbol in batch_data and batch_data[symbol].bars:
                                results[symbol] = batch_data[symbol].bars[0].close
                            else:
                                results[symbol] = None
                        
                        # If we got data for any symbols, return results
                        if any(price is not None for price in results.values()):
                            return results
                            
                except PolygonAPIError:
                    # If this date failed, try the next day back
                    pass
                except Exception as e:
                    logger.warning(f"Error fetching bulk previous day data for {current_date}: {e}")
            
            current_date -= timedelta(days=1)
        
        # If we couldn't find any data, return None for all symbols
        logger.warning(f"Could not find previous trading day data for {len(symbols)} symbols before {target_date}")
        return {symbol: None for symbol in symbols}
    
    async def fetch_historical_data_with_extension(
        self,
        symbols: List[str],
        original_start_date: date,
        original_end_date: date,
        filter_requirements: List,  # List of FilterRequirement objects
        adjusted: bool = True,
        max_concurrent: int = 200,
        prefer_bulk: bool = True
    ) -> Tuple[Dict[str, StockData], Dict[str, Any]]:
        """
        Fetch historical data with automatic period extension for filter requirements.
        
        This method automatically extends the data range to satisfy filter requirements,
        then trims the results back to the requested date range after filtering.
        
        Args:
            symbols: List of stock symbols
            original_start_date: Original requested start date
            original_end_date: Original requested end date
            filter_requirements: List of FilterRequirement objects from analyzer
            adjusted: Whether to adjust for splits (default: True)
            max_concurrent: Maximum concurrent requests (default: 200)
            prefer_bulk: Whether to prefer bulk endpoint (default: True)
            
        Returns:
            Tuple of (extended_stock_data_dict, extension_metadata)
        """
        from ..core.filter_analyzer import FilterRequirementAnalyzer
        
        start_time = time.time()
        
        # Calculate extended start date
        analyzer = FilterRequirementAnalyzer()
        if filter_requirements:
            max_lookback = max(req.lookback_days for req in filter_requirements)
            total_extension_days = max_lookback + analyzer.business_days_buffer
            extended_start_date = original_start_date - timedelta(days=total_extension_days)
        else:
            extended_start_date = original_start_date
            total_extension_days = 0
        
        logger.info(f"Fetching data with period extension: original range {original_start_date} to {original_end_date}, "
                   f"extended range {extended_start_date} to {original_end_date} (+{total_extension_days} days)")
        
        # Fetch extended data using existing optimized methods
        extended_data = await self.fetch_bulk_historical_data_with_fallback(
            symbols=symbols,
            start_date=extended_start_date,
            end_date=original_end_date,  # End date remains the same
            adjusted=adjusted,
            prefer_bulk=prefer_bulk,
            max_concurrent=max_concurrent
        )
        
        # Generate extension metadata
        extension_metadata = analyzer.get_extension_metadata(
            requirements=filter_requirements,
            original_start=original_start_date,
            extended_start=extended_start_date
        )
        
        elapsed_time = time.time() - start_time
        extension_metadata.update({
            "fetch_time_seconds": elapsed_time,
            "symbols_fetched": len(extended_data),
            "total_symbols_requested": len(symbols),
            "bulk_endpoint_used": prefer_bulk and original_start_date == original_end_date,
            "data_range_extended": total_extension_days > 0
        })
        
        logger.info(f"Completed extended data fetch in {elapsed_time:.2f} seconds: "
                   f"{len(extended_data)}/{len(symbols)} symbols, "
                   f"extension: +{total_extension_days} days")
        
        return extended_data, extension_metadata
    
    def slice_data_to_original_range(
        self,
        extended_data: Dict[str, StockData],
        original_start_date: date,
        original_end_date: date
    ) -> Dict[str, StockData]:
        """
        Slice extended stock data back to the original requested date range.
        
        This method is used after filtering to return only the data within
        the originally requested date range.
        
        Args:
            extended_data: Dictionary of extended stock data
            original_start_date: Original requested start date
            original_end_date: Original requested end date
            
        Returns:
            Dictionary of stock data sliced to original range
        """
        sliced_data = {}
        
        for symbol, stock_data in extended_data.items():
            # Filter bars to original date range
            sliced_bars = [
                bar for bar in stock_data.bars
                if original_start_date <= bar.date <= original_end_date
            ]
            
            # Create new StockData with sliced bars
            sliced_data[symbol] = StockData(symbol=symbol, bars=sliced_bars)
        
        # Log slicing results
        original_total_bars = sum(len(data.bars) for data in extended_data.values())
        sliced_total_bars = sum(len(data.bars) for data in sliced_data.values())
        
        logger.debug(f"Sliced data from {original_total_bars} to {sliced_total_bars} bars "
                    f"({len(sliced_data)} symbols) for range {original_start_date} to {original_end_date}")
        
        return sliced_data


# Example usage and testing
async def example_usage():
    """Example of how to use the PolygonClient"""
    
    # Using context manager for automatic cleanup
    async with PolygonClient() as client:
        # Check market status
        market_status = await client.check_market_status()
        print(f"Market status: {market_status}")
        
        # Fetch data for a single symbol
        from datetime import timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        stock_data = await client.fetch_historical_data(
            symbol="AAPL",
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"Fetched {len(stock_data.bars)} bars for {stock_data.symbol}")
        
        # Convert to numpy for processing
        np_data = stock_data.to_numpy()
        print(f"Numpy array shape: {np_data.shape}")
        
        # Batch fetch multiple symbols
        symbols = ["AAPL", "MSFT", "GOOGL"]
        batch_data = await client.fetch_batch_historical_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )
        
        for symbol, data in batch_data.items():
            print(f"{symbol}: {len(data.bars)} bars")


if __name__ == "__main__":
    # For testing purposes
    asyncio.run(example_usage())