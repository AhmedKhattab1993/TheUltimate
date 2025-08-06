"""
High-performance screener engine for filtering stocks using vectorized operations.

This module provides the main ScreenerEngine class that processes multiple stocks
through various filters efficiently using numpy vectorization.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import asyncio
from datetime import datetime, date

from ..core.filters import BaseFilter, FilterResult, CompositeFilter
from ..core.day_trading_filters import GapFilter
from ..core.filter_analyzer import FilterRequirementAnalyzer
from ..models.stock import StockData
from .previous_trading_day_service import PreviousTradingDayService
from .polygon_client import PolygonClient


logger = logging.getLogger(__name__)


class ScreenerResult:
    """Container for screener results across multiple stocks."""
    
    def __init__(self):
        self.results: Dict[str, FilterResult] = {}
        self.processing_errors: Dict[str, str] = {}
        self.processing_time: float = 0.0
        
    def add_result(self, symbol: str, result: FilterResult):
        """Add a filter result for a symbol."""
        self.results[symbol] = result
        
    def add_error(self, symbol: str, error: str):
        """Record an error for a symbol."""
        self.processing_errors[symbol] = error
        
    @property
    def qualifying_symbols(self) -> List[str]:
        """Get list of symbols that have at least one qualifying date."""
        return [symbol for symbol, result in self.results.items() 
                if result.num_qualifying_days > 0]
    
    @property
    def num_processed(self) -> int:
        """Get total number of symbols processed."""
        return len(self.results) + len(self.processing_errors)
    
    @property
    def num_errors(self) -> int:
        """Get number of processing errors."""
        return len(self.processing_errors)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of the screening results."""
        if not self.results:
            return {
                'total_processed': 0,
                'qualifying_symbols': 0,
                'errors': self.num_errors,
                'processing_time_ms': self.processing_time * 1000
            }
        
        # Calculate aggregate statistics
        total_qualifying_days = sum(r.num_qualifying_days for r in self.results.values())
        avg_qualifying_days = total_qualifying_days / len(self.results) if self.results else 0
        
        return {
            'total_processed': self.num_processed,
            'qualifying_symbols': len(self.qualifying_symbols),
            'errors': self.num_errors,
            'processing_time_ms': self.processing_time * 1000,
            'avg_qualifying_days_per_symbol': avg_qualifying_days,
            'total_qualifying_days': total_qualifying_days
        }


