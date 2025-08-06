from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union
import os
import json
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    polygon_api_key: str = os.getenv("POLYGON_API_KEY", "")
    cors_origins: List[str] = ["*"]  # Allow all origins for testing
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            # Handle JSON string from environment variable
            if v.startswith('[') and v.endswith(']'):
                try:
                    parsed = json.loads(v)
                    return parsed if isinstance(parsed, list) else [str(parsed)]
                except json.JSONDecodeError:
                    return [v] if v else ["*"]
            # Handle comma-separated string
            elif ',' in v:
                return [origin.strip() for origin in v.split(',')]
            else:
                return [v] if v else ["*"]
        return v if isinstance(v, list) else ["*"]
    
    # API settings
    api_v1_str: str = "/api/v1"
    project_name: str = "Stock Screener"
    
    # Polygon API settings
    polygon_base_url: str = "https://api.polygon.io"
    polygon_rate_limit: int = int(os.getenv("POLYGON_RATE_LIMIT", "100"))  # Default to 100 requests per minute for paid tier
    
    # Gap calculation enhancement settings
    enable_async_gap_calculation: bool = os.getenv("ENABLE_ASYNC_GAP_CALCULATION", "true").lower() == "true"
    previous_day_cache_ttl: int = int(os.getenv("PREVIOUS_DAY_CACHE_TTL", "86400"))  # 24 hours default
    max_previous_day_lookback: int = int(os.getenv("MAX_PREVIOUS_DAY_LOOKBACK", "10"))  # Maximum days to look back for previous trading day
    
    # Default stock universe
    default_symbols: List[str] = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", 
        "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM",
        "PFE", "CVX", "KO", "ABBV", "PEP", "NKE", "MRK", "TMO", "CSCO",
        "VZ", "ADBE", "CMCSA"
    ]  # Top 30 S&P 500 stocks as default
    
    class Config:
        case_sensitive = False


settings = Settings()