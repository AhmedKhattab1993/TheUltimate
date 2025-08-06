#!/usr/bin/env python3
"""
Demonstration of automatic period data extension solution.

This script demonstrates how the automatic period extension fixes
single-day screening for period-based filters.
"""

import asyncio
import logging
from datetime import date, timedelta
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from app.core.filters import VolumeFilter, MovingAverageFilter
from app.core.day_trading_filters import RelativeVolumeFilter
from app.core.filter_analyzer import FilterRequirementAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demonstrate_period_extension():
    """Demonstrate the automatic period extension functionality."""
    
    print("🚀 Automatic Period Data Extension Demo")
    print("=" * 50)
    
    # Scenario: Single-day screening on August 1, 2025
    target_date = date(2025, 8, 1)
    print(f"📅 Target screening date: {target_date}")
    print()
    
    # The problematic filters that previously failed on single-day screening
    print("🔍 Filters that require historical data:")
    filters = [
        RelativeVolumeFilter(min_relative_volume=2.0, lookback_days=20, name="RelativeVolume2x"),
        VolumeFilter(lookback_days=10, threshold=100000, name="MinVolume100K"),
        MovingAverageFilter(period=50, position="above", name="AboveMA50")
    ]
    
    for i, filter_obj in enumerate(filters, 1):
        print(f"  {i}. {filter_obj.name}")
        if hasattr(filter_obj, 'lookback_days'):
            print(f"     → Needs {filter_obj.lookback_days} days of historical data")
        elif hasattr(filter_obj, 'period'):
            print(f"     → Needs {filter_obj.period} days of historical data")
    print()
    
    # Analyze filter requirements
    print("🔬 Analyzing filter requirements...")
    analyzer = FilterRequirementAnalyzer()
    requirements = analyzer.analyze_filters(filters)
    
    for req in requirements:
        print(f"  • {req.filter_name}: {req.lookback_days} days ({req.filter_type})")
    
    # Calculate required extension
    extended_start_date, _ = analyzer.calculate_required_start_date(
        filters, target_date, target_date
    )
    
    extension_days = (target_date - extended_start_date).days
    print()
    print("📈 Extension calculation:")
    print(f"  • Original date range: {target_date} to {target_date} (single day)")
    print(f"  • Extended date range: {extended_start_date} to {target_date}")
    print(f"  • Extension: +{extension_days} days")
    print(f"  • Business days buffer: {analyzer.business_days_buffer} days (for weekends/holidays)")
    print()
    
    # Show the solution
    print("✨ How the automatic extension works:")
    print("  1. 🔍 Analyze active filters to determine data requirements")
    print("  2. 📅 Calculate minimum required start date")
    print("  3. 📊 Fetch extended historical data range")
    print("  4. 🎯 Apply filters to extended data")
    print("  5. ✂️  Slice results back to original date range")
    print()
    
    # Show the metadata
    extension_metadata = analyzer.get_extension_metadata(
        requirements, target_date, extended_start_date
    )
    
    print("📋 Extension metadata:")
    for key, value in extension_metadata.items():
        if key == 'filter_requirements':
            print(f"  • {key}: {len(value)} filters analyzed")
        else:
            print(f"  • {key}: {value}")
    print()
    
    # Show usage examples
    print("💡 Usage examples:")
    print()
    print("1️⃣  Direct ScreenerEngine usage:")
    print("   ```python")
    print("   screener = ScreenerEngine(polygon_client=client)")
    print("   result, metadata = await screener.screen_with_period_extension(")
    print("       symbols=['AAPL', 'MSFT', 'NVDA'],")
    print("       filters=[RelativeVolumeFilter(2.0, 20), MovingAverageFilter(50, 'above')],")
    print(f"       start_date=date({target_date.year}, {target_date.month}, {target_date.day}),")
    print(f"       end_date=date({target_date.year}, {target_date.month}, {target_date.day})")
    print("   )")
    print("   ```")
    print()
    
    print("2️⃣  API endpoint (automatic):")
    print("   The /screen endpoint now automatically uses period extension.")
    print("   Single-day requests with period-based filters work seamlessly!")
    print()
    
    print("3️⃣  PolygonClient usage:")
    print("   ```python")
    print("   extended_data, metadata = await client.fetch_historical_data_with_extension(")
    print("       symbols=['AAPL'], ")
    print(f"       original_start_date=date({target_date.year}, {target_date.month}, {target_date.day}),")
    print(f"       original_end_date=date({target_date.year}, {target_date.month}, {target_date.day}),")
    print("       filter_requirements=requirements")
    print("   )")
    print("   ```")
    print()
    
    print("🎯 Benefits:")
    print("  ✅ Single-day screening now works with all period-based filters")
    print("  ✅ Automatic detection - no manual configuration needed")
    print("  ✅ Maintains existing API compatibility")
    print("  ✅ Preserves bulk endpoint performance optimization")
    print("  ✅ Handles business days and holiday considerations")
    print("  ✅ Provides detailed extension metadata")
    print()
    
    print("🔧 Technical implementation:")
    print("  • FilterRequirementAnalyzer: Analyzes filter data needs")
    print("  • PolygonClient.fetch_historical_data_with_extension(): Extended data fetching")
    print("  • ScreenerEngine.screen_with_period_extension(): Integrated screening")
    print("  • SmartDateCalculator: Business day calculations")
    print("  • Automatic result slicing back to original date range")
    print()
    
    print("🎉 The automatic period extension is now active!")
    print("All period-based filters work correctly with single-day screening.")


if __name__ == "__main__":
    asyncio.run(demonstrate_period_extension())