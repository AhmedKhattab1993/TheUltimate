"""
Ticker discovery service for fetching available US common stocks.

This module provides functionality to discover available ticker symbols
from the Polygon API, specifically focusing on US common stocks.
"""

import logging
from typing import List, Optional, Set
from datetime import datetime

from app.services.polygon_client import PolygonClient, PolygonAPIError

logger = logging.getLogger(__name__)


class TickerDiscoveryService:
    """Service for discovering available ticker symbols from Polygon API."""
    
    def __init__(self, polygon_client: PolygonClient):
        """
        Initialize ticker discovery service.
        
        Args:
            polygon_client: Instance of PolygonClient for API access
        """
        self.polygon_client = polygon_client
    
    async def fetch_all_us_common_stocks(self) -> List[str]:
        """
        Fetch all active US common stock tickers from Polygon API.
        
        Returns:
            List of ticker symbols for US common stocks
            
        Raises:
            PolygonAPIError: On API errors
        """
        # Fetch common stocks only (for backward compatibility)
        return await self.fetch_us_equities(include_types=['CS'])
    
    async def fetch_us_equities(self, include_types: List[str] = None) -> List[str]:
        """
        Fetch active US equity tickers from Polygon API.
        
        Args:
            include_types: List of ticker types to include. 
                          Defaults to ['CS', 'ETF'] if not specified.
                          Valid types: 'CS' (Common Stock), 'ETF' (Exchange Traded Fund),
                          'ADRC' (ADR Common Stock), 'ADRP' (ADR Preferred), etc.
        
        Returns:
            List of ticker symbols for specified equity types
            
        Raises:
            PolygonAPIError: On API errors
        """
        if include_types is None:
            include_types = ['CS', 'ETF']
        
        all_tickers = []
        
        logger.info(f"Starting to fetch US equity tickers for types: {include_types}")
        
        try:
            # Fetch tickers for each type separately (API limitation)
            for ticker_type in include_types:
                logger.info(f"Fetching {ticker_type} tickers...")
                type_tickers = await self._fetch_tickers_by_type(ticker_type)
                all_tickers.extend(type_tickers)
                logger.info(f"Found {len(type_tickers)} {ticker_type} tickers")
            
            # Remove duplicates and sort
            unique_tickers = sorted(list(set(all_tickers)))
            
            logger.info(f"Successfully fetched {len(unique_tickers)} unique US equity tickers")
            return unique_tickers
            
        except PolygonAPIError as e:
            logger.error(f"Polygon API error while fetching tickers: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching tickers: {e}")
            raise PolygonAPIError(f"Error fetching tickers: {str(e)}")
    
    async def _fetch_tickers_by_type(self, ticker_type: str) -> List[str]:
        """
        Fetch all tickers for a specific type.
        
        Args:
            ticker_type: Type of ticker to fetch (e.g., 'CS', 'ETF')
            
        Returns:
            List of ticker symbols
        """
        all_tickers = []
        cursor = None
        page_count = 0
        
        try:
            while True:
                page_count += 1
                logger.debug(f"Fetching page {page_count} of {ticker_type} tickers")
                
                # Fetch a page of tickers
                tickers_data = await self._fetch_tickers_page(cursor, ticker_type)
                
                # Extract ticker symbols from results
                if "results" in tickers_data and tickers_data["results"]:
                    page_tickers = [
                        ticker["ticker"] 
                        for ticker in tickers_data["results"]
                        if ticker.get("ticker")
                    ]
                    all_tickers.extend(page_tickers)
                    logger.debug(f"Found {len(page_tickers)} tickers on page {page_count}")
                
                # Check if there are more pages
                if "next_url" in tickers_data and tickers_data["next_url"]:
                    cursor = tickers_data["next_url"]
                else:
                    # No more pages
                    break
            
            return all_tickers
            
        except Exception as e:
            logger.error(f"Error fetching {ticker_type} tickers: {e}")
            raise
    
    async def _fetch_tickers_page(self, cursor: Optional[str] = None, ticker_type: str = "CS") -> dict:
        """
        Fetch a single page of tickers from Polygon API.
        
        Args:
            cursor: Pagination cursor for next page
            ticker_type: Type of ticker to fetch (default: "CS")
            
        Returns:
            API response data
        """
        if cursor:
            # If we have a cursor URL, extract the cursor parameter
            # The cursor is typically the full next_url, so we'll use it directly
            # The Polygon client will handle building the URL
            import urllib.parse
            parsed = urllib.parse.urlparse(cursor)
            params = urllib.parse.parse_qs(parsed.query)
            cursor_value = params.get('cursor', [None])[0]
            
            return await self.polygon_client.fetch_tickers(
                market="stocks",
                ticker_type=ticker_type,
                active=True,
                limit=1000,
                cursor=cursor_value
            )
        else:
            # First page
            return await self.polygon_client.fetch_tickers(
                market="stocks",
                ticker_type=ticker_type,
                active=True,
                limit=1000
            )
    
    async def filter_tickers_by_criteria(
        self,
        tickers: List[str],
        min_market_cap: Optional[float] = None,
        min_average_volume: Optional[float] = None,
        exchanges: Optional[List[str]] = None
    ) -> List[str]:
        """
        Filter tickers by additional criteria (market cap, volume, exchange).
        
        This is a placeholder for future enhancement. Currently returns
        the input list unchanged.
        
        Args:
            tickers: List of ticker symbols to filter
            min_market_cap: Minimum market cap filter
            min_average_volume: Minimum average volume filter
            exchanges: List of allowed exchanges
            
        Returns:
            Filtered list of ticker symbols
        """
        # TODO: Implement filtering logic using additional API calls
        # For now, return the original list
        logger.warning("Ticker filtering by criteria not yet implemented")
        return tickers