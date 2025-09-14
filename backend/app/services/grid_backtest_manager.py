"""
Grid Backtest Manager Service

Manages parallel backtests for grid analysis, running different parameter
combinations for all screened symbols.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
import asyncpg
from decimal import Decimal

from .parallel_backtest_queue_manager import ParallelBacktestQueueManager
from .cache_service import CacheService
from ..config import settings

logger = logging.getLogger(__name__)


class GridBacktestManager:
    """Manages backtests for grid parameter analysis."""
    
    def __init__(self, db_pool: asyncpg.Pool, max_parallel: int = 10):
        self.db_pool = db_pool
        self.max_parallel = max_parallel
        self.cache_service = None  # Disable caching for grid analysis
        
        # Define parameter grid
        self.pivot_bars_values = [1, 2, 3, 5, 10, 20]
        self.lower_timeframe = 1  # Fixed at 1 minute (stored as integer)
        self.lower_timeframe_str = "1min"  # String format for backtest
        self.resolution = "Daily"
        self.initial_cash = 100000
        self.strategy_name = "MarketStructure"
        
    async def run_backtests_for_date(self, process_date: date) -> Dict[str, Any]:
        """
        Run backtests for all screened symbols on a given date.
        
        Args:
            process_date: Date to run backtests for
            
        Returns:
            Dictionary with processing statistics
        """
        start_time = time.time()
        
        # Get symbols from grid_screening table for this date
        symbols = await self._get_screened_symbols(process_date)
        
        if not symbols:
            logger.info(f"No screened symbols found for {process_date}")
            return {
                'date': process_date,
                'total_symbols': 0,
                'total_backtests': 0,
                'completed': 0,
                'failed': 0,
                'duration_seconds': time.time() - start_time
            }
        
        logger.info(f"Found {len(symbols)} screened symbols for {process_date}")
        
        # Check existing backtests to avoid duplicates
        existing_backtests = await self._get_existing_backtests(process_date)
        
        # Create backtest configs for all parameter combinations
        backtest_configs = []
        for symbol in symbols:
            for pivot_bars in self.pivot_bars_values:
                # Create unique key for this combination
                combo_key = f"{symbol}_{pivot_bars}"
                
                # Skip if already processed
                if combo_key in existing_backtests:
                    continue
                
                # Create backtest config
                config = {
                    'backtest_id': str(uuid.uuid4()),
                    'symbol': symbol,
                    'start_date': process_date.isoformat(),
                    'end_date': process_date.isoformat(),
                    'initial_cash': self.initial_cash,
                    'strategy_name': self.strategy_name,
                    'resolution': self.resolution,
                    'parameters': {
                        'pivot_bars': pivot_bars,
                        'lower_timeframe': self.lower_timeframe_str
                    }
                }
                backtest_configs.append(config)
        
        if not backtest_configs:
            logger.info(f"All backtests already completed for {process_date}")
            return {
                'date': process_date,
                'total_symbols': len(symbols),
                'total_backtests': len(symbols) * len(self.pivot_bars_values),
                'already_processed': len(existing_backtests),
                'completed': 0,
                'failed': 0,
                'duration_seconds': time.time() - start_time
            }
        
        logger.info(f"Running {len(backtest_configs)} backtests for {process_date}")
        logger.info(f"Sample backtest config: {backtest_configs[0] if backtest_configs else 'None'}")
        
        # Create grid session ID for tracking
        grid_session_id = uuid.uuid4()
        
        # Initialize the queue manager
        queue_manager = ParallelBacktestQueueManager(
            max_parallel=self.max_parallel,
            cache_service=None,  # Disable caching for grid analysis
            enable_storage=False,  # We'll handle storage ourselves
            enable_cleanup=True,
            screener_session_id=grid_session_id,
            bulk_id=f"grid_{process_date}"
        )
        logger.info(f"Queue manager initialized with max_parallel={self.max_parallel}")
        logger.info(f"TESTING_MODE setting: {getattr(settings, 'TESTING_MODE', 'Not set')}")
        
        
        # Process all backtests
        try:
            # Modify configs to have unique identifiers including pivot_bars
            modified_configs = []
            for config in backtest_configs:
                # Create a modified config with a composite symbol that includes pivot_bars
                pivot_bars = config['parameters']['pivot_bars']
                modified_config = {
                    **config,
                    'original_symbol': config['symbol'],
                    'symbol': f"{config['symbol']}_pb{pivot_bars}"  # Make symbol unique per pivot_bars
                }
                modified_configs.append(modified_config)
            
            # Run all backtests
            logger.info(f"Starting queue_manager.run_batch() with {len(modified_configs)} configs")
            results = await queue_manager.run_batch(modified_configs)
            logger.info(f"Queue batch completed. Got {len(results)} results")
            logger.info(f"Result keys: {list(results.keys()) if results else 'No results'}")
            
            # Process results
            completed_count = 0
            failed_count = 0
            
            for composite_symbol, result in results.items():
                # Extract original symbol and pivot_bars from composite symbol
                if '_pb' in composite_symbol:
                    original_symbol = composite_symbol.split('_pb')[0]
                    pivot_bars_str = composite_symbol.split('_pb')[1]
                    pivot_bars = int(pivot_bars_str)
                else:
                    # Fallback
                    original_symbol = composite_symbol
                    pivot_bars = 5  # Default
                
                logger.info(f"Processing result for {composite_symbol} -> {original_symbol} (pivot_bars={pivot_bars})")
                logger.info(f"Result type: {type(result)}, Result: {result}")
                
                if isinstance(result, dict) and (result.get('success') or result.get('status') == 'completed'):
                    completed_count += 1
                    # Fix the symbol in the result
                    result['symbol'] = original_symbol
                    logger.info(f"SUCCESS: Saving result for {original_symbol} with pivot_bars={pivot_bars}")
                    logger.info(f"Result keys: {list(result.keys())}")
                    if 'statistics' in result:
                        logger.info(f"Statistics type: {type(result['statistics'])}")
                        logger.info(f"Statistics content: {result['statistics']}")
                    await self._save_backtest_result(
                        symbol=original_symbol,
                        date=process_date,
                        pivot_bars=pivot_bars,
                        result=result
                    )
                else:
                    failed_count += 1
                    error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else str(result)
                    logger.error(f"FAILED: Backtest failed for {original_symbol} (pivot_bars={pivot_bars}): {error_msg}")
                    logger.error(f"Full result: {result}")
                
                # Log progress
                total_processed = completed_count + failed_count
                if total_processed % 10 == 0:
                    logger.info(f"Progress: {total_processed}/{len(backtest_configs)} "
                              f"({completed_count} completed, {failed_count} failed)")
            
            # Final statistics
            duration = time.time() - start_time
            logger.info(f"Completed {len(backtest_configs)} backtests in {duration:.2f} seconds")
            logger.info(f"Success: {completed_count}, Failed: {failed_count}")
            
            return {
                'date': process_date,
                'total_symbols': len(symbols),
                'total_backtests': len(backtest_configs),
                'already_processed': len(existing_backtests),
                'completed': completed_count,
                'failed': failed_count,
                'duration_seconds': duration,
                'throughput': len(backtest_configs) / duration if duration > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error processing backtests: {e}")
            raise
    
    async def _get_screened_symbols(self, process_date: date) -> List[str]:
        """Get symbols that have been screened for the given date."""
        try:
            async with self.db_pool.acquire() as conn:
                # Check if testing mode is enabled
                if settings.TESTING_MODE:
                    # Use only testing symbols that have been screened
                    query = """
                    SELECT DISTINCT symbol 
                    FROM grid_screening 
                    WHERE date = $1 
                        AND symbol = ANY($2::text[])
                    ORDER BY symbol
                    """
                    rows = await conn.fetch(query, process_date, settings.TESTING_SYMBOLS)
                    symbols = [row['symbol'] for row in rows]
                    logger.info(f"Testing mode: Found {len(symbols)} screened symbols from testing list")
                    return symbols
                
                # Normal mode - get all screened symbols
                query = """
                SELECT DISTINCT symbol 
                FROM grid_screening 
                WHERE date = $1 
                ORDER BY symbol
                """
                rows = await conn.fetch(query, process_date)
                return [row['symbol'] for row in rows]
        except Exception as e:
            logger.error(f"Error getting screened symbols: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Date parameter: {process_date}")
            raise
    
    async def _get_existing_backtests(self, process_date: date) -> Set[str]:
        """Get existing backtest combinations for this date."""
        async with self.db_pool.acquire() as conn:
            query = """
            SELECT symbol, pivot_bars 
            FROM grid_market_structure 
            WHERE backtest_date = $1
            """
            rows = await conn.fetch(query, process_date)
            return set(f"{row['symbol']}_{row['pivot_bars']}" for row in rows)
    
    async def _save_backtest_result(self, symbol: str, date: date, 
                                   pivot_bars: int, result: Dict[str, Any]) -> None:
        """Save backtest result to grid_market_structure table."""
        try:
            logger.info(f"SAVE: Saving backtest result for {symbol}, date={date}, pivot_bars={pivot_bars}")
            logger.info(f"SAVE: Full result dict: {result}")
            
            # The result should have statistics already
            # For cached results, statistics are in the result dict
            backtest_id = result.get('backtest_id', result.get('cache_id'))
            stats = result.get('statistics', {})
            
            logger.info(f"SAVE: Stats extracted: {stats}")
            logger.info(f"SAVE: Stats type: {type(stats)}")
            
            # Calculate key metrics - handle both formats
            total_return = stats.get('total_return', stats.get('Total Return [%]', 0))
            sharpe_ratio = stats.get('sharpe_ratio', stats.get('Sharpe Ratio', 0))
            max_drawdown = stats.get('max_drawdown', stats.get('Max Drawdown [%]', 0))
            win_rate = stats.get('win_rate', stats.get('Win Rate [%]', 0))
            profit_loss_ratio = stats.get('profit_loss_ratio', stats.get('Profit-Loss Ratio', 0))
            total_trades = stats.get('total_trades', stats.get('Total Trades', 0))
            
            logger.info(f"SAVE: Calculated metrics - total_return: {total_return}, sharpe: {sharpe_ratio}, trades: {total_trades}")
            
            # Get equity curve data if available
            equity_curve = result.get('equity_curve', {})
            final_equity = equity_curve.get('final_value', self.initial_cash)
            
            # Log the SQL parameters
            logger.info(f"SAVE: SQL parameters:")
            logger.info(f"  symbol: {symbol}")
            logger.info(f"  date: {date}")
            logger.info(f"  pivot_bars: {pivot_bars}")
            logger.info(f"  lower_timeframe: {self.lower_timeframe}")
            logger.info(f"  total_return: {total_return}")
            logger.info(f"  sharpe_ratio: {sharpe_ratio}")
            logger.info(f"  max_drawdown: {max_drawdown}")
            logger.info(f"  win_rate: {win_rate}")
            logger.info(f"  profit_factor: {profit_loss_ratio}")
            logger.info(f"  total_trades: {total_trades}")
            logger.info(f"  statistics length: {len(json.dumps(stats)) if stats else 0}")
            
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO grid_market_structure (
                        symbol, backtest_date, pivot_bars, lower_timeframe,
                        total_return, sharpe_ratio, max_drawdown,
                        win_rate, profit_factor, total_trades, statistics
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (symbol, backtest_date, pivot_bars) DO UPDATE SET
                        lower_timeframe = EXCLUDED.lower_timeframe,
                        total_return = EXCLUDED.total_return,
                        sharpe_ratio = EXCLUDED.sharpe_ratio,
                        max_drawdown = EXCLUDED.max_drawdown,
                        win_rate = EXCLUDED.win_rate,
                        profit_factor = EXCLUDED.profit_factor,
                        total_trades = EXCLUDED.total_trades,
                        statistics = EXCLUDED.statistics,
                        created_at = NOW()
                """, symbol, date, pivot_bars, self.lower_timeframe,
                    total_return, sharpe_ratio, max_drawdown,
                    win_rate, profit_loss_ratio, total_trades, 
                    json.dumps(stats) if stats else None)
                
                logger.info(f"SAVE: Successfully saved backtest result for {symbol} on {date} with pivot_bars={pivot_bars}")
                
                # Verify the save by reading it back
                row = await conn.fetchrow("""
                    SELECT total_return, sharpe_ratio, total_trades, statistics
                    FROM grid_market_structure
                    WHERE symbol = $1 AND backtest_date = $2 AND pivot_bars = $3
                """, symbol, date, pivot_bars)
                
                if row:
                    logger.info(f"SAVE VERIFY: Read back from DB:")
                    logger.info(f"  total_return: {row['total_return']}")
                    logger.info(f"  sharpe_ratio: {row['sharpe_ratio']}")
                    logger.info(f"  total_trades: {row['total_trades']}")
                    logger.info(f"  statistics: {'present' if row['statistics'] else 'null'}")
                else:
                    logger.error(f"SAVE VERIFY: Could not read back saved record!")
                
                # Save trades if available
                trades = result.get('trades', [])
                if trades:
                    await self._save_backtest_trades(symbol, date, pivot_bars, trades)
                
        except Exception as e:
            logger.error(f"Error saving backtest result for {symbol}: {e}")
    
    async def _save_backtest_trades(self, symbol: str, date: date, pivot_bars: int, 
                                   trades: List[Dict[str, Any]]) -> None:
        """Save backtest trades to grid_market_structure_trades table."""
        try:
            from zoneinfo import ZoneInfo
            from datetime import datetime
            
            if not trades:
                logger.info(f"No trades to save for {symbol} on {date} with pivot_bars={pivot_bars}")
                return
            
            # Prepare batch insert data
            insert_data = []
            eastern_tz = ZoneInfo('America/New_York')
            
            for trade in trades:
                # Convert unix timestamp to Eastern Time
                unix_timestamp = float(trade.get('trade_time', 0))
                trade_time_utc = datetime.fromtimestamp(unix_timestamp, tz=ZoneInfo('UTC'))
                trade_time_eastern = trade_time_utc.astimezone(eastern_tz)
                
                # Calculate position metrics if available
                fill_price = float(trade.get('fill_price', 0))
                fill_quantity = float(trade.get('fill_quantity', 0))
                position_value = fill_price * abs(fill_quantity)
                
                # Determine trade type based on message or pattern
                message = trade.get('message', '')
                trade_type = 'entry'
                signal_reason = ''
                
                if 'liquidat' in message.lower():
                    trade_type = 'exit'
                    signal_reason = 'MARKET_CLOSE'
                elif 'flip' in message.lower() or 'revers' in message.lower():
                    trade_type = 'reversal'
                    signal_reason = 'BOS_REVERSAL'
                elif 'bullish' in message.lower() or 'long' in message.lower():
                    signal_reason = 'BOS_BULLISH'
                elif 'bearish' in message.lower() or 'short' in message.lower():
                    signal_reason = 'BOS_BEARISH'
                
                insert_data.append((
                    symbol,
                    date,
                    pivot_bars,
                    trade_time_eastern,
                    trade.get('direction', ''),
                    abs(int(trade.get('quantity', 0))),
                    fill_price,
                    abs(int(fill_quantity)),
                    float(trade.get('order_fee', 0)),
                    None,  # profit_loss (calculated later if needed)
                    None,  # profit_loss_percent
                    abs(int(fill_quantity)),  # position_size
                    position_value,
                    trade.get('order_id', ''),
                    trade.get('order_type', 'market'),
                    trade_type,
                    signal_reason
                ))
            
            # Batch insert trades
            async with self.db_pool.acquire() as conn:
                await conn.executemany("""
                    INSERT INTO grid_market_structure_trades (
                        symbol, backtest_date, pivot_bars,
                        trade_time, direction, quantity, fill_price, fill_quantity,
                        order_fee, profit_loss, profit_loss_percent,
                        position_size, position_value, order_id, order_type,
                        trade_type, signal_reason
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                """, insert_data)
                
                logger.info(f"Saved {len(insert_data)} trades for {symbol} on {date} with pivot_bars={pivot_bars}")
        
        except Exception as e:
            logger.error(f"Error saving trades for {symbol}: {e}")
            # Don't fail the whole save if trade save fails