#!/usr/bin/env python3
"""
Debug grid backtest results processing.
"""

import asyncio
import json
from pathlib import Path
from app.services.grid_backtest_manager import GridBacktestManager
import asyncpg
from app.config import settings

async def debug_results():
    # Create database pool
    db_pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=5,
        max_size=20
    )
    
    try:
        manager = GridBacktestManager(db_pool)
        
        # Simulate a result from the parallel backtest queue
        mock_result = {
            'symbol': 'TEST',
            'success': True,
            'status': 'completed',
            'statistics': {
                'Total Return [%]': 5.25,
                'Sharpe Ratio': 1.2,
                'Max Drawdown [%]': 3.5,
                'Win Rate [%]': 60.0,
                'Profit-Loss Ratio': 1.5,
                'Total Trades': 10
            }
        }
        
        # Try to save it
        from datetime import date
        await manager._save_backtest_result(
            symbol='TEST',
            date=date(2025, 9, 10),
            pivot_bars=5,
            result=mock_result
        )
        
        print("Mock result saved successfully")
        
        # Check if it was saved
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM grid_market_structure 
                WHERE symbol = 'TEST' AND backtest_date = '2025-09-10'
            """)
            print(f"Records found: {count}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await db_pool.close()

if __name__ == "__main__":
    asyncio.run(debug_results())