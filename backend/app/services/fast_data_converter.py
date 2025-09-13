"""
Fast data converter that bypasses Pydantic models for performance.
"""

import numpy as np
from typing import List, Any
from datetime import date


def rows_to_numpy(rows: List[Any]) -> np.ndarray:
    """
    Convert database rows directly to numpy array without intermediate objects.
    
    Args:
        rows: List of asyncpg Record objects with fields:
              date, open, high, low, close, volume
    
    Returns:
        Structured numpy array for efficient computation
    """
    if not rows:
        # Return empty array with correct dtype
        dtype = [
            ('date', 'datetime64[D]'),
            ('open', 'float32'),
            ('high', 'float32'),
            ('low', 'float32'),
            ('close', 'float32'),
            ('volume', 'int64'),
            ('vwap', 'float32')
        ]
        return np.array([], dtype=dtype)
    
    # Pre-allocate arrays for better performance
    n = len(rows)
    dates = np.empty(n, dtype='datetime64[D]')
    opens = np.empty(n, dtype='float32')
    highs = np.empty(n, dtype='float32')
    lows = np.empty(n, dtype='float32')
    closes = np.empty(n, dtype='float32')
    volumes = np.empty(n, dtype='int64')
    vwaps = np.full(n, np.nan, dtype='float32')  # Default to NaN
    
    # Fill arrays in a single pass
    for i, row in enumerate(rows):
        dates[i] = row['date']
        opens[i] = row['open']
        highs[i] = row['high']
        lows[i] = row['low']
        closes[i] = row['close']
        volumes[i] = row['volume']
        # vwap might not be in the query results
        if 'vwap' in row:
            vwaps[i] = row['vwap']
    
    # Create structured array
    dtype = [
        ('date', 'datetime64[D]'),
        ('open', 'float32'),
        ('high', 'float32'),
        ('low', 'float32'),
        ('close', 'float32'),
        ('volume', 'int64'),
        ('vwap', 'float32')
    ]
    
    structured_array = np.empty(n, dtype=dtype)
    structured_array['date'] = dates
    structured_array['open'] = opens
    structured_array['high'] = highs
    structured_array['low'] = lows
    structured_array['close'] = closes
    structured_array['volume'] = volumes
    structured_array['vwap'] = vwaps
    
    return structured_array