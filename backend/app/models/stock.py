from pydantic import BaseModel
from datetime import date, datetime
from typing import List, Dict, Optional
import numpy as np


class StockBar(BaseModel):
    """Single stock price bar"""
    symbol: str
    date: date
    timestamp: Optional[datetime] = None  # For minute bars
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    transactions: Optional[int] = None  # Number of transactions for minute bars
    
class StockData(BaseModel):
    """Stock data for a single symbol"""
    symbol: str
    bars: List[StockBar]
    
    def to_numpy(self) -> np.ndarray:
        """Convert to structured numpy array for efficient computation"""
        dtype = [
            ('date', 'datetime64[D]'),
            ('open', 'float32'),
            ('high', 'float32'),
            ('low', 'float32'),
            ('close', 'float32'),
            ('volume', 'int64'),
            ('vwap', 'float32')
        ]
        
        data = []
        for bar in self.bars:
            data.append((
                bar.date,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                bar.vwap or 0.0
            ))
        
        return np.array(data, dtype=dtype)
