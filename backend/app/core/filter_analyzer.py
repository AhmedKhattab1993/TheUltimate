"""
Filter requirement analyzer for automatic period data extension.

This module analyzes active filters to determine their historical data requirements
and calculates the minimum required start date for proper filter operation.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import date, timedelta
import logging
from abc import ABC, abstractmethod

from .filters import BaseFilter, VolumeFilter, MovingAverageFilter, CompositeFilter
from .day_trading_filters import RelativeVolumeFilter, GapFilter


logger = logging.getLogger(__name__)


class FilterRequirement:
    """Container for filter data requirements."""
    
    def __init__(self, 
                 filter_name: str,
                 lookback_days: int,
                 filter_type: str,
                 description: str = ""):
        self.filter_name = filter_name
        self.lookback_days = lookback_days
        self.filter_type = filter_type
        self.description = description
    
    def __repr__(self) -> str:
        return f"FilterRequirement(name='{self.filter_name}', lookback={self.lookback_days}, type='{self.filter_type}')"


class FilterRequirementAnalyzer:
    """
    Analyzes filters to determine their historical data requirements.
    
    This analyzer examines filter configurations to calculate the minimum
    historical data needed for proper filter operation.
    """
    
    def __init__(self):
        self.business_days_buffer = 5  # Extra buffer for weekends/holidays
    
    def analyze_filters(self, filters: List[BaseFilter]) -> List[FilterRequirement]:
        """
        Analyze a list of filters to determine their data requirements.
        
        Args:
            filters: List of filters to analyze
            
        Returns:
            List of FilterRequirement objects
        """
        requirements = []
        
        for filter_obj in filters:
            filter_requirements = self._analyze_single_filter(filter_obj)
            requirements.extend(filter_requirements)
        
        return requirements
    
    def _analyze_single_filter(self, filter_obj: BaseFilter) -> List[FilterRequirement]:
        """Analyze a single filter to determine its requirements."""
        requirements = []
        
        # Handle composite filters recursively
        if isinstance(filter_obj, CompositeFilter):
            for sub_filter in filter_obj.filters:
                requirements.extend(self._analyze_single_filter(sub_filter))
            return requirements
        
        # Analyze specific filter types
        if isinstance(filter_obj, VolumeFilter):
            requirements.append(FilterRequirement(
                filter_name=filter_obj.name,
                lookback_days=filter_obj.lookback_days,
                filter_type="volume",
                description=f"Volume filter requires {filter_obj.lookback_days} days for average calculation"
            ))
        
        elif isinstance(filter_obj, MovingAverageFilter):
            requirements.append(FilterRequirement(
                filter_name=filter_obj.name,
                lookback_days=filter_obj.period,
                filter_type="moving_average",
                description=f"Moving average filter requires {filter_obj.period} days for SMA calculation"
            ))
        
        elif isinstance(filter_obj, RelativeVolumeFilter):
            requirements.append(FilterRequirement(
                filter_name=filter_obj.name,
                lookback_days=filter_obj.lookback_days,
                filter_type="relative_volume",
                description=f"Relative volume filter requires {filter_obj.lookback_days} days for average volume calculation"
            ))
        
        elif isinstance(filter_obj, GapFilter):
            requirements.append(FilterRequirement(
                filter_name=filter_obj.name,
                lookback_days=1,  # Gap filter only needs previous day
                filter_type="gap",
                description="Gap filter requires previous trading day close price"
            ))
        
        # Add more filter types here as needed
        else:
            # For unknown filters, assume no additional lookback needed
            logger.debug(f"Unknown filter type: {type(filter_obj).__name__}, assuming no lookback required")
        
        return requirements
    
    def calculate_required_start_date(self, 
                                    filters: List[BaseFilter], 
                                    target_start_date: date,
                                    target_end_date: date) -> Tuple[date, List[FilterRequirement]]:
        """
        Calculate the minimum required start date to satisfy all filter requirements.
        
        Args:
            filters: List of filters to analyze
            target_start_date: Original requested start date
            target_end_date: Original requested end date
            
        Returns:
            Tuple of (extended_start_date, list_of_requirements)
        """
        requirements = self.analyze_filters(filters)
        
        if not requirements:
            logger.debug("No filter requirements found, using original start date")
            return target_start_date, []
        
        # Find the maximum lookback requirement
        max_lookback = max(req.lookback_days for req in requirements)
        
        # Calculate required start date with business days buffer
        total_lookback_days = max_lookback + self.business_days_buffer
        
        # Extend from the original target start date
        extended_start_date = target_start_date - timedelta(days=total_lookback_days)
        
        # Ensure we don't go too far back (sanity check)
        max_reasonable_lookback = 365  # 1 year maximum
        if (target_start_date - extended_start_date).days > max_reasonable_lookback:
            logger.warning(f"Calculated lookback of {(target_start_date - extended_start_date).days} days "
                         f"exceeds maximum of {max_reasonable_lookback} days, capping at maximum")
            extended_start_date = target_start_date - timedelta(days=max_reasonable_lookback)
        
        logger.info(f"Extended start date from {target_start_date} to {extended_start_date} "
                   f"(+{(target_start_date - extended_start_date).days} days) to satisfy filter requirements")
        
        return extended_start_date, requirements
    
    def get_extension_metadata(self, 
                             requirements: List[FilterRequirement],
                             original_start: date,
                             extended_start: date) -> Dict[str, Any]:
        """
        Generate metadata about the period extension.
        
        Args:
            requirements: List of filter requirements
            original_start: Original start date
            extended_start: Extended start date
            
        Returns:
            Dictionary with extension metadata
        """
        extension_days = (original_start - extended_start).days
        
        metadata = {
            "period_extension_applied": True,
            "original_start_date": original_start.isoformat(),
            "extended_start_date": extended_start.isoformat(),
            "extension_days": extension_days,
            "filter_requirements": [
                {
                    "filter_name": req.filter_name,
                    "filter_type": req.filter_type,
                    "lookback_days": req.lookback_days,
                    "description": req.description
                }
                for req in requirements
            ],
            "max_lookback_required": max(req.lookback_days for req in requirements) if requirements else 0
        }
        
        return metadata
    
    def needs_extension(self, filters: List[BaseFilter]) -> bool:
        """
        Check if any of the provided filters require period extension.
        
        Args:
            filters: List of filters to check
            
        Returns:
            True if extension is needed, False otherwise
        """
        requirements = self.analyze_filters(filters)
        return len(requirements) > 0
    
    def get_filter_summary(self, filters: List[BaseFilter]) -> Dict[str, Any]:
        """
        Get a summary of filter requirements for logging/debugging.
        
        Args:
            filters: List of filters to analyze
            
        Returns:
            Dictionary with filter summary
        """
        requirements = self.analyze_filters(filters)
        
        summary = {
            "total_filters": len(filters),
            "filters_requiring_extension": len(requirements),
            "filter_types": list(set(req.filter_type for req in requirements)),
            "max_lookback_days": max(req.lookback_days for req in requirements) if requirements else 0,
            "min_lookback_days": min(req.lookback_days for req in requirements) if requirements else 0,
            "requirements": [
                {
                    "name": req.filter_name,
                    "type": req.filter_type,
                    "lookback": req.lookback_days
                }
                for req in requirements
            ]
        }
        
        return summary


class SmartDateCalculator:
    """
    Utility class for smart date calculations considering business days and holidays.
    """
    
    def __init__(self):
        # US market holidays (simplified - in production you'd want a more comprehensive list)
        self.known_holidays = {
            # Add major US stock market holidays here
            # This is a simplified list - in production use a proper holiday calendar
        }
    
    def calculate_business_days_back(self, from_date: date, business_days: int) -> date:
        """
        Calculate a date that is approximately 'business_days' business days before from_date.
        
        This is an approximation that accounts for weekends but not all holidays.
        
        Args:
            from_date: Starting date
            business_days: Number of business days to go back
            
        Returns:
            Approximate date that many business days back
        """
        # Rough calculation: assume 5/7 of days are business days
        # Add some buffer for holidays
        calendar_days = int(business_days * 1.5)  # Convert business days to calendar days
        
        return from_date - timedelta(days=calendar_days)
    
    def is_business_day(self, check_date: date) -> bool:
        """
        Check if a date is a business day (Monday-Friday, not a holiday).
        
        Args:
            check_date: Date to check
            
        Returns:
            True if it's a business day, False otherwise
        """
        # Check if it's a weekend
        if check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check if it's a known holiday
        if check_date in self.known_holidays:
            return False
        
        return True
    
    def get_previous_business_day(self, from_date: date, max_lookback: int = 10) -> Optional[date]:
        """
        Get the previous business day before the given date.
        
        Args:
            from_date: Starting date
            max_lookback: Maximum days to look back
            
        Returns:
            Previous business day or None if not found within max_lookback
        """
        current_date = from_date - timedelta(days=1)
        
        for _ in range(max_lookback):
            if self.is_business_day(current_date):
                return current_date
            current_date -= timedelta(days=1)
        
        return None