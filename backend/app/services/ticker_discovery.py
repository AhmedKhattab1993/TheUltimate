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
        all_tickers = []
        cursor = None
        page_count = 0
        
        logger.info("Starting to fetch US common stock tickers from Polygon API")
        
        try:
            while True:
                page_count += 1
                logger.debug(f"Fetching page {page_count} of tickers")
                
                # Fetch a page of tickers
                tickers_data = await self._fetch_tickers_page(cursor)
                
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
            
            # Remove duplicates and sort
            unique_tickers = sorted(list(set(all_tickers)))
            
            logger.info(f"Successfully fetched {len(unique_tickers)} unique US common stock tickers")
            return unique_tickers
            
        except PolygonAPIError as e:
            logger.error(f"Polygon API error while fetching tickers: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching tickers: {e}")
            raise PolygonAPIError(f"Error fetching tickers: {str(e)}")
    
    async def _fetch_tickers_page(self, cursor: Optional[str] = None) -> dict:
        """
        Fetch a single page of tickers from Polygon API.
        
        Args:
            cursor: Pagination cursor for next page
            
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
                ticker_type="CS",
                active=True,
                limit=1000,
                cursor=cursor_value
            )
        else:
            # First page
            return await self.polygon_client.fetch_tickers(
                market="stocks",
                ticker_type="CS",
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