class ScreenerEngine:
    """
    High-performance engine for screening stocks using vectorized filters.
    
    This engine processes multiple stocks through a series of filters,
    leveraging numpy vectorization for maximum performance. Enhanced version
    supports async operations for gap calculations with missing previous day data.
    """
    
    def __init__(self, max_workers: int = 4, polygon_client: Optional[PolygonClient] = None,
                 enable_async_gap_calculation: bool = False):
        """
        Initialize the screener engine.
        
        Args:
            max_workers: Maximum number of parallel workers for processing stocks
            polygon_client: Optional PolygonClient for fetching missing data
            enable_async_gap_calculation: Whether to enable async gap calculation for missing data
        """
        self.max_workers = max_workers
        self.polygon_client = polygon_client
        self.enable_async_gap_calculation = enable_async_gap_calculation
        self._previous_day_service: Optional[PreviousTradingDayService] = None
        
    def screen(self, 
               stock_data_list: List[StockData], 
               filters: List[BaseFilter],
               date_range: Optional[Tuple[date, date]] = None) -> ScreenerResult:
        """
        Screen multiple stocks through the provided filters.
        
        Args:
            stock_data_list: List of StockData objects to screen
            filters: List of filters to apply (combined with AND logic)
            date_range: Optional tuple of (start_date, end_date) to limit screening
            
        Returns:
            ScreenerResult containing filtered results and metrics
        """
        start_time = datetime.now()
        result = ScreenerResult()
        
        if not stock_data_list:
            logger.warning("No stock data provided for screening")
            result.processing_time = (datetime.now() - start_time).total_seconds()
            return result
        
        if not filters:
            logger.warning("No filters provided for screening")
            result.processing_time = (datetime.now() - start_time).total_seconds()
            return result
        
        # Create composite filter if multiple filters provided
        if len(filters) == 1:
            filter_to_apply = filters[0]
        else:
            filter_to_apply = CompositeFilter(filters)
        
        # Process stocks in parallel for better performance
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tasks
            future_to_symbol = {}
            for stock_data in stock_data_list:
                future = executor.submit(
                    self._process_single_stock,
                    stock_data,
                    filter_to_apply,
                    date_range
                )
                future_to_symbol[future] = stock_data.symbol
            
            # Collect results
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    filter_result = future.result()
                    if filter_result:
                        result.add_result(symbol, filter_result)
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {str(e)}")
                    result.add_error(symbol, str(e))
        
        result.processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Screener completed: {result.get_summary()}")
        
        return result
    
    def _process_single_stock(self,
                            stock_data: StockData,
                            filter: BaseFilter,
                            date_range: Optional[Tuple[date, date]]) -> Optional[FilterResult]:
        """
        Process a single stock through the filter.
        
        Args:
            stock_data: Stock data to process
            filter: Filter to apply
            date_range: Optional date range to limit data
            
        Returns:
            FilterResult or None if no data after filtering
        """
        try:
            # Convert to numpy array for efficient processing
            data = stock_data.to_numpy()
            
            if len(data) == 0:
                logger.warning(f"No data for {stock_data.symbol}")
                return None
            
            # Apply date range filter if specified
            if date_range:
                start_date, end_date = date_range
                # Convert dates to numpy datetime64 for comparison
                start_dt64 = np.datetime64(start_date)
                end_dt64 = np.datetime64(end_date)
                
                date_mask = (data['date'] >= start_dt64) & (data['date'] <= end_dt64)
                data = data[date_mask]
                
                if len(data) == 0:
                    logger.debug(f"No data for {stock_data.symbol} in date range")
                    return None
            
            # Apply filter
            return filter.apply(data, stock_data.symbol)
            
        except Exception as e:
            logger.error(f"Error processing {stock_data.symbol}: {str(e)}")
            raise
    
    def screen_with_metrics(self,
                          stock_data_list: List[StockData],
                          filters: List[BaseFilter],
                          metric_aggregations: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Screen stocks and return aggregated metrics for qualifying symbols.
        
        Args:
            stock_data_list: List of StockData objects to screen
            filters: List of filters to apply
            metric_aggregations: Dict mapping metric names to aggregation functions
                                ('mean', 'sum', 'min', 'max', 'std')
                                
        Returns:
            Dict containing screening results and aggregated metrics
        """
        # Default aggregations if not specified
        if metric_aggregations is None:
            metric_aggregations = {
                'avg_volume_*_mean': 'mean',
                'price_change_mean': 'mean',
                'distance_from_sma_*_mean': 'mean'
            }
        
        # Run screening
        screen_result = self.screen(stock_data_list, filters)
        
        # Prepare output
        output = {
            'summary': screen_result.get_summary(),
            'qualifying_symbols': [],
            'aggregated_metrics': {}
        }
        
        # Process qualifying symbols
        for symbol in screen_result.qualifying_symbols:
            result = screen_result.results[symbol]
            symbol_info = {
                'symbol': symbol,
                'qualifying_days': result.num_qualifying_days,
                'first_qualifying_date': str(result.qualifying_dates[0]) if result.num_qualifying_days > 0 else None,
                'last_qualifying_date': str(result.qualifying_dates[-1]) if result.num_qualifying_days > 0 else None,
                'metrics': result.metrics
            }
            output['qualifying_symbols'].append(symbol_info)
        
        # Aggregate metrics across all qualifying symbols
        if screen_result.qualifying_symbols:
            all_metrics = {}
            for symbol in screen_result.qualifying_symbols:
                for metric_name, value in screen_result.results[symbol].metrics.items():
                    if metric_name not in all_metrics:
                        all_metrics[metric_name] = []
                    all_metrics[metric_name].append(value)
            
            # Apply aggregations
            for pattern, agg_func in metric_aggregations.items():
                for metric_name, values in all_metrics.items():
                    # Check if metric matches pattern (support wildcards)
                    if self._matches_pattern(metric_name, pattern):
                        values_array = np.array(values)
                        if agg_func == 'mean':
                            output['aggregated_metrics'][f'{metric_name}_{agg_func}'] = float(np.mean(values_array))
                        elif agg_func == 'sum':
                            output['aggregated_metrics'][f'{metric_name}_{agg_func}'] = float(np.sum(values_array))
                        elif agg_func == 'min':
                            output['aggregated_metrics'][f'{metric_name}_{agg_func}'] = float(np.min(values_array))
                        elif agg_func == 'max':
                            output['aggregated_metrics'][f'{metric_name}_{agg_func}'] = float(np.max(values_array))
                        elif agg_func == 'std':
                            output['aggregated_metrics'][f'{metric_name}_{agg_func}'] = float(np.std(values_array))
        
        return output
    
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """Check if text matches pattern (supports * wildcard)."""
        if '*' not in pattern:
            return text == pattern
        
        # Simple wildcard matching
        parts = pattern.split('*')
        if len(parts) == 2:
            # Pattern like "prefix*" or "*suffix" or "prefix*suffix"
            if parts[0] and not text.startswith(parts[0]):
                return False
            if parts[1] and not text.endswith(parts[1]):
                return False
            return True
        
        return text == pattern  # Fallback for complex patterns
    
    async def screen_async(self, 
                          stock_data_list: List[StockData], 
                          filters: List[BaseFilter],
                          date_range: Optional[Tuple[date, date]] = None) -> ScreenerResult:
        """
        Screen multiple stocks through the provided filters with async support.
        
        This method supports async processing for gap calculations when single-day
        data is provided and previous day data needs to be fetched.
        
        Args:
            stock_data_list: List of StockData objects to screen
            filters: List of filters to apply (combined with AND logic)
            date_range: Optional tuple of (start_date, end_date) to limit screening
            
        Returns:
            ScreenerResult containing filtered results and metrics
        """
        start_time = datetime.now()
        result = ScreenerResult()
        
        if not stock_data_list:
            logger.warning("No stock data provided for screening")
            result.processing_time = (datetime.now() - start_time).total_seconds()
            return result
        
        if not filters:
            logger.warning("No filters provided for screening")
            result.processing_time = (datetime.now() - start_time).total_seconds()
            return result
        
        # Setup async gap calculation if needed
        gap_filters = [f for f in filters if isinstance(f, GapFilter)]
        if gap_filters and self.enable_async_gap_calculation:
            await self._setup_async_gap_filters(gap_filters)
        
        # Create composite filter if multiple filters provided
        if len(filters) == 1:
            filter_to_apply = filters[0]
        else:
            filter_to_apply = CompositeFilter(filters)
        
        # Check if we need async processing
        needs_async = self._check_if_async_needed(stock_data_list, gap_filters, date_range)
        
        if needs_async:
            # Use async processing
            logger.info(f"Using async processing for {len(stock_data_list)} stocks")
            await self._process_stocks_async(stock_data_list, filter_to_apply, date_range, result)
        else:
            # Use synchronous processing (existing logic)
            logger.info(f"Using synchronous processing for {len(stock_data_list)} stocks")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit tasks
                future_to_symbol = {}
                for stock_data in stock_data_list:
                    future = executor.submit(
                        self._process_single_stock,
                        stock_data,
                        filter_to_apply,
                        date_range
                    )
                    future_to_symbol[future] = stock_data.symbol
                
                # Collect results
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        filter_result = future.result()
                        if filter_result:
                            result.add_result(symbol, filter_result)
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {str(e)}")
                        result.add_error(symbol, str(e))
        
        result.processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Async screener completed: {result.get_summary()}")
        
        return result
    
    async def _setup_async_gap_filters(self, gap_filters: List[GapFilter]):
        """Setup gap filters for async processing."""
        if not self._previous_day_service:
            if not self.polygon_client:
                self.polygon_client = PolygonClient()
            self._previous_day_service = PreviousTradingDayService(self.polygon_client)
        
        # Configure gap filters with async fetcher
        for gap_filter in gap_filters:
            gap_filter.previous_day_fetcher = self._previous_day_service.get_previous_day_close
            gap_filter.enable_async_fetch = True
    
    def _check_if_async_needed(self, stock_data_list: List[StockData], 
                              gap_filters: List[GapFilter], 
                              date_range: Optional[Tuple[date, date]]) -> bool:
        """Check if async processing is needed."""
        if not gap_filters or not self.enable_async_gap_calculation:
            return False
        
        # Check if any stock has single-day data (which would need async processing for gaps)
        for stock_data in stock_data_list:
            data_length = len(stock_data.bars)
            
            # Apply date range filter if specified to determine effective length
            if date_range and data_length > 0:
                start_date, end_date = date_range
                relevant_bars = [
                    bar for bar in stock_data.bars 
                    if start_date <= bar.date <= end_date
                ]
                data_length = len(relevant_bars)
            
            if data_length == 1:
                return True  # Single-day data needs async processing for gaps
        
        return False
    
    async def _process_stocks_async(self, stock_data_list: List[StockData], 
                                   filter: BaseFilter, 
                                   date_range: Optional[Tuple[date, date]],
                                   result: ScreenerResult):
        """Process stocks asynchronously."""
        # Create semaphore to limit concurrent async operations
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def process_single_stock_async(stock_data: StockData):
            async with semaphore:
                try:
                    filter_result = await self._process_single_stock_async(
                        stock_data, filter, date_range
                    )
                    if filter_result:
                        result.add_result(stock_data.symbol, filter_result)
                except Exception as e:
                    logger.error(f"Error processing {stock_data.symbol}: {str(e)}")
                    result.add_error(stock_data.symbol, str(e))
        
        # Create tasks for all stocks
        tasks = [process_single_stock_async(stock_data) for stock_data in stock_data_list]
        
        # Execute all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_single_stock_async(self, stock_data: StockData,
                                         filter: BaseFilter,
                                         date_range: Optional[Tuple[date, date]]) -> Optional[FilterResult]:
        """Process a single stock through the filter asynchronously."""
        try:
            # Convert to numpy array for efficient processing
            data = stock_data.to_numpy()
            
            if len(data) == 0:
                logger.warning(f"No data for {stock_data.symbol}")
                return None
            
            # Apply date range filter if specified
            if date_range:
                start_date, end_date = date_range
                # Convert dates to numpy datetime64 for comparison
                start_dt64 = np.datetime64(start_date)
                end_dt64 = np.datetime64(end_date)
                
                date_mask = (data['date'] >= start_dt64) & (data['date'] <= end_dt64)
                data = data[date_mask]
                
                if len(data) == 0:
                    logger.debug(f"No data for {stock_data.symbol} in date range")
                    return None
            
            # Check if filter has async processing capability
            if hasattr(filter, 'apply_async') and isinstance(filter, GapFilter):
                return await filter.apply_async(data, stock_data.symbol)
            elif hasattr(filter, 'filters'):  # CompositeFilter
                # Handle composite filters with potential async components
                return await self._apply_composite_filter_async(filter, data, stock_data.symbol)
            else:
                # Regular synchronous filter
                return filter.apply(data, stock_data.symbol)
                
        except Exception as e:
            logger.error(f"Error processing {stock_data.symbol}: {str(e)}")
            raise
    
    async def _apply_composite_filter_async(self, composite_filter: CompositeFilter,
                                           data: np.ndarray, symbol: str) -> FilterResult:
        """Apply composite filter with async support for individual filters."""
        if not composite_filter.filters:
            return FilterResult(
                symbol=symbol,
                qualifying_mask=np.ones(len(data), dtype=bool),
                dates=data['date'],
                metrics={}
            )
        
        # Process first filter
        first_filter = composite_filter.filters[0]
        if hasattr(first_filter, 'apply_async') and isinstance(first_filter, GapFilter):
            result = await first_filter.apply_async(data, symbol)
        else:
            result = first_filter.apply(data, symbol)
        
        # Combine with remaining filters
        for filter in composite_filter.filters[1:]:
            if hasattr(filter, 'apply_async') and isinstance(filter, GapFilter):
                filter_result = await filter.apply_async(data, symbol)
            else:
                filter_result = filter.apply(data, symbol)
            result = result.combine_with(filter_result)
        
        return result
    
    async def screen_with_period_extension(self,
                                         symbols: List[str],
                                         filters: List[BaseFilter],
                                         start_date: date,
                                         end_date: date,
                                         polygon_client: Optional[PolygonClient] = None,
                                         auto_slice_results: bool = True,
                                         adjusted: bool = True,
                                         max_concurrent: int = 200,
                                         prefer_bulk: bool = True) -> Tuple[ScreenerResult, Dict[str, Any]]:
        """
        Screen stocks with automatic period extension for filters requiring historical data.
        
        This method automatically detects filter requirements, extends the data fetch period,
        applies filters, and optionally slices results back to the original date range.
        
        Args:
            symbols: List of stock symbols to screen
            filters: List of filters to apply
            start_date: Original start date for screening
            end_date: Original end date for screening
            polygon_client: Optional PolygonClient instance (creates one if None)
            auto_slice_results: Whether to slice results back to original date range (default: True)
            adjusted: Whether to use adjusted prices (default: True)
            max_concurrent: Maximum concurrent requests (default: 200)
            prefer_bulk: Whether to prefer bulk endpoint for single-day requests (default: True)
            
        Returns:
            Tuple of (ScreenerResult, extension_metadata)
        """
        start_time = datetime.now()
        
        # Initialize polygon client if not provided
        if polygon_client is None:
            polygon_client = self.polygon_client or PolygonClient()
        
        # Analyze filter requirements
        analyzer = FilterRequirementAnalyzer()
        
        # Check if extension is needed
        if not analyzer.needs_extension(filters):
            logger.info("No period extension needed for provided filters")
            # Use regular screening without extension
            stock_data_list = []
            
            # Fetch data normally
            stock_data_dict = await polygon_client.fetch_bulk_historical_data_with_fallback(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                adjusted=adjusted,
                prefer_bulk=prefer_bulk,
                max_concurrent=max_concurrent
            )
            
            # Convert to list format expected by screener
            stock_data_list = list(stock_data_dict.values())
            
            # Run regular screening
            screen_result = self.screen(stock_data_list, filters, (start_date, end_date))
            
            # Create minimal metadata
            extension_metadata = {
                "period_extension_applied": False,
                "original_start_date": start_date.isoformat(),
                "original_end_date": end_date.isoformat(),
                "filter_summary": analyzer.get_filter_summary(filters)
            }
            
            return screen_result, extension_metadata
        
        # Calculate extension requirements
        requirements = analyzer.analyze_filters(filters)
        extended_start_date, _ = analyzer.calculate_required_start_date(filters, start_date, end_date)
        
        logger.info(f"Period extension required: {len(requirements)} filters need historical data. "
                   f"Extending from {start_date} to {extended_start_date}")
        
        # Fetch extended data using PolygonClient's extension method
        extended_data_dict, extension_metadata = await polygon_client.fetch_historical_data_with_extension(
            symbols=symbols,
            original_start_date=start_date,
            original_end_date=end_date,
            filter_requirements=requirements,
            adjusted=adjusted,
            max_concurrent=max_concurrent,
            prefer_bulk=prefer_bulk
        )
        
        # Convert to list format for screening
        extended_stock_data_list = list(extended_data_dict.values())
        
        if not extended_stock_data_list:
            logger.warning("No extended stock data available for screening")
            result = ScreenerResult()
            result.processing_time = (datetime.now() - start_time).total_seconds()
            return result, extension_metadata
        
        # Apply filters to extended data (no date range restriction during filtering)
        logger.info(f"Applying filters to {len(extended_stock_data_list)} stocks with extended data")
        screen_result = self.screen(extended_stock_data_list, filters, date_range=None)
        
        # Optionally slice results back to original date range
        if auto_slice_results:
            logger.info(f"Slicing filter results back to original date range: {start_date} to {end_date}")
            sliced_results = {}
            
            for symbol, filter_result in screen_result.results.items():
                # Create date mask for original range
                original_start_dt64 = np.datetime64(start_date)
                original_end_dt64 = np.datetime64(end_date)
                
                date_mask = ((filter_result.dates >= original_start_dt64) & 
                           (filter_result.dates <= original_end_dt64))
                
                # Apply mask to qualifying_mask and dates
                sliced_qualifying_mask = filter_result.qualifying_mask[date_mask]
                sliced_dates = filter_result.dates[date_mask]
                
                # Create new FilterResult with sliced data
                sliced_filter_result = FilterResult(
                    symbol=symbol,
                    qualifying_mask=sliced_qualifying_mask,
                    dates=sliced_dates,
                    metrics=filter_result.metrics  # Keep original metrics
                )
                
                sliced_results[symbol] = sliced_filter_result
            
            # Update screen_result with sliced results
            screen_result.results = sliced_results
            
            # Update metadata
            extension_metadata["results_sliced_to_original_range"] = True
            extension_metadata["original_date_range"] = {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        else:
            extension_metadata["results_sliced_to_original_range"] = False
        
        # Add screening metadata
        screen_result.processing_time = (datetime.now() - start_time).total_seconds()
        extension_metadata["total_screening_time_seconds"] = screen_result.processing_time
        extension_metadata["filter_summary"] = analyzer.get_filter_summary(filters)
        
        logger.info(f"Period extension screening completed in {screen_result.processing_time:.2f} seconds: "
                   f"{len(screen_result.qualifying_symbols)} qualifying symbols out of {len(symbols)} processed")
        
        return screen_result, extension_metadata
    
    def screen_single_date_with_extension(self,
                                        symbols: List[str],
                                        filters: List[BaseFilter],
                                        target_date: date,
                                        polygon_client: Optional[PolygonClient] = None,
                                        **kwargs) -> Tuple[ScreenerResult, Dict[str, Any]]:
        """
        Convenience method for screening a single date with automatic period extension.
        
        This is a synchronous wrapper around screen_with_period_extension for single-date screening.
        
        Args:
            symbols: List of stock symbols to screen
            filters: List of filters to apply
            target_date: Single date to screen
            polygon_client: Optional PolygonClient instance
            **kwargs: Additional kwargs passed to screen_with_period_extension
            
        Returns:
            Tuple of (ScreenerResult, extension_metadata)
        """
        return asyncio.run(self.screen_with_period_extension(
            symbols=symbols,
            filters=filters,
            start_date=target_date,
            end_date=target_date,
            polygon_client=polygon_client,
            **kwargs
        ))