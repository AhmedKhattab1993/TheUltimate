"""
Date utilities for trading days calculations.
"""

from datetime import date, timedelta
from typing import List


def is_weekend(d: date) -> bool:
    """Check if a date is a weekend."""
    return d.weekday() >= 5  # Saturday = 5, Sunday = 6


def get_trading_days_between(start_date: date, end_date: date) -> List[date]:
    """
    Get all trading days between two dates (inclusive).
    For now, this simply excludes weekends. 
    In production, should also check market holidays.
    """
    trading_days = []
    current = start_date
    
    while current <= end_date:
        if not is_weekend(current):
            trading_days.append(current)
        current += timedelta(days=1)
    
    return trading_days


def get_previous_trading_day(d: date) -> date:
    """Get the previous trading day."""
    previous = d - timedelta(days=1)
    
    while is_weekend(previous):
        previous -= timedelta(days=1)
    
    return previous