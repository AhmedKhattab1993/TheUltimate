#!/usr/bin/env python3
"""
Analysis script for parameter sweep results.

This script:
1. Loads results from all parameter combinations
2. Analyzes performance metrics across different parameter values
3. Identifies best performing parameter combinations
4. Generates reports and visualizations
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ParameterSweepAnalyzer:
    """Analyzes parameter sweep results."""
    
    def __init__(self, results_dir: str = "pipeline_results"):
        """Initialize analyzer."""
        self.results_dir = Path(results_dir)
        self.all_results = []
        
    def load_all_results(self):
        """Load all pipeline results from the results directory."""
        logger.info(f"Loading results from {self.results_dir}")
        
        # Find all JSON result files
        json_files = list(self.results_dir.glob("pipeline_results_*.json"))
        logger.info(f"Found {len(json_files)} result files")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    result_data = json.load(f)
                    
                # Extract config file name from the result
                config_file = self._find_config_file_for_result(json_file)
                if config_file:
                    # Load the config to get parameters
                    import yaml
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                    
                    # Combine results with parameters
                    combined = {
                        'result_file': str(json_file),
                        'config_file': str(config_file),
                        'parameters': self._extract_parameters_from_config(config),
                        'summary': result_data.get('summary', {}),
                        'backtest_results': result_data.get('backtest_results', {})
                    }
                    self.all_results.append(combined)
                    
            except Exception as e:
                logger.error(f"Error loading {json_file}: {e}")
    
    def _find_config_file_for_result(self, result_file: Path) -> Path:
        """Find the corresponding config file for a result file."""
        # Extract timestamp from result filename
        timestamp = result_file.stem.replace('pipeline_results_', '')
        
        # Look for config files with similar timestamp
        config_dir = Path("parameter_sweep_configs")
        if config_dir.exists():
            # Find the most recent config file before this result
            config_files = sorted(config_dir.glob("config_*.yaml"))
            for config_file in reversed(config_files):
                # Simple heuristic: use the config file created just before the result
                return config_file
        return None
    
    def _extract_parameters_from_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant parameters from config."""
        params = {}
        
        # Screener parameters
        filters = config.get('screening', {}).get('filters', {})
        
        # Price range
        if filters.get('price_range', {}).get('enabled'):
            params['price_min'] = filters['price_range']['min_price']
            params['price_max'] = filters['price_range']['max_price']
        
        # Price vs MA
        if filters.get('price_vs_ma', {}).get('enabled'):
            params['ma_period'] = filters['price_vs_ma']['ma_period']
            params['ma_condition'] = filters['price_vs_ma']['condition']
        else:
            params['ma_period'] = None
            params['ma_condition'] = None
        
        # Gap
        if filters.get('gap', {}).get('enabled'):
            params['gap_threshold'] = filters['gap']['gap_threshold']
            params['gap_direction'] = filters['gap']['direction']
        else:
            params['gap_threshold'] = None
            params['gap_direction'] = None
        
        # Volume
        params['min_volume'] = filters.get('prev_day_dollar_volume', {}).get('min_dollar_volume')
        
        # Relative volume
        if filters.get('relative_volume', {}).get('enabled'):
            params['rel_volume_ratio'] = filters['relative_volume']['min_ratio']
        else:
            params['rel_volume_ratio'] = None
        
        # RSI
        if filters.get('rsi', {}).get('enabled'):
            params['rsi_threshold'] = filters['rsi']['threshold']
            params['rsi_condition'] = filters['rsi']['condition']
        else:
            params['rsi_threshold'] = None
            params['rsi_condition'] = None
        
        # Backtest parameters
        backtest_params = config.get('backtesting', {}).get('parameters', {})
        params['pivot_bars'] = backtest_params.get('pivot_bars')
        params['lower_timeframe'] = backtest_params.get('lower_timeframe')
        
        return params
    
    def analyze_by_parameter(self) -> pd.DataFrame:
        """Analyze results grouped by each parameter."""
        if not self.all_results:
            logger.warning("No results loaded")
            return pd.DataFrame()
        
        # Convert to DataFrame for easier analysis
        rows = []
        for result in self.all_results:
            params = result['parameters']
            summary = result['summary']
            
            # Calculate aggregate metrics
            if result['backtest_results']:
                returns = []
                sharpe_ratios = []
                win_rates = []
                
                for symbol, backtest in result['backtest_results'].items():
                    if isinstance(backtest, dict) and 'statistics' in backtest:
                        stats = backtest['statistics']
                        if 'total_return' in stats:
                            returns.append(stats['total_return'])
                        if 'sharpe_ratio' in stats:
                            sharpe_ratios.append(stats['sharpe_ratio'])
                        if 'win_rate' in stats:
                            win_rates.append(stats['win_rate'])
                
                # Add row with parameters and metrics
                row = params.copy()
                row.update({
                    'num_symbols': len(result['backtest_results']),
                    'avg_return': sum(returns) / len(returns) if returns else 0,
                    'avg_sharpe': sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0,
                    'avg_win_rate': sum(win_rates) / len(win_rates) if win_rates else 0,
                    'positive_returns': sum(1 for r in returns if r > 0),
                    'negative_returns': sum(1 for r in returns if r < 0)
                })
                rows.append(row)
        
        return pd.DataFrame(rows)
    
    def find_best_combinations(self, metric: str = 'avg_return', top_n: int = 10) -> pd.DataFrame:
        """Find the best parameter combinations based on a metric."""
        df = self.analyze_by_parameter()
        if df.empty:
            return df
        
        # Sort by metric and get top N
        return df.nlargest(top_n, metric)
    
    def analyze_parameter_impact(self) -> Dict[str, pd.DataFrame]:
        """Analyze the impact of each parameter on performance."""
        df = self.analyze_by_parameter()
        if df.empty:
            return {}
        
        results = {}
        
        # Analyze each parameter
        parameters = ['price_min', 'price_max', 'ma_period', 'ma_condition', 
                     'gap_threshold', 'gap_direction', 'min_volume', 
                     'rel_volume_ratio', 'rsi_threshold', 'rsi_condition',
                     'pivot_bars', 'lower_timeframe']
        
        for param in parameters:
            if param in df.columns:
                # Group by parameter value and calculate mean metrics
                grouped = df.groupby(param).agg({
                    'avg_return': 'mean',
                    'avg_sharpe': 'mean',
                    'avg_win_rate': 'mean',
                    'num_symbols': 'mean'
                }).round(2)
                
                results[param] = grouped
        
        return results
    
    def generate_report(self, output_file: str = "parameter_sweep_analysis.txt"):
        """Generate a comprehensive analysis report."""
        with open(output_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("PARAMETER SWEEP ANALYSIS REPORT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            
            # Overall statistics
            df = self.analyze_by_parameter()
            if not df.empty:
                f.write("OVERALL STATISTICS\n")
                f.write("-"*40 + "\n")
                f.write(f"Total combinations analyzed: {len(df)}\n")
                f.write(f"Average symbols per combination: {df['num_symbols'].mean():.1f}\n")
                f.write(f"Average return: {df['avg_return'].mean():.2f}%\n")
                f.write(f"Average Sharpe ratio: {df['avg_sharpe'].mean():.3f}\n")
                f.write(f"Average win rate: {df['avg_win_rate'].mean():.1f}%\n\n")
                
                # Best combinations
                f.write("TOP 10 COMBINATIONS BY RETURN\n")
                f.write("-"*40 + "\n")
                best = self.find_best_combinations('avg_return', 10)
                f.write(best.to_string() + "\n\n")
                
                # Parameter impact analysis
                f.write("PARAMETER IMPACT ANALYSIS\n")
                f.write("-"*40 + "\n")
                impact = self.analyze_parameter_impact()
                
                for param, analysis in impact.items():
                    f.write(f"\n{param.upper()}:\n")
                    f.write(analysis.to_string() + "\n")
        
        logger.info(f"Report saved to {output_file}")
    
    def export_to_csv(self, output_file: str = "parameter_sweep_results.csv"):
        """Export all results to CSV for further analysis."""
        df = self.analyze_by_parameter()
        if not df.empty:
            df.to_csv(output_file, index=False)
            logger.info(f"Results exported to {output_file}")


def main():
    """Main entry point."""
    analyzer = ParameterSweepAnalyzer()
    
    # Load all results
    analyzer.load_all_results()
    
    # Generate analysis report
    analyzer.generate_report()
    
    # Export to CSV
    analyzer.export_to_csv()
    
    # Print summary
    logger.info("\nAnalysis complete!")
    logger.info("Files generated:")
    logger.info("  - parameter_sweep_analysis.txt (detailed report)")
    logger.info("  - parameter_sweep_results.csv (raw data for further analysis)")


if __name__ == "__main__":
    main()