#!/usr/bin/env python3
"""
Comprehensive filter testing to understand why no stocks are showing in results.
Tests each filter individually and progressively to identify bottlenecks.
"""

import asyncio
import sys
from datetime import date, timedelta
from typing import List, Dict, Any
import numpy as np
# from tabulate import tabulate  # Not installed, using simple formatting

# Add app to path
sys.path.append('/home/ahmed/TheUltimate/backend')

from app.services.polygon_client import PolygonClient
from app.services.screener import ScreenerEngine
from app.core.day_trading_filters import (
    GapFilter,
    PriceRangeFilter,
    RelativeVolumeFilter,
    MarketCapFilter
)
from app.models.stock import StockData, StockBar


class FilterTester:
    """Comprehensive filter testing utility."""
    
    def __init__(self):
        self.polygon_client = PolygonClient()
        self.screener = ScreenerEngine(polygon_client=self.polygon_client)
        
        # Test symbols - mix of popular stocks
        self.test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'AMC', 'GME', 'SPY', 'QQQ', 'META']
        
        # Test dates
        self.test_dates = [
            date(2025, 8, 1),  # Original test date
            date(2024, 12, 31),  # Recent past date
            date(2024, 11, 15),  # Further past date
        ]
        
        # Filter configurations to test
        self.filter_configs = {
            'gap_strict': GapFilter(min_gap_percent=4.0),
            'gap_moderate': GapFilter(min_gap_percent=2.0),
            'gap_lenient': GapFilter(min_gap_percent=1.0),
            'price_strict': PriceRangeFilter(min_price=10.0, max_price=500.0),
            'price_lenient': PriceRangeFilter(min_price=1.0, max_price=1000.0),
            'volume_strict': RelativeVolumeFilter(min_relative_volume=2.0),
            'volume_lenient': RelativeVolumeFilter(min_relative_volume=1.5),
            'market_cap': MarketCapFilter(max_market_cap=10_000_000_000),  # $10B
        }
        
    async def fetch_data_for_date(self, target_date: date) -> Dict[str, StockData]:
        """Fetch data for all test symbols for a specific date."""
        print(f"\nFetching data for {target_date}...")
        
        # Fetch 30 days of data to ensure filters have enough history
        start_date = target_date - timedelta(days=30)
        end_date = target_date
        
        try:
            data_dict = await self.polygon_client.fetch_bulk_historical_data_with_fallback(
                symbols=self.test_symbols,
                start_date=start_date,
                end_date=end_date,
                adjusted=True,
                prefer_bulk=True,
                max_concurrent=10
            )
            
            print(f"Successfully fetched data for {len(data_dict)} symbols")
            return data_dict
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return {}
    
    def analyze_data_availability(self, stock_data_dict: Dict[str, StockData], target_date: date) -> Dict[str, Any]:
        """Analyze data availability for each symbol."""
        results = []
        
        for symbol, stock_data in stock_data_dict.items():
            if not stock_data or not stock_data.bars:
                results.append({
                    'symbol': symbol,
                    'has_data': False,
                    'total_days': 0,
                    'date_range': 'N/A',
                    'has_target_date': False,
                    'last_price': 'N/A',
                    'last_volume': 'N/A'
                })
                continue
            
            bars = stock_data.bars
            dates = [bar.date for bar in bars]
            has_target = target_date in dates
            
            results.append({
                'symbol': symbol,
                'has_data': True,
                'total_days': len(bars),
                'date_range': f"{min(dates)} to {max(dates)}",
                'has_target_date': has_target,
                'last_price': f"${bars[-1].close:.2f}",
                'last_volume': f"{bars[-1].volume:,}"
            })
        
        return results
    
    def test_individual_filter(self, stock_data_list: List[StockData], filter_obj, filter_name: str, target_date: date) -> Dict[str, Any]:
        """Test a single filter and return results."""
        print(f"\nTesting {filter_name}...")
        
        # Run the filter
        result = self.screener.screen(
            stock_data_list=stock_data_list,
            filters=[filter_obj],
            date_range=(target_date, target_date)
        )
        
        # Analyze results
        total_symbols = len(stock_data_list)
        qualifying_symbols = len(result.qualifying_symbols)
        pass_rate = (qualifying_symbols / total_symbols * 100) if total_symbols > 0 else 0
        
        # Get details for each symbol
        symbol_details = []
        for stock_data in stock_data_list:
            symbol = stock_data.symbol
            if symbol in result.results:
                filter_result = result.results[symbol]
                passed = filter_result.num_qualifying_days > 0
                metrics = filter_result.metrics
            else:
                passed = False
                metrics = {}
            
            symbol_details.append({
                'symbol': symbol,
                'passed': passed,
                'metrics': metrics
            })
        
        return {
            'filter_name': filter_name,
            'total_symbols': total_symbols,
            'qualifying_symbols': qualifying_symbols,
            'pass_rate': pass_rate,
            'symbol_details': symbol_details,
            'processing_time_ms': result.processing_time * 1000
        }
    
    def test_progressive_filters(self, stock_data_list: List[StockData], target_date: date) -> List[Dict[str, Any]]:
        """Test filters progressively, adding one at a time."""
        print("\nTesting progressive filter combinations...")
        
        # Define progressive filter combinations
        progressive_configs = [
            ('No filters', []),
            ('Gap only (4%)', [self.filter_configs['gap_strict']]),
            ('Gap (4%) + Price', [self.filter_configs['gap_strict'], self.filter_configs['price_strict']]),
            ('Gap (4%) + Price + Volume', [
                self.filter_configs['gap_strict'], 
                self.filter_configs['price_strict'],
                self.filter_configs['volume_strict']
            ]),
            ('All filters', [
                self.filter_configs['gap_strict'], 
                self.filter_configs['price_strict'],
                self.filter_configs['volume_strict'],
                self.filter_configs['market_cap']
            ]),
        ]
        
        results = []
        for config_name, filters in progressive_configs:
            if not filters:
                # No filters - return all stocks
                result = {
                    'config_name': config_name,
                    'filter_count': 0,
                    'qualifying_symbols': len(stock_data_list),
                    'pass_rate': 100.0,
                    'symbols': [s.symbol for s in stock_data_list]
                }
            else:
                screen_result = self.screener.screen(
                    stock_data_list=stock_data_list,
                    filters=filters,
                    date_range=(target_date, target_date)
                )
                
                result = {
                    'config_name': config_name,
                    'filter_count': len(filters),
                    'qualifying_symbols': len(screen_result.qualifying_symbols),
                    'pass_rate': (len(screen_result.qualifying_symbols) / len(stock_data_list) * 100) 
                                if stock_data_list else 0,
                    'symbols': screen_result.qualifying_symbols
                }
            
            results.append(result)
        
        return results
    
    def analyze_specific_stock(self, stock_data: StockData, target_date: date) -> Dict[str, Any]:
        """Analyze why a specific stock passes or fails each filter."""
        symbol = stock_data.symbol
        print(f"\nDetailed analysis for {symbol} on {target_date}:")
        
        # Find the bar for target date
        target_bar = None
        prev_bar = None
        
        for i, bar in enumerate(stock_data.bars):
            if bar.date == target_date:
                target_bar = bar
                if i > 0:
                    prev_bar = stock_data.bars[i-1]
                break
        
        if not target_bar:
            return {
                'symbol': symbol,
                'has_target_date': False,
                'analysis': 'No data for target date'
            }
        
        # Calculate metrics
        analysis = {
            'symbol': symbol,
            'has_target_date': True,
            'target_date': target_date,
            'open': target_bar.open,
            'close': target_bar.close,
            'volume': target_bar.volume,
            'filters': {}
        }
        
        # Gap analysis
        if prev_bar:
            gap_percent = ((target_bar.open - prev_bar.close) / prev_bar.close) * 100
            analysis['gap_percent'] = gap_percent
            analysis['filters']['gap_4%'] = gap_percent >= 4.0
            analysis['filters']['gap_2%'] = gap_percent >= 2.0
            analysis['filters']['gap_1%'] = gap_percent >= 1.0
        else:
            analysis['gap_percent'] = 'N/A (no previous day)'
            analysis['filters']['gap_4%'] = False
            analysis['filters']['gap_2%'] = False
            analysis['filters']['gap_1%'] = False
        
        # Price range analysis
        analysis['filters']['price_10-500'] = 10.0 <= target_bar.close <= 500.0
        analysis['filters']['price_1-1000'] = 1.0 <= target_bar.close <= 1000.0
        
        # Volume analysis (relative to 20-day average)
        if len(stock_data.bars) >= 21:
            # Get last 20 days before target
            volumes = []
            for i, bar in enumerate(stock_data.bars):
                if bar.date < target_date:
                    volumes.append(bar.volume)
            
            if len(volumes) >= 20:
                avg_volume = np.mean(volumes[-20:])
                relative_volume = target_bar.volume / avg_volume if avg_volume > 0 else 0
                analysis['relative_volume'] = relative_volume
                analysis['filters']['volume_2x'] = relative_volume >= 2.0
                analysis['filters']['volume_1.5x'] = relative_volume >= 1.5
            else:
                analysis['relative_volume'] = 'N/A (insufficient history)'
                analysis['filters']['volume_2x'] = False
                analysis['filters']['volume_1.5x'] = False
        else:
            analysis['relative_volume'] = 'N/A (insufficient history)'
            analysis['filters']['volume_2x'] = False
            analysis['filters']['volume_1.5x'] = False
        
        return analysis
    
    async def run_comprehensive_test(self):
        """Run comprehensive filter testing."""
        print("Starting comprehensive filter test...")
        print("=" * 80)
        
        all_results = {}
        
        for test_date in self.test_dates:
            print(f"\n\n{'='*80}")
            print(f"TESTING DATE: {test_date}")
            print(f"{'='*80}")
            
            # Fetch data
            stock_data_dict = await self.fetch_data_for_date(test_date)
            if not stock_data_dict:
                print(f"No data available for {test_date}")
                continue
            
            stock_data_list = list(stock_data_dict.values())
            
            # 1. Data availability analysis
            print("\n1. DATA AVAILABILITY ANALYSIS")
            print("-" * 40)
            availability = self.analyze_data_availability(stock_data_dict, test_date)
            
            print(f"{'Symbol':<8} {'Has Data':<10} {'Days':<6} {'Date Range':<25} {'Target':<8} {'Price':<10} {'Volume':<15}")
            print("-" * 90)
            for r in availability:
                print(f"{r['symbol']:<8} {str(r['has_data']):<10} {r['total_days']:<6} {r['date_range']:<25} "
                      f"{str(r['has_target_date']):<8} {r['last_price']:<10} {r['last_volume']:<15}")
            
            # 2. Individual filter tests
            print("\n2. INDIVIDUAL FILTER TESTS")
            print("-" * 40)
            
            filter_results = []
            for filter_name, filter_obj in self.filter_configs.items():
                result = self.test_individual_filter(stock_data_list, filter_obj, filter_name, test_date)
                filter_results.append(result)
            
            # Summary table
            print(f"\n{'Filter':<20} {'Total':<8} {'Pass':<8} {'Rate %':<10} {'Time(ms)':<10}")
            print("-" * 60)
            for r in filter_results:
                print(f"{r['filter_name']:<20} {r['total_symbols']:<8} {r['qualifying_symbols']:<8} "
                      f"{r['pass_rate']:>6.1f}% {r['processing_time_ms']:>8.1f}")
            
            # 3. Progressive filter test
            print("\n3. PROGRESSIVE FILTER TEST")
            print("-" * 40)
            
            progressive_results = self.test_progressive_filters(stock_data_list, test_date)
            
            print(f"\n{'Configuration':<30} {'Filters':<10} {'Passing':<10} {'Rate %':<10} {'Symbols':<40}")
            print("-" * 100)
            for r in progressive_results:
                symbols_str = ', '.join(r['symbols'][:5]) + ('...' if len(r['symbols']) > 5 else '')
                print(f"{r['config_name']:<30} {r['filter_count']:<10} {r['qualifying_symbols']:<10} "
                      f"{r['pass_rate']:>6.1f}% {symbols_str:<40}")
            
            # 4. Specific stock analysis for popular tickers
            print("\n4. DETAILED STOCK ANALYSIS")
            print("-" * 40)
            
            for symbol in ['AAPL', 'TSLA', 'NVDA']:
                if symbol in stock_data_dict:
                    analysis = self.analyze_specific_stock(stock_data_dict[symbol], test_date)
                    if analysis['has_target_date']:
                        print(f"\n{symbol}:")
                        print(f"  Price: ${analysis['open']:.2f} -> ${analysis['close']:.2f}")
                        print(f"  Volume: {analysis['volume']:,}")
                        print(f"  Gap %: {analysis['gap_percent']}")
                        print(f"  Relative Volume: {analysis['relative_volume']}")
                        print(f"  Filter Results:")
                        for filter_name, passed in analysis['filters'].items():
                            print(f"    {filter_name}: {'PASS' if passed else 'FAIL'}")
            
            # Store results
            all_results[test_date] = {
                'availability': availability,
                'filter_results': filter_results,
                'progressive_results': progressive_results
            }
        
        # 5. Final recommendations
        print("\n\n" + "="*80)
        print("ANALYSIS SUMMARY AND RECOMMENDATIONS")
        print("="*80)
        
        print("\n1. DATA ISSUES:")
        print("   - August 1, 2025 is a future date - no real market data exists")
        print("   - Consider using historical dates for testing")
        
        print("\n2. FILTER BOTTLENECKS:")
        print("   - Gap filter (4%) is very restrictive - few stocks gap up 4% daily")
        print("   - Relative volume (2x) requires significant volume spike")
        print("   - Combined filters are too restrictive")
        
        print("\n3. RECOMMENDATIONS:")
        print("   a) Use more lenient filter values:")
        print("      - Gap: 1-2% instead of 4%")
        print("      - Relative Volume: 1.2-1.5x instead of 2x")
        print("   b) Test with historical dates that have real data")
        print("   c) Consider OR logic for some filters instead of AND")
        print("   d) Add more stocks to universe for better results")
        
        return all_results


async def main():
    """Run the comprehensive filter test."""
    tester = FilterTester()
    results = await tester.run_comprehensive_test()
    
    print("\n\nTest completed successfully!")
    return results


if __name__ == "__main__":
    asyncio.run(main())