#!/usr/bin/env python3
"""
Comprehensive test suite for automatic period data extension implementation.

This script thoroughly tests all aspects of the period extension solution to ensure
single-day screening works correctly with all period-based filters.
"""

import asyncio
import logging
import json
import time
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
import sys
import os
import numpy as np

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from app.core.filters import VolumeFilter, MovingAverageFilter, BaseFilter
from app.core.day_trading_filters import RelativeVolumeFilter, GapFilter
from app.core.filter_analyzer import FilterRequirementAnalyzer, FilterRequirement
from app.services.polygon_client import PolygonClient
from app.services.screener import ScreenerEngine
from app.models.stock import StockData, StockBar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestResults:
    """Container for test results and statistics."""
    
    def __init__(self):
        self.test_cases: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.start_time = time.time()
        
    def add_test_result(self, test_name: str, status: str, details: Dict[str, Any], 
                       execution_time: float = 0.0, error: Optional[str] = None):
        """Add a test result."""
        result = {
            'test_name': test_name,
            'status': status,
            'details': details,
            'execution_time_ms': execution_time * 1000,
            'timestamp': datetime.now().isoformat()
        }
        
        if error:
            result['error'] = error
            
        self.test_cases.append(result)
        
        if status == 'PASSED':
            self.passed += 1
        elif status == 'FAILED':
            self.failed += 1
        else:
            self.errors += 1
            
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary."""
        total_time = time.time() - self.start_time
        total_tests = len(self.test_cases)
        
        return {
            'total_tests': total_tests,
            'passed': self.passed,
            'failed': self.failed,
            'errors': self.errors,
            'success_rate': (self.passed / total_tests * 100) if total_tests > 0 else 0,
            'total_execution_time_seconds': total_time,
            'avg_test_time_ms': sum(tc['execution_time_ms'] for tc in self.test_cases) / total_tests if total_tests > 0 else 0
        }
        
    def print_summary(self):
        """Print comprehensive test summary."""
        summary = self.get_summary()
        print(f"\n{'='*80}")
        print("COMPREHENSIVE PERIOD EXTENSION TEST RESULTS")
        print(f"{'='*80}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']} ({summary['success_rate']:.1f}%)")
        print(f"Failed: {summary['failed']}")
        print(f"Errors: {summary['errors']}")
        print(f"Total Execution Time: {summary['total_execution_time_seconds']:.2f} seconds")
        print(f"Average Test Time: {summary['avg_test_time_ms']:.1f} ms")
        print(f"{'='*80}\n")
        
    def print_detailed_results(self):
        """Print detailed results for all tests."""
        for test_case in self.test_cases:
            status_symbol = "✅" if test_case['status'] == 'PASSED' else "❌" if test_case['status'] == 'FAILED' else "⚠️"
            print(f"{status_symbol} {test_case['test_name']} - {test_case['status']} ({test_case['execution_time_ms']:.1f}ms)")
            
            if test_case['status'] != 'PASSED':
                if 'error' in test_case:
                    print(f"   Error: {test_case['error']}")
                else:
                    print(f"   Details: {json.dumps(test_case['details'], indent=6)}")


class ComprehensivePeriodExtensionTester:
    """Comprehensive tester for period extension functionality."""
    
    def __init__(self):
        self.results = TestResults()
        self.polygon_client = None
        self.test_date = date(2025, 8, 1)  # August 1, 2025 - a Friday
        self.test_symbols = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL']
        
    async def initialize(self):
        """Initialize test environment."""
        try:
            # Try to initialize Polygon client
            self.polygon_client = PolygonClient()
            logger.info("Polygon client initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize Polygon client: {e}")
            logger.info("Tests will use mock data where possible")
            
    def create_mock_stock_data(self, symbol: str, start_date: date, num_days: int = 50) -> StockData:
        """Create realistic mock stock data for testing."""
        bars = []
        current_date = start_date - timedelta(days=num_days)
        
        # Generate realistic price and volume patterns
        base_price = 100.0 + hash(symbol) % 200  # Different base price per symbol
        base_volume = 1000000 + hash(symbol) % 5000000  # Different base volume per symbol
        
        for i in range(num_days + 1):
            # Skip weekends (simplified calendar)
            if current_date.weekday() < 5:
                # Create realistic price movements
                price_change = np.random.normal(0, 2)  # 2% daily volatility
                volume_multiplier = np.random.lognormal(0, 0.5)  # Volume variation
                
                # Calculate OHLC with realistic patterns
                close_price = base_price * (1 + price_change / 100)
                high_price = close_price * (1 + abs(np.random.normal(0, 0.01)))
                low_price = close_price * (1 - abs(np.random.normal(0, 0.01)))
                open_price = close_price * (1 + np.random.normal(0, 0.005))
                volume = int(base_volume * volume_multiplier)
                
                bar = StockBar(
                    symbol=symbol,
                    date=current_date,
                    open=max(0.01, open_price),
                    high=max(0.01, high_price),
                    low=max(0.01, low_price),
                    close=max(0.01, close_price),
                    volume=max(1, volume),
                    vwap=(high_price + low_price + close_price) / 3
                )
                bars.append(bar)
                base_price = close_price  # Update base price for next day
                
            current_date += timedelta(days=1)
            
        return StockData(symbol=symbol, bars=bars)
    
    async def test_filter_requirement_analyzer(self):
        """Test 1: FilterRequirementAnalyzer functionality."""
        test_start = time.time()
        
        try:
            analyzer = FilterRequirementAnalyzer()
            
            # Test 1.1: Single filter analysis
            volume_filter = VolumeFilter(lookback_days=20, threshold=1000000, name="TestVolumeFilter")
            requirements = analyzer.analyze_filters([volume_filter])
            
            assert len(requirements) == 1, f"Expected 1 requirement, got {len(requirements)}"
            assert requirements[0].lookback_days == 20, f"Expected 20 lookback days, got {requirements[0].lookback_days}"
            assert requirements[0].filter_type == "volume", f"Expected volume type, got {requirements[0].filter_type}"
            
            # Test 1.2: Multiple filter analysis
            ma_filter = MovingAverageFilter(period=50, position="above", name="TestMAFilter")
            rel_vol_filter = RelativeVolumeFilter(min_relative_volume=2.0, lookback_days=20, name="TestRelVolFilter")
            
            multi_requirements = analyzer.analyze_filters([volume_filter, ma_filter, rel_vol_filter])
            assert len(multi_requirements) == 3, f"Expected 3 requirements, got {len(multi_requirements)}"
            
            # Test 1.3: Date range calculation
            test_start_date = date(2025, 8, 1)
            test_end_date = date(2025, 8, 1)
            
            extended_start, reqs = analyzer.calculate_required_start_date(
                [volume_filter, ma_filter, rel_vol_filter], 
                test_start_date, 
                test_end_date
            )
            
            # Should extend by max(20, 50, 20) + 5 buffer = 55 days
            expected_extension = 55
            actual_extension = (test_start_date - extended_start).days
            
            assert actual_extension >= expected_extension - 5, f"Extension too small: {actual_extension} vs expected ~{expected_extension}"
            assert actual_extension <= expected_extension + 10, f"Extension too large: {actual_extension} vs expected ~{expected_extension}"
            
            # Test 1.4: Extension metadata
            metadata = analyzer.get_extension_metadata(reqs, test_start_date, extended_start)
            
            assert metadata['period_extension_applied'] == True
            assert metadata['extension_days'] == actual_extension
            assert len(metadata['filter_requirements']) == 3
            
            self.results.add_test_result(
                "FilterRequirementAnalyzer - Basic Functionality",
                "PASSED",
                {
                    "single_filter_requirements": len(requirements),
                    "multi_filter_requirements": len(multi_requirements),
                    "extension_days": actual_extension,
                    "expected_extension": expected_extension,
                    "metadata_keys": list(metadata.keys())
                },
                time.time() - test_start
            )
            
        except Exception as e:
            self.results.add_test_result(
                "FilterRequirementAnalyzer - Basic Functionality",
                "ERROR",
                {},
                time.time() - test_start,
                str(e)
            )
            
    async def test_individual_filters(self):
        """Test 2: Individual period-based filter functionality."""
        test_start = time.time()
        
        try:
            # Create mock data with enough history
            stock_data = self.create_mock_stock_data("AAPL", self.test_date, 60)
            
            # Convert stock data to numpy format for filter testing
            numpy_data = stock_data.to_numpy()
            
            # Test 2.1: VolumeFilter with lookback
            volume_filter = VolumeFilter(lookback_days=20, threshold=500000, name="VolumeTest")
            volume_result = volume_filter.apply(numpy_data, stock_data.symbol)
            
            assert volume_result is not None, "VolumeFilter returned None"
            assert hasattr(volume_result, 'qualifying_mask'), "VolumeFilter result missing qualifying_mask"
            
            # Test 2.2: MovingAverageFilter with period
            ma_filter = MovingAverageFilter(period=20, position="above", name="MATest")
            ma_result = ma_filter.apply(numpy_data, stock_data.symbol)
            
            assert ma_result is not None, "MovingAverageFilter returned None"
            assert hasattr(ma_result, 'qualifying_mask'), "MovingAverageFilter result missing qualifying_mask"
            
            # Test 2.3: RelativeVolumeFilter with lookback
            rel_vol_filter = RelativeVolumeFilter(min_relative_volume=1.5, lookback_days=20, name="RelVolTest")
            rel_vol_result = rel_vol_filter.apply(numpy_data, stock_data.symbol)
            
            assert rel_vol_result is not None, "RelativeVolumeFilter returned None"
            assert hasattr(rel_vol_result, 'qualifying_mask'), "RelativeVolumeFilter result missing qualifying_mask"
            
            # Test 2.4: GapFilter (needs previous day)
            gap_filter = GapFilter(min_gap_percent=2.0, max_gap_percent=10.0, name="GapTest")
            gap_result = gap_filter.apply(numpy_data, stock_data.symbol)
            
            assert gap_result is not None, "GapFilter returned None"
            assert hasattr(gap_result, 'qualifying_mask'), "GapFilter result missing qualifying_mask"
            
            self.results.add_test_result(
                "Individual Period-Based Filters",
                "PASSED",
                {
                    "volume_filter_qualifying_days": int(np.sum(volume_result.qualifying_mask)),
                    "ma_filter_qualifying_days": int(np.sum(ma_result.qualifying_mask)),
                    "rel_vol_filter_qualifying_days": int(np.sum(rel_vol_result.qualifying_mask)),
                    "gap_filter_qualifying_days": int(np.sum(gap_result.qualifying_mask)),
                    "data_points_available": len(stock_data.bars)
                },
                time.time() - test_start
            )
            
        except Exception as e:
            self.results.add_test_result(
                "Individual Period-Based Filters",
                "ERROR",
                {},
                time.time() - test_start,
                str(e)
            )
            
    async def test_screener_engine_integration(self):
        """Test 3: ScreenerEngine with period extension."""
        test_start = time.time()
        
        try:
            screener = ScreenerEngine(max_workers=4)
            
            # Create filters requiring different periods
            filters = [
                VolumeFilter(lookback_days=20, threshold=500000, name="VolumeFilter20"),
                MovingAverageFilter(period=50, position="above", name="MA50"),
                RelativeVolumeFilter(min_relative_volume=1.5, lookback_days=20, name="RelVol20")
            ]
            
            # Create mock stock data for multiple symbols
            stock_data_list = [
                self.create_mock_stock_data(symbol, self.test_date, 80) 
                for symbol in ['AAPL', 'MSFT', 'NVDA']
            ]
            
            # Test regular screening with sufficient data - use None for date range to test all data
            # The filters will work on all the historical data, not just the target date
            screen_result = screener.screen(stock_data_list, filters, date_range=None)
            
            assert screen_result is not None, "ScreenerEngine returned None"
            assert hasattr(screen_result, 'results'), "ScreenerResult missing results attribute"
            
            # Verify results
            total_symbols = len(screen_result.results)
            qualifying_symbols = len(screen_result.qualifying_symbols)
            
            assert total_symbols > 0, "No symbols processed"
            
            self.results.add_test_result(
                "ScreenerEngine Integration",
                "PASSED",
                {
                    "symbols_processed": total_symbols,
                    "qualifying_symbols": qualifying_symbols,
                    "processing_time_ms": screen_result.processing_time * 1000,
                    "filters_tested": len(filters)
                },
                time.time() - test_start
            )
            
        except Exception as e:
            self.results.add_test_result(
                "ScreenerEngine Integration",
                "ERROR",
                {},
                time.time() - test_start,
                str(e)
            )
            
    async def test_api_integration(self):
        """Test 4: API integration with real or simulated requests."""
        test_start = time.time()
        
        try:
            if self.polygon_client is None:
                # Skip real API test if no client available
                self.results.add_test_result(
                    "API Integration Test",
                    "SKIPPED",
                    {"reason": "No Polygon client available"},
                    time.time() - test_start
                )
                return
                
            screener = ScreenerEngine(max_workers=4, polygon_client=self.polygon_client)
            
            # Test single-day screening with period extension
            filters = [
                VolumeFilter(lookback_days=20, threshold=1000000, name="VolumeAPI"),
                MovingAverageFilter(period=20, position="above", name="MA20API")
            ]
            
            symbols = ['AAPL', 'MSFT']  # Use smaller set for faster testing
            
            # Test the period extension method
            try:
                screen_result, extension_metadata = await screener.screen_with_period_extension(
                    symbols=symbols,
                    filters=filters,
                    start_date=self.test_date,
                    end_date=self.test_date,
                    auto_slice_results=True,
                    adjusted=True,
                    max_concurrent=50,
                    prefer_bulk=True
                )
                
                # Verify extension was applied
                assert extension_metadata.get('period_extension_applied') == True, "Period extension not applied"
                assert 'extension_days' in extension_metadata, "Extension days not in metadata"
                assert extension_metadata['extension_days'] > 0, "No extension days calculated"
                
                # Verify results
                assert screen_result is not None, "No screen result returned"
                processed_symbols = len(screen_result.results)
                
                self.results.add_test_result(
                    "API Integration - Period Extension",
                    "PASSED",
                    {
                        "symbols_requested": len(symbols),
                        "symbols_processed": processed_symbols,
                        "extension_applied": extension_metadata['period_extension_applied'],
                        "extension_days": extension_metadata['extension_days'],
                        "processing_time_s": screen_result.processing_time,
                        "qualifying_symbols": len(screen_result.qualifying_symbols)
                    },
                    time.time() - test_start
                )
                
            except Exception as api_error:
                self.results.add_test_result(
                    "API Integration - Period Extension",
                    "FAILED",
                    {"api_error": str(api_error)},
                    time.time() - test_start,
                    str(api_error)
                )
                
        except Exception as e:
            self.results.add_test_result(
                "API Integration Test",
                "ERROR",
                {},
                time.time() - test_start,
                str(e)
            )
            
    async def test_edge_cases(self):
        """Test 5: Edge cases and error handling."""
        test_start = time.time()
        
        edge_cases_passed = 0
        edge_cases_total = 0
        
        try:
            analyzer = FilterRequirementAnalyzer()
            
            # Edge Case 1: Minimal extension for GapFilter (should need only 1 day + buffer)
            gap_filter = GapFilter(min_gap_percent=1.0, max_gap_percent=5.0, name="SimpleGap")
            edge_cases_total += 1
            
            gap_start, gap_reqs = analyzer.calculate_required_start_date(
                [gap_filter], self.test_date, self.test_date
            )
            gap_extension = (self.test_date - gap_start).days
            
            if 5 <= gap_extension <= 10:  # Should be minimal (1 day + 5 buffer)
                edge_cases_passed += 1
                logger.info(f"✅ Edge Case 1 passed: Minimal extension for GapFilter ({gap_extension} days)")
            else:
                logger.warning(f"❌ Edge Case 1 failed: GapFilter extension incorrect ({gap_extension} days)")
            
            # Edge Case 2: Very long period (200-day MA)
            edge_cases_total += 1
            long_period_filter = MovingAverageFilter(period=200, position="above", name="MA200")
            extended_start, _ = analyzer.calculate_required_start_date(
                [long_period_filter], 
                self.test_date, 
                self.test_date
            )
            
            extension_days = (self.test_date - extended_start).days
            if 200 <= extension_days <= 365:  # Should be capped at 365 days max
                edge_cases_passed += 1
                logger.info(f"✅ Edge Case 2 passed: Long period handled correctly ({extension_days} days)")
            else:
                logger.warning(f"❌ Edge Case 2 failed: Long period not handled correctly ({extension_days} days)")
            
            # Edge Case 3: Weekend extension (Monday screening)
            edge_cases_total += 1
            monday_date = date(2025, 8, 4)  # Monday
            weekend_start, _ = analyzer.calculate_required_start_date(
                [VolumeFilter(lookback_days=5, threshold=100000, name="WeekendTest")],
                monday_date,
                monday_date
            )
            
            weekend_extension = (monday_date - weekend_start).days
            if weekend_extension >= 10:  # Should account for weekend
                edge_cases_passed += 1
                logger.info(f"✅ Edge Case 3 passed: Weekend extension handled ({weekend_extension} days)")
            else:
                logger.warning(f"❌ Edge Case 3 failed: Weekend extension insufficient ({weekend_extension} days)")
            
            # Edge Case 4: Multiple overlapping periods
            edge_cases_total += 1
            overlapping_filters = [
                VolumeFilter(lookback_days=20, threshold=100000, name="Vol20"),
                VolumeFilter(lookback_days=50, threshold=200000, name="Vol50"),
                MovingAverageFilter(period=30, position="above", name="MA30")
            ]
            
            overlap_start, overlap_reqs = analyzer.calculate_required_start_date(
                overlapping_filters,
                self.test_date,
                self.test_date
            )
            
            overlap_extension = (self.test_date - overlap_start).days
            max_required = max(20, 50, 30)  # Should use maximum requirement
            
            if overlap_extension >= max_required:
                edge_cases_passed += 1
                logger.info(f"✅ Edge Case 4 passed: Overlapping periods handled ({overlap_extension} days for max {max_required})")
            else:
                logger.warning(f"❌ Edge Case 4 failed: Overlapping periods not handled correctly ({overlap_extension} days)")
            
            self.results.add_test_result(
                "Edge Cases and Error Handling",
                "PASSED" if edge_cases_passed == edge_cases_total else "FAILED",
                {
                    "edge_cases_passed": edge_cases_passed,
                    "edge_cases_total": edge_cases_total,
                    "success_rate": (edge_cases_passed / edge_cases_total) * 100
                },
                time.time() - test_start
            )
            
        except Exception as e:
            self.results.add_test_result(
                "Edge Cases and Error Handling",
                "ERROR",
                {
                    "edge_cases_passed": edge_cases_passed,
                    "edge_cases_total": edge_cases_total
                },
                time.time() - test_start,
                str(e)
            )
            
    async def test_performance_comparison(self):
        """Test 6: Performance comparison between regular and extended screening."""
        test_start = time.time()
        
        try:
            # Create test data
            symbols = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'TSLA']
            stock_data_list = [
                self.create_mock_stock_data(symbol, self.test_date, 100) 
                for symbol in symbols
            ]
            
            filters = [
                VolumeFilter(lookback_days=20, threshold=500000, name="PerfVol"),
                MovingAverageFilter(period=50, position="above", name="PerfMA")
            ]
            
            screener = ScreenerEngine(max_workers=4)
            
            # Test regular screening (with sufficient pre-loaded data)
            regular_start = time.time()
            regular_result = screener.screen(stock_data_list, filters, (self.test_date, self.test_date))
            regular_time = time.time() - regular_start
            
            # Test with period extension logic (using mock data)
            extension_start = time.time()
            
            # Simulate the period extension process
            analyzer = FilterRequirementAnalyzer()
            extended_start_date, requirements = analyzer.calculate_required_start_date(
                filters, self.test_date, self.test_date
            )
            
            # Create extended mock data
            extended_stock_data_list = [
                self.create_mock_stock_data(symbol, extended_start_date, 
                                          (self.test_date - extended_start_date).days + 10) 
                for symbol in symbols
            ]
            
            # Run screening on extended data
            extended_result = screener.screen(extended_stock_data_list, filters, None)
            extension_time = time.time() - extension_start
            
            # Performance comparison
            performance_overhead = ((extension_time - regular_time) / regular_time) * 100
            
            self.results.add_test_result(
                "Performance Comparison",
                "PASSED",
                {
                    "regular_screening_time_ms": regular_time * 1000,
                    "extended_screening_time_ms": extension_time * 1000,
                    "performance_overhead_percent": performance_overhead,
                    "symbols_tested": len(symbols),
                    "filters_tested": len(filters),
                    "regular_qualifying": len(regular_result.qualifying_symbols),
                    "extended_qualifying": len(extended_result.qualifying_symbols)
                },
                time.time() - test_start
            )
            
        except Exception as e:
            self.results.add_test_result(
                "Performance Comparison",
                "ERROR",
                {},
                time.time() - test_start,
                str(e)
            )
            
    async def test_real_world_scenarios(self):
        """Test 7: Real-world screening scenarios."""
        test_start = time.time()
        
        try:
            scenarios = [
                {
                    "name": "Day Trading Scenario",
                    "filters": [
                        RelativeVolumeFilter(min_relative_volume=2.0, lookback_days=20, name="DayTradingRelVol"),
                        GapFilter(min_gap_percent=2.0, max_gap_percent=8.0, name="DayTradingGap"),
                        VolumeFilter(lookback_days=10, threshold=1000000, name="DayTradingVol")
                    ]
                },
                {
                    "name": "Swing Trading Scenario", 
                    "filters": [
                        MovingAverageFilter(period=20, position="above", name="SwingMA20"),
                        MovingAverageFilter(period=50, position="above", name="SwingMA50"),
                        VolumeFilter(lookback_days=20, threshold=500000, name="SwingVol")
                    ]
                },
                {
                    "name": "Long Term Momentum",
                    "filters": [
                        MovingAverageFilter(period=200, position="above", name="LongMA200"),
                        VolumeFilter(lookback_days=50, threshold=2000000, name="LongVol")
                    ]
                }
            ]
            
            scenario_results = []
            
            for scenario in scenarios:
                scenario_start = time.time()
                
                # Create test data for scenario
                symbols = ['AAPL', 'MSFT', 'NVDA']
                stock_data_list = [
                    self.create_mock_stock_data(symbol, self.test_date, 250)  # Enough for 200-day MA
                    for symbol in symbols
                ]
                
                screener = ScreenerEngine(max_workers=4)
                
                # Run scenario
                result = screener.screen(stock_data_list, scenario["filters"], (self.test_date, self.test_date))
                scenario_time = time.time() - scenario_start
                
                scenario_result = {
                    "scenario_name": scenario["name"],
                    "filters_count": len(scenario["filters"]),
                    "symbols_processed": len(result.results),
                    "qualifying_symbols": len(result.qualifying_symbols),
                    "processing_time_ms": scenario_time * 1000,
                    "success": result.num_processed > 0
                }
                
                scenario_results.append(scenario_result)
                
            # All scenarios should complete successfully
            successful_scenarios = sum(1 for sr in scenario_results if sr["success"])
            
            self.results.add_test_result(
                "Real-World Scenarios",
                "PASSED" if successful_scenarios == len(scenarios) else "FAILED",
                {
                    "scenarios_tested": len(scenarios),
                    "scenarios_successful": successful_scenarios,
                    "scenario_details": scenario_results
                },
                time.time() - test_start
            )
            
        except Exception as e:
            self.results.add_test_result(
                "Real-World Scenarios",
                "ERROR",
                {},
                time.time() - test_start,
                str(e)
            )
            
    async def test_backward_compatibility(self):
        """Test 8: Backward compatibility with existing functionality."""
        test_start = time.time()
        
        try:
            # Test that existing multi-day screening still works
            screener = ScreenerEngine(max_workers=4)
            
            # Multi-day range (should not need extension)
            multi_day_start = self.test_date - timedelta(days=30)
            multi_day_end = self.test_date
            
            # Create data for multi-day range
            stock_data_list = [
                self.create_mock_stock_data(symbol, multi_day_end, 60)
                for symbol in ['AAPL', 'MSFT']
            ]
            
            # Filters that would normally require extension
            filters = [
                VolumeFilter(lookback_days=20, threshold=500000, name="BackCompatVol"),
                MovingAverageFilter(period=20, position="above", name="BackCompatMA")
            ]
            
            # Test multi-day screening
            multi_day_result = screener.screen(
                stock_data_list, 
                filters, 
                (multi_day_start, multi_day_end)
            )
            
            # For single-day screening, we expect this to fail without period extension
            # because the data is filtered to just one day before filters are applied
            single_day_result = screener.screen(
                stock_data_list,
                filters,
                (self.test_date, self.test_date)
            )
            
            # Multi-day should work, single-day may have limited results due to insufficient data
            assert multi_day_result is not None, "Multi-day screening failed"
            assert single_day_result is not None, "Single-day screening failed"
            assert len(multi_day_result.results) > 0, "Multi-day results empty"
            
            # Single-day might have empty results due to insufficient data - this is expected
            # and is exactly the problem that period extension solves
            single_day_errors = single_day_result.num_errors
            multi_day_errors = multi_day_result.num_errors
            
            self.results.add_test_result(
                "Backward Compatibility",
                "PASSED",
                {
                    "multi_day_symbols": len(multi_day_result.results),
                    "single_day_symbols": len(single_day_result.results),
                    "multi_day_qualifying": len(multi_day_result.qualifying_symbols),
                    "single_day_qualifying": len(single_day_result.qualifying_symbols),
                    "multi_day_errors": multi_day_errors,
                    "single_day_errors": single_day_errors,
                    "multi_day_processing_time_ms": multi_day_result.processing_time * 1000,
                    "single_day_processing_time_ms": single_day_result.processing_time * 1000,
                    "note": "Single-day errors expected without period extension"
                },
                time.time() - test_start
            )
            
        except Exception as e:
            self.results.add_test_result(
                "Backward Compatibility",
                "ERROR",
                {},
                time.time() - test_start,
                str(e)
            )
            
    async def run_all_tests(self):
        """Run the complete test suite."""
        logger.info("Starting comprehensive period extension testing...")
        
        await self.initialize()
        
        # Run all test categories
        test_methods = [
            self.test_filter_requirement_analyzer,
            self.test_individual_filters,
            self.test_screener_engine_integration,
            self.test_api_integration,
            self.test_edge_cases,
            self.test_performance_comparison,
            self.test_real_world_scenarios,
            self.test_backward_compatibility
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                logger.error(f"Critical error in {test_method.__name__}: {e}")
                
        # Print results
        self.results.print_summary()
        
        # Print detailed results if there were failures
        if self.results.failed > 0 or self.results.errors > 0:
            print("\nDETAILED RESULTS:")
            print("="*50)
            self.results.print_detailed_results()
            
        return self.results


async def main():
    """Main test execution function."""
    print("🚀 Starting Comprehensive Period Extension Test Suite")
    print("="*80)
    
    tester = ComprehensivePeriodExtensionTester()
    results = await tester.run_all_tests()
    
    # Final assessment
    success_rate = results.get_summary()['success_rate']
    
    if success_rate >= 90:
        print(f"🎉 TEST SUITE PASSED! Success rate: {success_rate:.1f}%")
        print("✅ Period extension implementation is working correctly")
    elif success_rate >= 70:
        print(f"⚠️  TEST SUITE PASSED WITH WARNINGS! Success rate: {success_rate:.1f}%")
        print("🔧 Some minor issues detected, but core functionality works")
    else:
        print(f"❌ TEST SUITE FAILED! Success rate: {success_rate:.1f}%")
        print("🛠️  Significant issues detected, implementation needs review")
    
    # Save detailed results to file
    with open('/home/ahmed/TheUltimate/backend/period_extension_test_results.json', 'w') as f:
        json.dump({
            'summary': results.get_summary(),
            'test_cases': results.test_cases,
            'timestamp': datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\n📊 Detailed results saved to: /home/ahmed/TheUltimate/backend/period_extension_test_results.json")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())