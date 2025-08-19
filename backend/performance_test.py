#!/usr/bin/env python3
"""
Performance Testing Script for Enhanced Backtest Results Schema

This script tests and optimizes query performance for the enhanced backtest results schema,
including measuring response times, analyzing indexes, and providing optimization recommendations.
"""

import asyncio
import asyncpg
import time
import statistics
import json
import sys
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from uuid import uuid4
import aiohttp

# Add the app directory to path so we can import modules
sys.path.append('/home/ahmed/TheUltimate/backend')
from app.config import settings


class PerformanceTester:
    """Performance testing for enhanced backtest results schema."""
    
    def __init__(self):
        self.conn = None
        self.results = {}
        self.test_data_count = 0
        
    async def connect(self):
        """Connect to the database."""
        try:
            self.conn = await asyncpg.connect(settings.database_url)
            print(f"✓ Connected to database: {settings.database_url}")
        except Exception as e:
            print(f"✗ Failed to connect to database: {e}")
            sys.exit(1)
    
    async def disconnect(self):
        """Disconnect from database."""
        if self.conn:
            await self.conn.close()
    
    async def analyze_schema(self):
        """Analyze current database schema and indexes."""
        print("\n=== DATABASE SCHEMA ANALYSIS ===")
        
        # Check if table exists
        table_exists = await self.conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'market_structure_results'
            )
        """)
        
        if not table_exists:
            print("✗ Table 'market_structure_results' does not exist")
            return False
        
        print("✓ Table 'market_structure_results' exists")
        
        # Get table schema
        columns = await self.conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'market_structure_results'
            ORDER BY ordinal_position
        """)
        
        print(f"\nTable has {len(columns)} columns:")
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  {col['column_name']}: {col['data_type']} {nullable}")
        
        # Get existing indexes
        indexes = await self.conn.fetch("""
            SELECT indexname, indexdef, schemaname
            FROM pg_indexes 
            WHERE tablename = 'market_structure_results'
            ORDER BY indexname
        """)
        
        print(f"\nExisting indexes ({len(indexes)}):")
        for idx in indexes:
            print(f"  {idx['indexname']}: {idx['indexdef']}")
        
        # Get table statistics
        stats = await self.conn.fetchrow("""
            SELECT 
                pg_size_pretty(pg_total_relation_size('market_structure_results')) as table_size,
                COUNT(*) as row_count,
                MIN(created_at) as earliest_record,
                MAX(created_at) as latest_record
            FROM market_structure_results
        """)
        
        if stats:
            self.test_data_count = stats['row_count']
            print(f"\nTable statistics:")
            print(f"  Size: {stats['table_size']}")
            print(f"  Row count: {stats['row_count']}")
            print(f"  Date range: {stats['earliest_record']} to {stats['latest_record']}")
        
        return True
    
    async def time_query(self, name: str, query: str, params: List = None, iterations: int = 5) -> Dict[str, Any]:
        """Time a query execution multiple times and return statistics."""
        times = []
        plans = []
        
        for i in range(iterations):
            start_time = time.perf_counter()
            
            try:
                if params:
                    result = await self.conn.fetch(query, *params)
                else:
                    result = await self.conn.fetch(query)
                
                end_time = time.perf_counter()
                execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
                times.append(execution_time)
                
                # Get query plan for the first iteration
                if i == 0:
                    plan_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
                    if params:
                        plan_result = await self.conn.fetchrow(plan_query, *params)
                    else:
                        plan_result = await self.conn.fetchrow(plan_query)
                    plans.append(plan_result[0] if plan_result else None)
                
            except Exception as e:
                print(f"  ✗ Error in {name}: {e}")
                return {"error": str(e)}
        
        return {
            "name": name,
            "iterations": iterations,
            "times_ms": times,
            "avg_time_ms": statistics.mean(times),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "result_count": len(result) if 'result' in locals() else 0,
            "execution_plan": plans[0] if plans else None
        }
    
    async def test_api_endpoint(self, endpoint: str, params: Dict = None, iterations: int = 3) -> Dict[str, Any]:
        """Test API endpoint performance."""
        times = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                start_time = time.perf_counter()
                
                try:
                    url = f"http://localhost:8000{endpoint}"
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            end_time = time.perf_counter()
                            execution_time = (end_time - start_time) * 1000
                            times.append(execution_time)
                        else:
                            return {"error": f"HTTP {response.status}: {await response.text()}"}
                            
                except Exception as e:
                    return {"error": str(e)}
        
        return {
            "endpoint": endpoint,
            "iterations": iterations,
            "times_ms": times,
            "avg_time_ms": statistics.mean(times),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "std_dev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "result_count": len(data.get('results', [])) if 'data' in locals() and data else 0
        }
    
    async def test_basic_queries(self):
        """Test basic query performance scenarios."""
        print("\n=== BASIC QUERY PERFORMANCE TESTS ===")
        
        # Test 1: Simple count query
        result = await self.time_query(
            "Total count",
            "SELECT COUNT(*) FROM market_structure_results"
        )
        self.results["basic_count"] = result
        print(f"✓ Total count: {result.get('avg_time_ms', 0):.2f}ms avg")
        
        # Test 2: Select all columns with limit
        result = await self.time_query(
            "Select all columns (LIMIT 20)",
            "SELECT * FROM market_structure_results ORDER BY created_at DESC LIMIT 20"
        )
        self.results["select_all_limited"] = result
        print(f"✓ Select all (20 rows): {result.get('avg_time_ms', 0):.2f}ms avg")
        
        # Test 3: Select by primary key
        # First get a random ID
        random_id = await self.conn.fetchval(
            "SELECT id FROM market_structure_results ORDER BY RANDOM() LIMIT 1"
        )
        if random_id:
            result = await self.time_query(
                "Select by primary key",
                "SELECT * FROM market_structure_results WHERE id = $1",
                [random_id]
            )
            self.results["select_by_pk"] = result
            print(f"✓ Select by primary key: {result.get('avg_time_ms', 0):.2f}ms avg")
    
    async def test_cache_key_performance(self):
        """Test cache key lookup performance using composite index."""
        print("\n=== CACHE KEY LOOKUP PERFORMANCE ===")
        
        # Get a random record to use for cache key testing
        sample_record = await self.conn.fetchrow("""
            SELECT symbol, strategy_name, start_date, end_date, 
                   initial_cash, pivot_bars, lower_timeframe
            FROM market_structure_results 
            ORDER BY RANDOM() 
            LIMIT 1
        """)
        
        if not sample_record:
            print("✗ No sample data available for cache key testing")
            return
        
        print(f"Testing cache key lookup for: {sample_record['symbol']} / {sample_record['strategy_name']}")
        
        # Test cache key lookup
        result = await self.time_query(
            "Cache key lookup",
            """
            SELECT * FROM market_structure_results
            WHERE symbol = $1 
              AND strategy_name = $2 
              AND start_date = $3 
              AND end_date = $4 
              AND initial_cash = $5 
              AND pivot_bars = $6 
              AND lower_timeframe = $7
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [
                sample_record['symbol'],
                sample_record['strategy_name'],
                sample_record['start_date'],
                sample_record['end_date'],
                sample_record['initial_cash'],
                sample_record['pivot_bars'],
                sample_record['lower_timeframe']
            ]
        )
        self.results["cache_key_lookup"] = result
        print(f"✓ Cache key lookup: {result.get('avg_time_ms', 0):.2f}ms avg")
        
        # Test each component of cache key separately
        cache_components = [
            ("symbol", "symbol = $1", [sample_record['symbol']]),
            ("strategy_name", "strategy_name = $1", [sample_record['strategy_name']]),
            ("date_range", "start_date = $1 AND end_date = $2", 
             [sample_record['start_date'], sample_record['end_date']]),
            ("initial_cash", "initial_cash = $1", [sample_record['initial_cash']]),
            ("pivot_bars", "pivot_bars = $1", [sample_record['pivot_bars']]),
            ("lower_timeframe", "lower_timeframe = $1", [sample_record['lower_timeframe']])
        ]
        
        for component_name, where_clause, params in cache_components:
            result = await self.time_query(
                f"Filter by {component_name}",
                f"SELECT COUNT(*) FROM market_structure_results WHERE {where_clause}",
                params
            )
            self.results[f"filter_{component_name}"] = result
            print(f"✓ Filter by {component_name}: {result.get('avg_time_ms', 0):.2f}ms avg")
    
    async def test_sorting_performance(self):
        """Test sorting performance on various columns."""
        print("\n=== SORTING PERFORMANCE TESTS ===")
        
        sort_tests = [
            ("created_at DESC", "created_at DESC"),
            ("total_return DESC", "total_return DESC"),
            ("sharpe_ratio DESC", "sharpe_ratio DESC"),
            ("max_drawdown ASC", "max_drawdown ASC"),
            ("win_rate DESC", "win_rate DESC"),
            ("profit_factor DESC", "profit_factor DESC")
        ]
        
        for test_name, order_clause in sort_tests:
            result = await self.time_query(
                f"Sort by {test_name}",
                f"SELECT * FROM market_structure_results ORDER BY {order_clause} LIMIT 50",
            )
            self.results[f"sort_{test_name.replace(' ', '_')}"] = result
            print(f"✓ Sort by {test_name}: {result.get('avg_time_ms', 0):.2f}ms avg")
    
    async def test_pagination_performance(self):
        """Test pagination performance with different page sizes and offsets."""
        print("\n=== PAGINATION PERFORMANCE TESTS ===")
        
        page_sizes = [20, 50, 100]
        page_numbers = [1, 10, 50]  # Test different offsets
        
        for page_size in page_sizes:
            for page_num in page_numbers:
                offset = (page_num - 1) * page_size
                
                result = await self.time_query(
                    f"Pagination (page {page_num}, size {page_size})",
                    """
                    SELECT * FROM market_structure_results 
                    ORDER BY created_at DESC 
                    LIMIT $1 OFFSET $2
                    """,
                    [page_size, offset]
                )
                
                test_key = f"pagination_p{page_num}_s{page_size}"
                self.results[test_key] = result
                print(f"✓ Page {page_num}, size {page_size}: {result.get('avg_time_ms', 0):.2f}ms avg")
    
    async def test_filtering_performance(self):
        """Test filtering performance on new schema columns."""
        print("\n=== FILTERING PERFORMANCE TESTS ===")
        
        # Get sample data for realistic filters
        sample_data = await self.conn.fetchrow("""
            SELECT DISTINCT symbol, strategy_name, 
                   MIN(total_return) as min_return,
                   MAX(total_return) as max_return,
                   AVG(sharpe_ratio) as avg_sharpe
            FROM market_structure_results 
            GROUP BY symbol, strategy_name
            LIMIT 1
        """)
        
        if sample_data:
            filter_tests = [
                ("symbol", "symbol = $1", [sample_data['symbol']]),
                ("strategy_name", "strategy_name = $1", [sample_data['strategy_name']]),
                ("positive_returns", "total_return > 0", []),
                ("high_sharpe", "sharpe_ratio > $1", [1.0]),
                ("low_drawdown", "max_drawdown < $1", [10.0]),
                ("date_range", "created_at >= $1", [datetime.now() - timedelta(days=30)]),
                ("combined_filters", 
                 "symbol = $1 AND total_return > $2 AND sharpe_ratio > $3",
                 [sample_data['symbol'], 0, 0.5])
            ]
            
            for test_name, where_clause, params in filter_tests:
                result = await self.time_query(
                    f"Filter: {test_name}",
                    f"SELECT COUNT(*) FROM market_structure_results WHERE {where_clause}",
                    params
                )
                self.results[f"filter_{test_name}"] = result
                print(f"✓ Filter {test_name}: {result.get('avg_time_ms', 0):.2f}ms avg")
    
    async def test_api_endpoints(self):
        """Test API endpoint performance."""
        print("\n=== API ENDPOINT PERFORMANCE TESTS ===")
        
        # Test database-backed endpoints
        api_tests = [
            ("/api/v2/backtest/db/results", {"page": 1, "page_size": 20}),
            ("/api/v2/backtest/db/results", {"page": 1, "page_size": 50}),
            ("/api/v2/backtest/db/results", {"page": 5, "page_size": 20}),
            ("/api/v2/backtest/db/statistics", {}),
        ]
        
        # Get a sample record for cache lookup test
        sample_record = await self.conn.fetchrow("""
            SELECT symbol, strategy_name, start_date, end_date, 
                   initial_cash, pivot_bars, lower_timeframe
            FROM market_structure_results 
            ORDER BY RANDOM() 
            LIMIT 1
        """)
        
        if sample_record:
            api_tests.append((
                "/api/v2/backtest/db/cache-lookup",
                {
                    "symbol": sample_record['symbol'],
                    "strategy_name": sample_record['strategy_name'],
                    "start_date": sample_record['start_date'].isoformat(),
                    "end_date": sample_record['end_date'].isoformat(),
                    "initial_cash": float(sample_record['initial_cash']),
                    "pivot_bars": sample_record['pivot_bars'],
                    "lower_timeframe": sample_record['lower_timeframe']
                }
            ))
        
        for endpoint, params in api_tests:
            result = await self.test_api_endpoint(endpoint, params)
            
            if "error" not in result:
                test_key = f"api_{endpoint.replace('/', '_').replace('-', '_')}"
                self.results[test_key] = result
                print(f"✓ {endpoint}: {result.get('avg_time_ms', 0):.2f}ms avg")
            else:
                print(f"✗ {endpoint}: {result['error']}")
    
    async def analyze_indexes(self):
        """Analyze index usage and effectiveness."""
        print("\n=== INDEX ANALYSIS ===")
        
        # Check index usage statistics
        index_stats = await self.conn.fetch("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes 
            WHERE tablename = 'market_structure_results'
            ORDER BY idx_tup_read DESC
        """)
        
        print("Index usage statistics:")
        for stat in index_stats:
            print(f"  {stat['indexname']}: reads={stat['idx_tup_read']}, fetches={stat['idx_tup_fetch']}")
        
        # Check if composite index exists for cache key
        cache_index_exists = await self.conn.fetchval("""
            SELECT COUNT(*) FROM pg_indexes 
            WHERE tablename = 'market_structure_results' 
            AND indexdef LIKE '%symbol%strategy_name%start_date%end_date%initial_cash%pivot_bars%lower_timeframe%'
        """)
        
        print(f"\nComposite cache index exists: {'Yes' if cache_index_exists > 0 else 'No'}")
        
        # Suggest missing indexes
        await self.suggest_index_optimizations()
    
    async def suggest_index_optimizations(self):
        """Suggest index optimizations based on test results."""
        print("\n=== INDEX OPTIMIZATION SUGGESTIONS ===")
        
        suggestions = []
        
        # Check if cache key composite index exists
        cache_index_exists = await self.conn.fetchval("""
            SELECT COUNT(*) FROM pg_indexes 
            WHERE tablename = 'market_structure_results' 
            AND indexdef LIKE '%symbol%strategy_name%start_date%end_date%initial_cash%pivot_bars%lower_timeframe%'
        """)
        
        if cache_index_exists == 0:
            suggestions.append({
                "priority": "HIGH",
                "type": "CREATE INDEX",
                "description": "Create composite index for cache key lookup",
                "sql": """
CREATE INDEX CONCURRENTLY idx_market_structure_cache_key 
ON market_structure_results (symbol, strategy_name, start_date, end_date, initial_cash, pivot_bars, lower_timeframe);
                """.strip()
            })
        
        # Check for performance-related indexes
        performance_indexes = [
            ("created_at", "Time-based queries and sorting"),
            ("total_return", "Performance sorting"),
            ("sharpe_ratio", "Risk-adjusted return sorting"),
            ("symbol", "Symbol-based filtering"),
            ("strategy_name", "Strategy-based filtering")
        ]
        
        for column, description in performance_indexes:
            index_exists = await self.conn.fetchval(f"""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE tablename = 'market_structure_results' 
                AND indexdef LIKE '%{column}%'
                AND indexname != 'market_structure_results_pkey'
            """)
            
            if index_exists == 0:
                suggestions.append({
                    "priority": "MEDIUM",
                    "type": "CREATE INDEX",
                    "description": f"Create index on {column} for {description}",
                    "sql": f"CREATE INDEX CONCURRENTLY idx_market_structure_{column} ON market_structure_results ({column});"
                })
        
        # Print suggestions
        for suggestion in suggestions:
            print(f"[{suggestion['priority']}] {suggestion['description']}")
            print(f"  SQL: {suggestion['sql']}")
            print()
        
        self.results["optimization_suggestions"] = suggestions
    
    async def generate_performance_report(self):
        """Generate a comprehensive performance report."""
        print("\n=== PERFORMANCE REPORT ===")
        
        # Calculate overall statistics
        query_times = []
        api_times = []
        
        for key, result in self.results.items():
            if isinstance(result, dict) and "avg_time_ms" in result:
                if key.startswith("api_"):
                    api_times.append(result["avg_time_ms"])
                else:
                    query_times.append(result["avg_time_ms"])
        
        # Performance summary
        print("Performance Summary:")
        if query_times:
            print(f"  Database queries: {len(query_times)} tests")
            print(f"    Average response time: {statistics.mean(query_times):.2f}ms")
            print(f"    Fastest query: {min(query_times):.2f}ms")
            print(f"    Slowest query: {max(query_times):.2f}ms")
        
        if api_times:
            print(f"  API endpoints: {len(api_times)} tests")
            print(f"    Average response time: {statistics.mean(api_times):.2f}ms")
            print(f"    Fastest endpoint: {min(api_times):.2f}ms")
            print(f"    Slowest endpoint: {max(api_times):.2f}ms")
        
        # Performance thresholds
        print("\nPerformance Assessment:")
        slow_queries = [k for k, v in self.results.items() 
                       if isinstance(v, dict) and v.get("avg_time_ms", 0) > 1000]
        
        if slow_queries:
            print(f"  ⚠️  {len(slow_queries)} slow queries (>1000ms):")
            for query in slow_queries:
                print(f"    - {query}: {self.results[query]['avg_time_ms']:.2f}ms")
        else:
            print("  ✓ All queries perform well (<1000ms)")
        
        # Cache performance
        cache_lookup_time = self.results.get("cache_key_lookup", {}).get("avg_time_ms", 0)
        if cache_lookup_time:
            if cache_lookup_time < 100:
                print(f"  ✓ Cache lookup excellent: {cache_lookup_time:.2f}ms")
            elif cache_lookup_time < 500:
                print(f"  ✓ Cache lookup good: {cache_lookup_time:.2f}ms")
            else:
                print(f"  ⚠️  Cache lookup needs optimization: {cache_lookup_time:.2f}ms")
        
        # Data volume assessment
        print(f"\nData Volume: {self.test_data_count:,} records")
        if self.test_data_count < 1000:
            print("  ⚠️  Low data volume - performance may improve with more data")
        elif self.test_data_count > 100000:
            print("  ✓ Good data volume for performance testing")
        
        # Save detailed report
        report = {
            "timestamp": datetime.now().isoformat(),
            "test_data_count": self.test_data_count,
            "performance_results": self.results,
            "summary": {
                "total_tests": len([k for k, v in self.results.items() 
                                  if isinstance(v, dict) and "avg_time_ms" in v]),
                "avg_query_time_ms": statistics.mean(query_times) if query_times else 0,
                "avg_api_time_ms": statistics.mean(api_times) if api_times else 0,
                "slow_queries": slow_queries,
                "cache_lookup_time_ms": cache_lookup_time
            }
        }
        
        # Write report to file
        report_file = f"/home/ahmed/TheUltimate/backend/performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\nDetailed report saved to: {report_file}")
        
        return report
    
    async def run_all_tests(self):
        """Run all performance tests."""
        print("🚀 Starting Enhanced Backtest Results Schema Performance Testing")
        print("=" * 70)
        
        try:
            await self.connect()
            
            # Analyze current schema
            schema_ok = await self.analyze_schema()
            if not schema_ok:
                return
            
            # Run performance tests
            await self.test_basic_queries()
            await self.test_cache_key_performance()
            await self.test_sorting_performance()
            await self.test_pagination_performance()
            await self.test_filtering_performance()
            await self.test_api_endpoints()
            
            # Analyze indexes
            await self.analyze_indexes()
            
            # Generate final report
            report = await self.generate_performance_report()
            
            print("\n🎉 Performance testing completed successfully!")
            
            return report
            
        except Exception as e:
            print(f"\n❌ Performance testing failed: {e}")
            raise
        finally:
            await self.disconnect()


async def main():
    """Main entry point for performance testing."""
    tester = PerformanceTester()
    
    try:
        report = await tester.run_all_tests()
        
        # Return success exit code
        sys.exit(0)
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())