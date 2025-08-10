"""
Service for storing and retrieving backtest results.
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, List

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
                         strategy_name: str,
                         start_date: date,
                         end_date: date,
                         initial_cash: float,
                         result_path: str) -> Optional[BacktestResult]:
        """
        Save a completed backtest result.
        
        Args:
            backtest_id: Unique identifier for the backtest
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
                
                # Risk Metrics
                sharpe_ratio=float(stats_data.get("Sharpe Ratio", 0)),
                sortino_ratio=float(stats_data.get("Sortino Ratio", 0)),
                max_drawdown=abs(float(portfolio_stats.get("drawdown", 0))) * -100 if portfolio_stats.get("drawdown") else abs(self._parse_percentage(stats_data.get("Drawdown", "0%"))) * -1,
                probabilistic_sharpe_ratio=self._parse_percentage(stats_data.get("Probabilistic Sharpe Ratio", "0%")),
                
                # Trading Statistics
                total_orders=int(stats_data.get("Total Orders", 0)),
                total_trades=int(trade_stats.get("totalNumberOfTrades", stats_data.get("Total Trades", 0))),
                win_rate=self._parse_percentage(stats_data.get("Win Rate", "0%")),
                loss_rate=self._parse_percentage(stats_data.get("Loss Rate", "0%")),
                average_win=self._parse_percentage(stats_data.get("Average Win", "0%")),
                average_loss=self._parse_percentage(stats_data.get("Average Loss", "0%")),
                # Note: Average Win/Loss in currency not available in LEAN output, using percentage * avg trade size
                average_win_currency=0.0,  # Will be calculated from trades if needed
                average_loss_currency=0.0,  # Will be calculated from trades if needed
                
                # Advanced Metrics
                profit_factor=float(stats_data.get("Profit Factor", 0)) or float(stats_data.get("Profit-Loss Ratio", 0)),
                profit_loss_ratio=float(stats_data.get("Profit-Loss Ratio", 0)),
                expectancy=float(stats_data.get("Expectancy", 0)),
                alpha=float(stats_data.get("Alpha", 0)),
                beta=float(stats_data.get("Beta", 0)),
                annual_standard_deviation=float(stats_data.get("Annual Standard Deviation", 0)),
                annual_variance=float(stats_data.get("Annual Variance", 0)),
                information_ratio=float(stats_data.get("Information Ratio", 0)),
                tracking_error=float(stats_data.get("Tracking Error", 0)),
                treynor_ratio=float(stats_data.get("Treynor Ratio", 0)),
                
                # Portfolio Information
                start_equity=parse_currency(portfolio_stats.get("startEquity", stats_data.get("Start Equity", initial_cash))),
                end_equity=parse_currency(portfolio_stats.get("endEquity", stats_data.get("End Equity", initial_cash))),
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
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
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
                json.dump(result.dict(), f, indent=2, default=str)
            
            logger.info(f"Saved backtest result {backtest_id} to {result_path}")
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
            return float(value.strip().rstrip('%'))
        return 0.0
    
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
            
            return await self.save_result(
                backtest_id=backtest_id,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                result_path=str(result_dir)
            )
            
        except Exception as e:
            logger.error(f"Error reconstructing result from LEAN files: {e}")
            return None