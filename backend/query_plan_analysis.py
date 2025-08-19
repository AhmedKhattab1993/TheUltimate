#!/usr/bin/env python3
"""
Query Plan Analysis for Enhanced Backtest Results Schema

This script analyzes execution plans to verify index usage and optimization.
"""

import asyncio
import asyncpg
import json
import sys

# Add the app directory to path
sys.path.append('/home/ahmed/TheUltimate/backend')
from app.config import settings


async def analyze_query_plans():
    """Analyze execution plans for key queries."""
    
    try:
        conn = await asyncpg.connect(settings.database_url)
        print("✓ Connected to database")
        
        # Test queries with EXPLAIN ANALYZE
        test_queries = [
            {
                "name": "Cache Key Lookup",
                "query": """
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
                "params": ['AGX', 'MarketStructure', '2025-08-17', '2025-08-17', 100000, 5, '5min']
            },
            {
                "name": "Performance Sorting",
                "query": """
                    SELECT * FROM market_structure_results 
                    ORDER BY total_return DESC, sharpe_ratio DESC 
                    LIMIT 20
                """,
                "params": []
            },
            {
                "name": "Symbol Filtering",
                "query": """
                    SELECT COUNT(*) FROM market_structure_results 
                    WHERE symbol = $1
                """,
                "params": ['AGX']
            },
            {
                "name": "Date Range Query",
                "query": """
                    SELECT * FROM market_structure_results 
                    WHERE created_at >= $1 
                    ORDER BY created_at DESC 
                    LIMIT 50
                """,
                "params": ['2025-08-17']
            },
            {
                "name": "Combined Filters",
                "query": """
                    SELECT * FROM market_structure_results 
                    WHERE symbol = $1 
                      AND total_return > $2 
                      AND sharpe_ratio > $3
                    ORDER BY total_return DESC
                """,
                "params": ['AGX', 0, 0]
            }
        ]
        
        print("\n=== QUERY EXECUTION PLAN ANALYSIS ===")
        
        for test in test_queries:
            print(f"\n--- {test['name']} ---")
            
            # Get execution plan
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {test['query']}"
            
            try:
                if test['params']:
                    result = await conn.fetchrow(explain_query, *test['params'])
                else:
                    result = await conn.fetchrow(explain_query)
                
                if result:
                    plan = result[0][0]  # Extract the plan from JSON result
                    
                    # Extract key information
                    execution_time = plan.get('Execution Time', 0)
                    planning_time = plan.get('Planning Time', 0)
                    
                    print(f"  Execution Time: {execution_time:.3f}ms")
                    print(f"  Planning Time: {planning_time:.3f}ms")
                    
                    # Analyze the plan node
                    def analyze_node(node, level=0):
                        indent = "  " * (level + 1)
                        node_type = node.get('Node Type', 'Unknown')
                        cost = node.get('Total Cost', 0)
                        rows = node.get('Actual Rows', 0)
                        
                        print(f"{indent}{node_type} (cost={cost:.2f}, rows={rows})")
                        
                        # Check for index usage
                        if 'Index Name' in node:
                            print(f"{indent}  → Using Index: {node['Index Name']}")
                        
                        if 'Relation Name' in node:
                            print(f"{indent}  → Table: {node['Relation Name']}")
                        
                        if 'Filter' in node:
                            print(f"{indent}  → Filter: {node['Filter']}")
                        
                        if 'Sort Key' in node:
                            print(f"{indent}  → Sort Key: {node['Sort Key']}")
                        
                        # Recursively analyze child nodes
                        if 'Plans' in node:
                            for child in node['Plans']:
                                analyze_node(child, level + 1)
                    
                    # Analyze the main plan node
                    main_plan = plan.get('Plan', {})
                    analyze_node(main_plan)
                    
                else:
                    print(f"  ✗ No execution plan returned")
                    
            except Exception as e:
                print(f"  ✗ Error analyzing plan: {e}")
        
        # Check index usage statistics
        print("\n=== INDEX USAGE STATISTICS ===")
        
        index_stats = await conn.fetch("""
            SELECT 
                schemaname,
                tablename, 
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes 
            WHERE tablename = 'market_structure_results'
            ORDER BY idx_scan DESC
        """)
        
        print("Index usage since last stats reset:")
        for stat in index_stats:
            print(f"  {stat['indexname']}:")
            print(f"    Scans: {stat['idx_scan']}")
            print(f"    Tuples read: {stat['idx_tup_read']}")
            print(f"    Tuples fetched: {stat['idx_tup_fetch']}")
        
        # Check table statistics
        print("\n=== TABLE STATISTICS ===")
        
        table_stats = await conn.fetchrow("""
            SELECT 
                schemaname,
                tablename,
                n_tup_ins,
                n_tup_upd,
                n_tup_del,
                n_live_tup,
                n_dead_tup,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables 
            WHERE tablename = 'market_structure_results'
        """)
        
        if table_stats:
            print("Table maintenance statistics:")
            print(f"  Live tuples: {table_stats['n_live_tup']}")
            print(f"  Dead tuples: {table_stats['n_dead_tup']}")
            print(f"  Inserts: {table_stats['n_tup_ins']}")
            print(f"  Updates: {table_stats['n_tup_upd']}")
            print(f"  Deletes: {table_stats['n_tup_del']}")
            print(f"  Last analyze: {table_stats['last_analyze']}")
            print(f"  Last autovacuum: {table_stats['last_autovacuum']}")
        
        await conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(analyze_query_plans())