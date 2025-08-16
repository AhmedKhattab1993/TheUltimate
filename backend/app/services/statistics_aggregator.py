"""
Statistics Aggregator for collecting and analyzing backtest results.

This service:
- Collects statistics from multiple backtest results
- Calculates aggregate metrics (average return, sharpe, win rate, etc.)
- Formats output for different formats (JSON, CSV, HTML, console)
- Provides statistical analysis across all backtests
"""

import json
import csv
import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class StatisticsAggregator:
    """Aggregates and analyzes statistics from multiple backtests."""
    
    def __init__(self):
        """Initialize the statistics aggregator."""
        self.results = []
        
    def _parse_lean_results(self, result_path: str) -> Optional[Dict[str, Any]]:
        """Parse LEAN backtest results from the result directory."""
        if not result_path:
            return None
            
        result_dir = Path(result_path)
        if not result_dir.exists():
            return None
        
        # Find summary JSON file
        summary_files = list(result_dir.glob("*-summary.json"))
        if not summary_files:
            return None
        
        try:
            with open(summary_files[0], 'r') as f:
                lean_data = json.load(f)
            
            # Extract key statistics from both statistics and runtimeStatistics sections
            stats = lean_data.get('statistics', {})
            runtime_stats = lean_data.get('runtimeStatistics', {})
            portfolio_stats = lean_data.get('totalPerformance', {}).get('portfolioStatistics', {})
            trade_stats = lean_data.get('totalPerformance', {}).get('tradeStatistics', {})
            
            def safe_float(value, default=0.0):
                """Safely convert to float, handling string percentages."""
                if value is None:
                    return default
                if isinstance(value, str):
                    value = value.replace('%', '').replace('$', '').replace(',', '').strip()
                    try:
                        return float(value)
                    except ValueError:
                        return default
                return float(value) if value else default
            
            # Try to get values from runtime stats first (which have actual values), then fall back to statistics
            total_return = safe_float(runtime_stats.get('Return', '0').replace('%', ''))
            if total_return == 0:
                total_return = safe_float(stats.get('Net Profit', '0').replace('%', ''))
            
            # Get sharpe ratio from portfolio statistics if available
            sharpe_ratio = safe_float(portfolio_stats.get('sharpeRatio', '0'))
            if sharpe_ratio == 0:
                sharpe_ratio = safe_float(stats.get('Sharpe Ratio', '0'))
            
            # Get win rate from trade statistics
            win_rate = safe_float(trade_stats.get('winRate', '0')) * 100  # Convert to percentage
            if win_rate == 0:
                win_rate = safe_float(stats.get('Win Rate', '0').replace('%', ''))
            
            # Get drawdown from portfolio statistics
            max_drawdown = abs(safe_float(portfolio_stats.get('drawdown', '0')))
            if max_drawdown == 0:
                max_drawdown = abs(safe_float(stats.get('Drawdown', '0').replace('%', '')))
            
            # Get total trades from trade statistics
            total_trades = int(safe_float(trade_stats.get('totalNumberOfTrades', '0')))
            if total_trades == 0:
                total_trades = int(safe_float(stats.get('Total Orders', '0')))
            
            # Get profit factor from trade statistics
            profit_factor = safe_float(trade_stats.get('profitFactor', '0'))
            if profit_factor == 0:
                profit_factor = safe_float(stats.get('Profit Factor', '0'))
            
            # Calculate starting and ending equity
            start_equity = safe_float(portfolio_stats.get('startEquity', '100000'))
            end_equity = safe_float(portfolio_stats.get('endEquity', '100000'))
            
            # If total return is still 0, calculate it from equity values
            if total_return == 0 and start_equity > 0:
                total_return = ((end_equity - start_equity) / start_equity) * 100
            
            parsed_stats = {
                'total_return': total_return,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'profit_factor': profit_factor,
                'average_win': safe_float(trade_stats.get('averageProfit', '0')),
                'average_loss': abs(safe_float(trade_stats.get('averageLoss', '0'))),
                'compounding_annual_return': safe_float(portfolio_stats.get('compoundingAnnualReturn', '0')),
                'volatility': safe_float(portfolio_stats.get('annualStandardDeviation', '0')),
                'start_equity': start_equity,
                'end_equity': end_equity,
                'net_profit': end_equity - start_equity
            }
            
            return parsed_stats
            
        except Exception as e:
            logger.error(f"Failed to parse LEAN results from {result_path}: {e}")
            return None
    
    def aggregate_results(self, backtest_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate statistics from multiple backtest results.
        
        Args:
            backtest_results: Dictionary mapping symbols to backtest results
            
        Returns:
            Aggregated statistics and analysis
        """
        # Collect all statistics
        all_stats = []
        failed_backtests = []
        
        for symbol, result in backtest_results.items():
            if result.get('status') == 'failed':
                failed_backtests.append({
                    'symbol': symbol,
                    'error': result.get('error', 'Unknown error')
                })
                continue
            
            # Parse LEAN results if available
            result_path = result.get('result_path')
            if result_path:
                stats = self._parse_lean_results(result_path)
                if stats:
                    stats['symbol'] = symbol
                    all_stats.append(stats)
                else:
                    logger.warning(f"Could not parse results for {symbol}")
        
        # Calculate aggregate metrics
        aggregated = {
            'summary': {
                'total_backtests': len(backtest_results),
                'successful_backtests': len(all_stats),
                'failed_backtests': len(failed_backtests),
                'timestamp': datetime.now().isoformat()
            },
            'failed_backtests': failed_backtests,
            'individual_results': all_stats
        }
        
        if all_stats:
            # Calculate statistical measures
            aggregated['aggregate_statistics'] = {
                'average_return': statistics.mean([s['total_return'] for s in all_stats]),
                'median_return': statistics.median([s['total_return'] for s in all_stats]),
                'std_dev_return': statistics.stdev([s['total_return'] for s in all_stats]) if len(all_stats) > 1 else 0,
                'min_return': min([s['total_return'] for s in all_stats]),
                'max_return': max([s['total_return'] for s in all_stats]),
                'average_sharpe': statistics.mean([s['sharpe_ratio'] for s in all_stats]),
                'average_max_drawdown': statistics.mean([s['max_drawdown'] for s in all_stats]),
                'average_win_rate': statistics.mean([s['win_rate'] for s in all_stats]),
                'total_trades_all': sum([s['total_trades'] for s in all_stats]),
                'average_trades_per_symbol': statistics.mean([s['total_trades'] for s in all_stats])
            }
            
            # Find best and worst performers
            sorted_by_return = sorted(all_stats, key=lambda x: x['total_return'], reverse=True)
            aggregated['top_performers'] = sorted_by_return[:10]
            aggregated['worst_performers'] = sorted_by_return[-10:]
            
            # Distribution analysis
            returns = [s['total_return'] for s in all_stats]
            aggregated['return_distribution'] = {
                'profitable_count': sum(1 for r in returns if r > 0),
                'unprofitable_count': sum(1 for r in returns if r <= 0),
                'percentile_25': statistics.quantiles(returns, n=4)[0] if len(returns) > 1 else 0,
                'percentile_50': statistics.quantiles(returns, n=4)[1] if len(returns) > 1 else 0,
                'percentile_75': statistics.quantiles(returns, n=4)[2] if len(returns) > 1 else 0
            }
        
        return aggregated
    
    def save_json(self, aggregated_stats: Dict[str, Any], filepath: Path):
        """Save aggregated statistics to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(aggregated_stats, f, indent=2)
    
    def save_csv(self, aggregated_stats: Dict[str, Any], filepath: Path):
        """Save aggregated statistics to CSV file."""
        # Convert individual results to DataFrame
        individual_results = aggregated_stats.get('individual_results', [])
        
        if individual_results:
            df = pd.DataFrame(individual_results)
            # Reorder columns to put symbol first
            cols = ['symbol'] + [col for col in df.columns if col != 'symbol']
            df = df[cols]
            df.to_csv(filepath, index=False)
        else:
            # Create empty CSV with headers
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['symbol', 'total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades', 'net_profit', 'start_equity', 'end_equity', 'profit_factor'])
    
    def save_html(self, aggregated_stats: Dict[str, Any], filepath: Path):
        """Save aggregated statistics to HTML report."""
        html_content = self._generate_html_report(aggregated_stats)
        with open(filepath, 'w') as f:
            f.write(html_content)
    
    def _generate_html_report(self, stats: Dict[str, Any]) -> str:
        """Generate HTML report from aggregated statistics."""
        summary = stats.get('summary', {})
        agg_stats = stats.get('aggregate_statistics', {})
        top_performers = stats.get('top_performers', [])[:5]
        worst_performers = stats.get('worst_performers', [])[:5]
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Pipeline Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
        .positive {{ color: green; }}
        .negative {{ color: red; }}
        .summary-box {{ background-color: #f9f9f9; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-label {{ font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Backtest Pipeline Results</h1>
    <p>Generated: {summary.get('timestamp', 'N/A')}</p>
    
    <div class="summary-box">
        <h2>Summary</h2>
        <div class="metric">
            <span class="metric-label">Total Backtests:</span> {summary.get('total_backtests', 0)}
        </div>
        <div class="metric">
            <span class="metric-label">Successful:</span> {summary.get('successful_backtests', 0)}
        </div>
        <div class="metric">
            <span class="metric-label">Failed:</span> {summary.get('failed_backtests', 0)}
        </div>
    </div>
    
    <h2>Aggregate Statistics</h2>
    <table>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
        <tr>
            <td>Average Return</td>
            <td class="{'positive' if agg_stats.get('average_return', 0) > 0 else 'negative'}">{agg_stats.get('average_return', 0):.2f}%</td>
        </tr>
        <tr>
            <td>Median Return</td>
            <td class="{'positive' if agg_stats.get('median_return', 0) > 0 else 'negative'}">{agg_stats.get('median_return', 0):.2f}%</td>
        </tr>
        <tr>
            <td>Standard Deviation</td>
            <td>{agg_stats.get('std_dev_return', 0):.2f}%</td>
        </tr>
        <tr>
            <td>Average Sharpe Ratio</td>
            <td>{agg_stats.get('average_sharpe', 0):.2f}</td>
        </tr>
        <tr>
            <td>Average Max Drawdown</td>
            <td class="negative">{agg_stats.get('average_max_drawdown', 0):.2f}%</td>
        </tr>
        <tr>
            <td>Average Win Rate</td>
            <td>{agg_stats.get('average_win_rate', 0):.2f}%</td>
        </tr>
    </table>
    
    <h2>Top Performers</h2>
    <table>
        <tr>
            <th>Symbol</th>
            <th>Total Return</th>
            <th>Sharpe Ratio</th>
            <th>Win Rate</th>
            <th>Total Trades</th>
            <th>Net Profit</th>
        </tr>
"""
        
        for perf in top_performers:
            net_profit = perf.get('net_profit', 0)
            html += f"""
        <tr>
            <td>{perf['symbol']}</td>
            <td class="positive">{perf['total_return']:.2f}%</td>
            <td>{perf['sharpe_ratio']:.2f}</td>
            <td>{perf['win_rate']:.2f}%</td>
            <td>{perf.get('total_trades', 0)}</td>
            <td class="positive">${net_profit:,.2f}</td>
        </tr>
"""
        
        html += """
    </table>
    
    <h2>Worst Performers</h2>
    <table>
        <tr>
            <th>Symbol</th>
            <th>Total Return</th>
            <th>Sharpe Ratio</th>
            <th>Win Rate</th>
            <th>Total Trades</th>
            <th>Net Profit</th>
        </tr>
"""
        
        for perf in worst_performers:
            net_profit = perf.get('net_profit', 0)
            html += f"""
        <tr>
            <td>{perf['symbol']}</td>
            <td class="negative">{perf['total_return']:.2f}%</td>
            <td>{perf['sharpe_ratio']:.2f}</td>
            <td>{perf['win_rate']:.2f}%</td>
            <td>{perf.get('total_trades', 0)}</td>
            <td class="{'negative' if net_profit < 0 else 'positive'}">${net_profit:,.2f}</td>
        </tr>
"""
        
        html += """
    </table>
</body>
</html>
"""
        return html
    
    def print_summary(self, aggregated_stats: Dict[str, Any]):
        """Print summary statistics to console."""
        summary = aggregated_stats.get('summary', {})
        agg_stats = aggregated_stats.get('aggregate_statistics', {})
        dist = aggregated_stats.get('return_distribution', {})
        
        print("\n" + "=" * 80)
        print("BACKTEST RESULTS SUMMARY")
        print("=" * 80)
        
        print(f"\nTotal Backtests: {summary.get('total_backtests', 0)}")
        print(f"Successful: {summary.get('successful_backtests', 0)}")
        print(f"Failed: {summary.get('failed_backtests', 0)}")
        
        if agg_stats:
            print("\nAGGREGATE STATISTICS:")
            print("-" * 40)
            print(f"Average Return: {agg_stats.get('average_return', 0):.2f}%")
            print(f"Median Return: {agg_stats.get('median_return', 0):.2f}%")
            print(f"Std Dev Return: {agg_stats.get('std_dev_return', 0):.2f}%")
            print(f"Min Return: {agg_stats.get('min_return', 0):.2f}%")
            print(f"Max Return: {agg_stats.get('max_return', 0):.2f}%")
            print(f"Average Sharpe: {agg_stats.get('average_sharpe', 0):.2f}")
            print(f"Average Max Drawdown: {agg_stats.get('average_max_drawdown', 0):.2f}%")
            print(f"Average Win Rate: {agg_stats.get('average_win_rate', 0):.2f}%")
            
            print("\nRETURN DISTRIBUTION:")
            print("-" * 40)
            print(f"Profitable: {dist.get('profitable_count', 0)} symbols")
            print(f"Unprofitable: {dist.get('unprofitable_count', 0)} symbols")
            print(f"25th Percentile: {dist.get('percentile_25', 0):.2f}%")
            print(f"50th Percentile: {dist.get('percentile_50', 0):.2f}%")
            print(f"75th Percentile: {dist.get('percentile_75', 0):.2f}%")
        
        # Show top performers
        top_performers = aggregated_stats.get('top_performers', [])[:5]
        if top_performers:
            print("\nTOP 5 PERFORMERS:")
            print("-" * 40)
            for i, perf in enumerate(top_performers, 1):
                net_profit = perf.get('net_profit', 0)
                print(f"{i}. {perf['symbol']}: {perf['total_return']:.2f}% (Net: ${net_profit:,.2f}, Sharpe: {perf['sharpe_ratio']:.2f}, Trades: {perf.get('total_trades', 0)})")
        
        print("=" * 80)