"""
Service for storing and retrieving backtest results.
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, List
import asyncpg
import os
from zoneinfo import ZoneInfo

from ..models.backtest import (
    BacktestResult, BacktestStatistics, BacktestListResponse
)


logger = logging.getLogger(__name__)


class BacktestStorage:
    """Manages storage and retrieval of backtest results."""
    
    def __init__(self, results_base_path: str = "/home/ahmed/TheUltimate/backend/lean/test-project/backtests", strategy_name: Optional[str] = None):
        # Store strategy name for use in reconstruction
        self.strategy_name = strategy_name
        
        # If strategy name is provided, use strategy-specific path
        if strategy_name:
            self.results_base_path = Path(f"/home/ahmed/TheUltimate/backend/lean/{strategy_name}/backtests")
        else:
            self.results_base_path = Path(results_base_path)
        self.results_base_path.mkdir(parents=True, exist_ok=True)
        
    async def save_result(self, 
                         backtest_id: str,
                         symbol: str,
                         strategy_name: str,
                         start_date: date,
                         end_date: date,
                         initial_cash: float,
                         result_path: str) -> Optional[BacktestResult]:
        """
        Save a completed backtest result.
        
        Args:
            backtest_id: Unique identifier for the backtest
            symbol: Symbol that was backtested
            strategy_name: Name of the strategy tested
            start_date: Backtest start date
            end_date: Backtest end date
            initial_cash: Initial cash amount
            result_path: Path to the LEAN result files
            
        Returns:
            BacktestResult if successful, None otherwise
        """
        try:
            result_dir = Path(result_path)
            
            # Find the summary file which contains statistics
            summary_file = None
            for f in result_dir.glob("*-summary.json"):
                summary_file = f
                break
            
            if not summary_file or not summary_file.exists():
                # Fallback to main result file
                for f in result_dir.glob("*.json"):
                    if f.stem.isdigit():
                        summary_file = f
                        break
            
            if not summary_file or not summary_file.exists():
                logger.error(f"No result file found in {result_path}")
                return None
            
            # Read LEAN results
            with open(summary_file, 'r') as f:
                lean_result = json.load(f)
            
            # Extract statistics - map LEAN statistics names to our model fields
            stats_data = lean_result.get("statistics", {})
            if not stats_data:
                # Try uppercase for backward compatibility
                stats_data = lean_result.get("Statistics", {})
            
            # Parse currency values by removing $ and commas
            def parse_currency(value):
                if isinstance(value, str):
                    # Handle negative values with $ sign
                    value = value.replace('$', '').replace(',', '')
                    if value.startswith('-') and not value[1:].replace('.', '').replace('-', '').isdigit():
                        # Handle format like "$-23,603.13" parsed as "-23,603.13"
                        value = '-' + value[1:].replace('-', '')
                    return float(value)
                elif isinstance(value, (int, float)):
                    return float(value)
                return float(value or 0)
            
            # Get runtime statistics for currency values
            runtime_stats = lean_result.get("runtimeStatistics", {})
            
            # Get trade statistics for more detailed metrics
            trade_stats = lean_result.get("totalPerformance", {}).get("tradeStatistics", {})
            portfolio_stats = lean_result.get("totalPerformance", {}).get("portfolioStatistics", {})
            
            statistics = BacktestStatistics(
                # Core Performance Metrics
                total_return=self._parse_percentage(runtime_stats.get("Return", stats_data.get("Total Return", "0%"))),
                net_profit=float(portfolio_stats.get("totalNetProfit", 0)) * 100 if portfolio_stats.get("totalNetProfit") else self._parse_percentage(stats_data.get("Net Profit", "0%")),
                net_profit_currency=parse_currency(runtime_stats.get("Net Profit", "$0")),
                compounding_annual_return=float(portfolio_stats.get("compoundingAnnualReturn", 0)) * 100 if portfolio_stats.get("compoundingAnnualReturn") else self._parse_percentage(stats_data.get("Compounding Annual Return", "0%")),
                final_value=parse_currency(portfolio_stats.get("endEquity", stats_data.get("End Equity", runtime_stats.get("Equity", initial_cash)))),
                start_equity=parse_currency(portfolio_stats.get("startEquity", stats_data.get("Start Equity", initial_cash))),
                end_equity=parse_currency(portfolio_stats.get("endEquity", stats_data.get("End Equity", initial_cash))),
                
                # Risk Metrics - Use trade statistics if portfolio statistics are zero
                sharpe_ratio=float(trade_stats.get("sharpeRatio", stats_data.get("Sharpe Ratio", 0))) if self._parse_numeric(stats_data.get("Sharpe Ratio", 0)) == 0 else self._parse_numeric(stats_data.get("Sharpe Ratio", 0)),
                sortino_ratio=float(trade_stats.get("sortinoRatio", stats_data.get("Sortino Ratio", 0))) if self._parse_numeric(stats_data.get("Sortino Ratio", 0)) == 0 else self._parse_numeric(stats_data.get("Sortino Ratio", 0)),
                max_drawdown=abs(float(trade_stats.get("maximumClosedTradeDrawdown", 0)) / initial_cash * 100) if trade_stats.get("maximumClosedTradeDrawdown") and self._parse_numeric(stats_data.get("Drawdown", 0)) == 0 else (abs(float(portfolio_stats.get("drawdown", 0))) * -100 if portfolio_stats.get("drawdown") else abs(self._parse_percentage(stats_data.get("Drawdown", "0%"))) * -1),
                probabilistic_sharpe_ratio=self._parse_percentage(stats_data.get("Probabilistic Sharpe Ratio", "0%")),
                annual_standard_deviation=self._parse_numeric(stats_data.get("Annual Standard Deviation", 0)),
                annual_variance=self._parse_numeric(stats_data.get("Annual Variance", 0)),
                beta=self._parse_numeric(stats_data.get("Beta", 0)),
                alpha=self._parse_numeric(stats_data.get("Alpha", 0)),
                
                # Trading Statistics
                total_orders=int(stats_data.get("Total Orders", 0)),
                total_trades=int(trade_stats.get("totalNumberOfTrades", stats_data.get("Total Trades", 0))),
                winning_trades=int(trade_stats.get("numberOfWinningTrades", 0)),
                losing_trades=int(trade_stats.get("numberOfLosingTrades", 0)),
                win_rate=float(trade_stats.get("winRate", 0)) * 100 if trade_stats.get("winRate") else self._parse_percentage(stats_data.get("Win Rate", "0%")),
                loss_rate=float(trade_stats.get("lossRate", 0)) * 100 if trade_stats.get("lossRate") else self._parse_percentage(stats_data.get("Loss Rate", "0%")),
                average_win=self._parse_percentage(stats_data.get("Average Win", "0%")),
                average_loss=self._parse_percentage(stats_data.get("Average Loss", "0%")),
                profit_factor=float(trade_stats.get("profitFactor", stats_data.get("Profit Factor", 0))) if stats_data.get("Profit Factor", "0") == "0" else self._parse_numeric(stats_data.get("Profit Factor", 0)),
                profit_loss_ratio=float(trade_stats.get("profitLossRatio", stats_data.get("Profit-Loss Ratio", 0))) if stats_data.get("Profit-Loss Ratio", "0") == "0" else self._parse_numeric(stats_data.get("Profit-Loss Ratio", 0)),
                expectancy=self._parse_numeric(stats_data.get("Expectancy", 0)),
                
                # Advanced Metrics
                information_ratio=self._parse_numeric(stats_data.get("Information Ratio", 0)),
                tracking_error=self._parse_numeric(stats_data.get("Tracking Error", 0)),
                treynor_ratio=self._parse_numeric(stats_data.get("Treynor Ratio", 0)),
                total_fees=parse_currency(stats_data.get("Total Fees", "$0")),
                estimated_strategy_capacity=parse_currency(stats_data.get("Estimated Strategy Capacity", "$0")),
                lowest_capacity_asset=stats_data.get("Lowest Capacity Asset", ""),
                portfolio_turnover=self._parse_percentage(stats_data.get("Portfolio Turnover", "0%"))
            )
            
            # Extract final portfolio value
            final_value = statistics.end_equity if statistics.end_equity > 0 else initial_cash
            
            # Extract orders/trades
            orders = []
            # Find order events file
            order_events_file = None
            for f in result_dir.glob("*-order-events.json"):
                order_events_file = f
                break
            if order_events_file.exists():
                try:
                    with open(order_events_file, 'r') as f:
                        order_events = json.load(f)
                        # Order events is an array, not an object
                        if isinstance(order_events, list):
                            orders = order_events  # Return all orders
                        else:
                            orders = order_events.get("Orders", [])
                except Exception as e:
                    logger.warning(f"Could not load order events: {e}")
            
            # Extract equity curve from charts (lowercase)
            equity_curve = []
            charts_data = lean_result.get("charts", {})
            if not charts_data:
                # Try uppercase for backward compatibility 
                charts_data = lean_result.get("Charts", {})
            
            if charts_data and "Strategy Equity" in charts_data:
                strategy_equity = charts_data["Strategy Equity"]
                if "series" in strategy_equity:
                    series_data = strategy_equity["series"]
                    if "Equity" in series_data and "values" in series_data["Equity"]:
                        # Values are in OHLC format: [timestamp, open, high, low, close]
                        for point in series_data["Equity"]["values"]:
                            if isinstance(point, list) and len(point) >= 5:
                                timestamp = point[0]
                                close_value = point[4]  # Use closing value
                                equity_curve.append({
                                    "time": timestamp,
                                    "value": close_value
                                })
            
            # Create result object
            result = BacktestResult(
                backtest_id=backtest_id,
                symbol=symbol,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                resolution="Daily",  # Default resolution
                pivot_bars=20,  # Default pivot bars
                lower_timeframe="5min",  # Default lower timeframe
                final_value=final_value,
                statistics=statistics,
                orders=orders,
                equity_curve=equity_curve[:1000],  # Limit curve points
                created_at=datetime.now(),
                result_path=result_path
            )
            
            # Save metadata for quick retrieval
            metadata_file = result_dir / "backtest_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(result.model_dump(), f, indent=2, default=str)
            
            logger.info(f"Saved backtest result {backtest_id} to {result_path}")
            
            # Save trades to database if we have orders
            if orders:
                await self._save_trades_to_database(backtest_id, orders)
            
            return result
            
        except Exception as e:
            logger.error(f"Error saving backtest result: {e}")
            return None
    
    async def get_result(self, timestamp: str) -> Optional[BacktestResult]:
        """
        Retrieve a specific backtest result by timestamp.
        
        Args:
            timestamp: Timestamp folder name (e.g., "2025-08-10_05-09-01")
            
        Returns:
            BacktestResult if found, None otherwise
        """
        try:
            result_dir = self.results_base_path / timestamp
            if not result_dir.exists():
                return None
            
            # First try to load from metadata file
            metadata_file = result_dir / "backtest_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                    
                # Convert string dates back to date objects
                data['start_date'] = datetime.fromisoformat(data['start_date']).date()
                data['end_date'] = datetime.fromisoformat(data['end_date']).date()
                data['created_at'] = datetime.fromisoformat(data['created_at'])
                
                return BacktestResult(**data)
            
            # Otherwise try to reconstruct from LEAN files
            # This is a fallback for older results
            return await self._reconstruct_result_from_lean(result_dir)
            
        except Exception as e:
            logger.error(f"Error retrieving backtest result: {e}")
            return None
    
    async def list_results(self, 
                          page: int = 1,
                          page_size: int = 20,
                          strategy_name: Optional[str] = None) -> BacktestListResponse:
        """
        List all backtest results with pagination.
        
        Args:
            page: Page number (1-based)
            page_size: Number of results per page
            strategy_name: Filter by strategy name
            
        Returns:
            BacktestListResponse with paginated results
        """
        try:
            all_results = []
            
            # Iterate through all result directories
            for result_dir in sorted(self.results_base_path.iterdir(), reverse=True):
                if not result_dir.is_dir():
                    continue
                
                # Try to load result
                result = await self.get_result(result_dir.name)
                if result:
                    if strategy_name is None or result.strategy_name == strategy_name:
                        all_results.append(result)
            
            # Apply pagination
            total_count = len(all_results)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_results = all_results[start_idx:end_idx]
            
            return BacktestListResponse(
                results=paginated_results,
                total_count=total_count,
                page=page,
                page_size=page_size
            )
            
        except Exception as e:
            logger.error(f"Error listing backtest results: {e}")
            return BacktestListResponse(
                results=[],
                total_count=0,
                page=page,
                page_size=page_size
            )
    
    async def delete_result(self, timestamp: str) -> bool:
        """
        Delete a backtest result.
        
        Args:
            timestamp: Timestamp folder name
            
        Returns:
            True if deleted successfully
        """
        try:
            result_dir = self.results_base_path / timestamp
            if result_dir.exists():
                import shutil
                shutil.rmtree(result_dir)
                logger.info(f"Deleted backtest result at {timestamp}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting backtest result: {e}")
            return False
    
    def _parse_percentage(self, value: str) -> float:
        """Parse percentage string to float."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # Remove percentage sign and whitespace
                cleaned = value.strip().rstrip('%').strip()
                # Handle empty string after cleaning
                if not cleaned or cleaned == '':
                    return 0.0
                return float(cleaned)
            except ValueError:
                logger.warning(f"Could not parse percentage value: {value}")
                return 0.0
        return 0.0
    
    def _parse_numeric(self, value: Any, default: float = 0.0) -> float:
        """Parse a numeric value that might be a string with percentage sign."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Check if it's a percentage string
            if '%' in value:
                return self._parse_percentage(value)
            try:
                return float(value)
            except ValueError:
                logger.warning(f"Could not parse numeric value: {value}")
                return default
        return default
    
    async def _reconstruct_result_from_lean(self, result_dir: Path) -> Optional[BacktestResult]:
        """Reconstruct a BacktestResult from LEAN output files."""
        try:
            # Find main result file
            result_file = None
            for f in result_dir.glob("*.json"):
                if f.stem.isdigit():
                    result_file = f
                    break
            
            if not result_file:
                return None
            
            # Read config to get parameters
            config_file = result_dir / "config"
            config_data = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
            
            # Extract dates and parameters from config
            params = config_data.get("parameters", {})
            
            # Parse dates
            start_date = datetime.strptime(params.get("startDate", "20130101"), "%Y%m%d").date()
            end_date = datetime.strptime(params.get("endDate", "20131231"), "%Y%m%d").date()
            initial_cash = float(params.get("cash", 100000))
            
            # Use stored strategy name or try to determine from context
            strategy_name = self.strategy_name or "main"
            
            # If no strategy name was provided, try to determine from directory structure
            if not self.strategy_name:
                # Check if we can infer from the parent directory path
                backtests_parent = self.results_base_path.parent
                if backtests_parent.name != "lean" and backtests_parent.name != "test-project":
                    strategy_name = backtests_parent.name
                else:
                    strategy_name = "main"
            
            # Use the save_result method to process LEAN output
            backtest_id = result_dir.name  # Use directory name as ID
            
            # Extract symbol from config parameters
            symbol = params.get("symbols", "UNKNOWN")
            
            return await self.save_result(
                backtest_id=backtest_id,
                symbol=symbol,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                result_path=str(result_dir)
            )
            
        except Exception as e:
            logger.error(f"Error reconstructing result from LEAN files: {e}")
            return None
    
    async def _save_trades_to_database(self, backtest_id: str, orders: List[Dict[str, Any]]):
        """Save filled trades to the database with Eastern Time conversion."""
        try:
            # Database connection parameters
            db_config = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '5432')),
                'database': os.getenv('DB_NAME', 'stock_screener'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'postgres')
            }
            
            # Connect to database
            conn = await asyncpg.connect(**db_config)
            
            # Filter only filled trades
            filled_trades = [order for order in orders if order.get('status') == 'filled']
            
            if not filled_trades:
                logger.info(f"No filled trades to save for backtest {backtest_id}")
                await conn.close()
                return
            
            # Prepare batch insert data
            insert_data = []
            eastern_tz = ZoneInfo('America/New_York')
            
            for trade in filled_trades:
                # Convert unix timestamp to Eastern Time
                unix_timestamp = float(trade.get('time', 0))
                trade_time_utc = datetime.fromtimestamp(unix_timestamp, tz=ZoneInfo('UTC'))
                trade_time_eastern = trade_time_utc.astimezone(eastern_tz)
                
                # Extract order IDs from the composite ID (e.g., "1182382954-1-2")
                id_parts = trade.get('id', '').split('-')
                algorithm_id = id_parts[0] if len(id_parts) > 0 else ''
                order_id = int(id_parts[1]) if len(id_parts) > 1 else 0
                order_event_id = int(id_parts[2]) if len(id_parts) > 2 else 0
                
                insert_data.append((
                    backtest_id,  # backtest_id
                    algorithm_id,  # algorithm_id
                    order_id,  # order_id
                    order_event_id,  # order_event_id
                    trade.get('symbol', ''),  # symbol
                    trade.get('symbolValue', ''),  # symbol_value
                    trade_time_eastern,  # trade_time (Eastern)
                    int(unix_timestamp),  # trade_time_unix
                    trade.get('status', 'filled'),  # status
                    trade.get('direction', ''),  # direction
                    float(trade.get('quantity', 0)),  # quantity
                    float(trade.get('fillPrice', 0)) if trade.get('fillPrice') else None,  # fill_price
                    trade.get('fillPriceCurrency', 'USD'),  # fill_price_currency
                    float(trade.get('fillQuantity', 0)) if trade.get('fillQuantity') else None,  # fill_quantity
                    float(trade.get('orderFeeAmount', 0)) if trade.get('orderFeeAmount') else None,  # order_fee_amount
                    trade.get('orderFeeCurrency', 'USD'),  # order_fee_currency
                    bool(trade.get('isAssignment', False)),  # is_assignment
                    trade.get('message', '')  # message
                ))
            
            # Batch insert trades
            await conn.executemany("""
                INSERT INTO backtest_trades (
                    backtest_id, algorithm_id, order_id, order_event_id,
                    symbol, symbol_value, trade_time, trade_time_unix,
                    status, direction, quantity, fill_price, fill_price_currency,
                    fill_quantity, order_fee_amount, order_fee_currency,
                    is_assignment, message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            """, insert_data)
            
            await conn.close()
            logger.info(f"Saved {len(insert_data)} filled trades for backtest {backtest_id}")
            
        except Exception as e:
            logger.error(f"Error saving trades to database: {e}")
            # Don't fail the whole backtest save if trade save fails
            pass