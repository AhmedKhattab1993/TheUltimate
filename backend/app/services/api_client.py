"""
API Client for interacting with the screener API.

This client provides a simple interface for calling the screener API
from within the backend services.
"""

import aiohttp
import logging
from typing import Dict, Any, Optional
from datetime import date

from ..models.simple_requests import SimpleScreenRequest, SimpleScreenResponse

logger = logging.getLogger(__name__)


class APIClient:
    """Client for interacting with the screener API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the API client.
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _ensure_session(self):
        """Ensure we have an active session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def screen_stocks(self, request: SimpleScreenRequest) -> SimpleScreenResponse:
        """
        Call the stock screener API.
        
        Args:
            request: Screening request with filters
            
        Returns:
            SimpleScreenResponse with results
        """
        await self._ensure_session()
        
        url = f"{self.base_url}/api/v2/simple-screener/screen"
        
        # Convert request to dict, handling date serialization
        request_data = request.model_dump()
        
        # Convert dates to strings
        if isinstance(request_data.get('start_date'), date):
            request_data['start_date'] = request_data['start_date'].isoformat()
        if isinstance(request_data.get('end_date'), date):
            request_data['end_date'] = request_data['end_date'].isoformat()
        
        try:
            async with self.session.post(url, json=request_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API request failed with status {response.status}: {error_text}")
                
                response_data = await response.json()
                
                # Convert response data back to model
                return SimpleScreenResponse(**response_data)
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            raise Exception(f"Failed to connect to screener API: {e}")
        except Exception as e:
            logger.error(f"Screener API error: {e}")
            raise
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None