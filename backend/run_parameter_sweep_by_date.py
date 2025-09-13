#!/usr/bin/env python3
"""
Parameter sweep script that processes all combinations for each date before moving to the next date.

This script:
1. For each trading day:
   - Generates all parameter combinations
   - Runs all combinations for that specific day
   - Saves results
2. Then moves to the next trading day
"""

import asyncio
import logging
import sys
import yaml
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple
from itertools import product
import hashlib

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent))

from run_screener_backtest_pipeline import ScreenerBacktestPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DateBasedParameterSweep:
    """Manages parameter sweep execution by date."""
    
    def __init__(self, base_config_path: str = "pipeline_config.yaml", 
                 progress_file: str = "parameter_sweep_by_date_progress.json"):
        """Initialize parameter sweep."""
        self.base_config_path = Path(base_config_path)
        self.progress_file = Path(progress_file)
        self.base_config = self._load_base_config()
        self.completed_combinations = self._load_progress()
        
        # Define parameter ranges (same as before)
        self.parameter_ranges = {
            'screener': {
                'price_range': [
                    (1, 20),      # Penny stocks
                    (20, 10000),  # All stocks above $20
                    (20, 100),    # Mid-range stocks
                    (100, 10000)  # High-priced stocks
                ],
                'price_vs_ma': [
                    {'enabled': False},
                    {'enabled': True, 'period': 20, 'condition': 'above'},
                    {'enabled': True, 'period': 20, 'condition': 'below'},
                    {'enabled': True, 'period': 50, 'condition': 'above'},
                    {'enabled': True, 'period': 50, 'condition': 'below'},
                    {'enabled': True, 'period': 200, 'condition': 'above'},
                    {'enabled': True, 'period': 200, 'condition': 'below'}
                ],
                'gap': [
                    {'enabled': False},
                    # Up gaps
                    {'enabled': True, 'threshold': 1.0, 'direction': 'up'},
                    {'enabled': True, 'threshold': 2.0, 'direction': 'up'},
                    {'enabled': True, 'threshold': 3.0, 'direction': 'up'},
                    {'enabled': True, 'threshold': 4.0, 'direction': 'up'},
                    {'enabled': True, 'threshold': 5.0, 'direction': 'up'},
                    # Down gaps
                    {'enabled': True, 'threshold': 1.0, 'direction': 'down'},
                    {'enabled': True, 'threshold': 2.0, 'direction': 'down'},
                    {'enabled': True, 'threshold': 3.0, 'direction': 'down'},
                    {'enabled': True, 'threshold': 4.0, 'direction': 'down'},
                    {'enabled': True, 'threshold': 5.0, 'direction': 'down'},
                    # Both directions
                    {'enabled': True, 'threshold': 1.0, 'direction': 'both'},
                    {'enabled': True, 'threshold': 2.0, 'direction': 'both'},
                    {'enabled': True, 'threshold': 3.0, 'direction': 'both'},
                    {'enabled': True, 'threshold': 4.0, 'direction': 'both'},
                    {'enabled': True, 'threshold': 5.0, 'direction': 'both'}
                ],
                'prev_day_dollar_volume': [
                    10000000,     # $10M
                    100000000,    # $100M
                    1000000000    # $1B
                ],
                'relative_volume': [
                    {'enabled': False},
                    {'enabled': True, 'ratio': 1.5},
                    {'enabled': True, 'ratio': 2.0},
                    {'enabled': True, 'ratio': 3.0}
                ],
                'rsi': [
                    {'enabled': False},
                    # Above thresholds
                    {'enabled': True, 'period': 14, 'threshold': 50, 'condition': 'above'},
                    {'enabled': True, 'period': 14, 'threshold': 60, 'condition': 'above'},
                    {'enabled': True, 'period': 14, 'threshold': 70, 'condition': 'above'},
                    {'enabled': True, 'period': 14, 'threshold': 80, 'condition': 'above'},
                    {'enabled': True, 'period': 14, 'threshold': 90, 'condition': 'above'},
                    # Below thresholds
                    {'enabled': True, 'period': 14, 'threshold': 50, 'condition': 'below'},
                    {'enabled': True, 'period': 14, 'threshold': 40, 'condition': 'below'},
                    {'enabled': True, 'period': 14, 'threshold': 30, 'condition': 'below'},
                    {'enabled': True, 'period': 14, 'threshold': 20, 'condition': 'below'},
                    {'enabled': True, 'period': 14, 'threshold': 10, 'condition': 'below'}
                ]
            },
            'backtest': {
                'pivot_bars': list(range(1, 11)),  # 1 through 10
                'lower_timeframe': ['1min']  # Fixed at 1 minute
            }
        }
        
    def _load_base_config(self) -> Dict[str, Any]:
        """Load base configuration from YAML file."""
        if not self.base_config_path.exists():
            raise FileNotFoundError(f"Base configuration file not found: {self.base_config_path}")
        
        with open(self.base_config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _load_progress(self) -> Dict[str, set]:
        """Load completed combinations from progress file, organized by date."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                # Convert lists back to sets for each date
                return {date_str: set(combos) for date_str, combos in data.get('completed_by_date', {}).items()}
        return {}
    
    def _save_progress(self, date_str: str, combination_hash: str):
        """Save progress after completing a combination for a specific date."""
        if date_str not in self.completed_combinations:
            self.completed_combinations[date_str] = set()
        self.completed_combinations[date_str].add(combination_hash)
        
        # Convert sets to lists for JSON serialization
        progress_data = {
            'completed_by_date': {date_str: list(combos) for date_str, combos in self.completed_combinations.items()},
            'last_updated': datetime.now().isoformat()
        }
        
        # Save back to file
        with open(self.progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
    
    def _generate_combination_hash(self, params: Dict[str, Any]) -> str:
        """Generate unique hash for a parameter combination."""
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()
    
    def _get_trading_days(self, start_date: str, end_date: str) -> List[date]:
        """Get all trading days between start and end dates in reverse order (newest first)."""
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        trading_days = []
        current = end  # Start from end date
        
        while current >= start:  # Work backwards to start date
            # Check if it's a weekday (Monday=0 to Friday=4)
            if current.weekday() < 5:
                trading_days.append(current)
            current = current - timedelta(days=1)
        
        return trading_days  # This list is already in reverse order (newest first)
    
    def _create_config_for_combination(self, combination: Dict[str, Any], trading_date: date) -> Dict[str, Any]:
        """Create a pipeline config for a specific parameter combination and date."""
        # Deep copy base config
        config = json.loads(json.dumps(self.base_config))
        
        # Set the date range to just this specific day
        date_str = trading_date.strftime('%Y-%m-%d')
        config['screening']['date_range']['start'] = date_str
        config['screening']['date_range']['end'] = date_str
        
        # Update screener filters
        screener_params = combination['screener']
        
        # Price range
        config['screening']['filters']['price_range']['enabled'] = True
        config['screening']['filters']['price_range']['min_price'] = screener_params['price_range'][0]
        config['screening']['filters']['price_range']['max_price'] = screener_params['price_range'][1]
        
        # Price vs MA
        if screener_params['price_vs_ma']['enabled']:
            config['screening']['filters']['price_vs_ma']['enabled'] = True
            config['screening']['filters']['price_vs_ma']['ma_period'] = screener_params['price_vs_ma']['period']
            config['screening']['filters']['price_vs_ma']['condition'] = screener_params['price_vs_ma']['condition']
        else:
            config['screening']['filters']['price_vs_ma']['enabled'] = False
        
        # Gap
        if screener_params['gap']['enabled']:
            config['screening']['filters']['gap']['enabled'] = True
            config['screening']['filters']['gap']['gap_threshold'] = screener_params['gap']['threshold']
            config['screening']['filters']['gap']['direction'] = screener_params['gap']['direction']
        else:
            config['screening']['filters']['gap']['enabled'] = False
        
        # Previous day dollar volume
        config['screening']['filters']['prev_day_dollar_volume']['enabled'] = True
        config['screening']['filters']['prev_day_dollar_volume']['min_dollar_volume'] = screener_params['prev_day_dollar_volume']
        
        # Relative volume
        if screener_params['relative_volume']['enabled']:
            config['screening']['filters']['relative_volume']['enabled'] = True
            config['screening']['filters']['relative_volume']['min_ratio'] = screener_params['relative_volume']['ratio']
            config['screening']['filters']['relative_volume']['recent_days'] = 2
            config['screening']['filters']['relative_volume']['lookback_days'] = 20
        else:
            config['screening']['filters']['relative_volume']['enabled'] = False
        
        # RSI
        if screener_params['rsi']['enabled']:
            config['screening']['filters']['rsi']['enabled'] = True
            config['screening']['filters']['rsi']['rsi_period'] = screener_params['rsi']['period']
            config['screening']['filters']['rsi']['threshold'] = screener_params['rsi']['threshold']
            config['screening']['filters']['rsi']['condition'] = screener_params['rsi']['condition']
        else:
            config['screening']['filters']['rsi']['enabled'] = False
        
        # Update backtest parameters
        config['backtesting']['parameters']['pivot_bars'] = combination['backtest']['pivot_bars']
        config['backtesting']['parameters']['lower_timeframe'] = combination['backtest']['lower_timeframe']
        
        return config
    
    def _generate_all_combinations(self) -> List[Dict[str, Any]]:
        """Generate all parameter combinations."""
        combinations = []
        
        # Get all screener combinations
        screener_combos = list(product(
            self.parameter_ranges['screener']['price_range'],
            self.parameter_ranges['screener']['price_vs_ma'],
            self.parameter_ranges['screener']['gap'],
            self.parameter_ranges['screener']['prev_day_dollar_volume'],
            self.parameter_ranges['screener']['relative_volume'],
            self.parameter_ranges['screener']['rsi']
        ))
        
        # Get all backtest combinations
        backtest_combos = list(product(
            self.parameter_ranges['backtest']['pivot_bars'],
            self.parameter_ranges['backtest']['lower_timeframe']
        ))
        
        # Combine screener and backtest parameters
        for screener_combo in screener_combos:
            for backtest_combo in backtest_combos:
                combination = {
                    'screener': {
                        'price_range': screener_combo[0],
                        'price_vs_ma': screener_combo[1],
                        'gap': screener_combo[2],
                        'prev_day_dollar_volume': screener_combo[3],
                        'relative_volume': screener_combo[4],
                        'rsi': screener_combo[5]
                    },
                    'backtest': {
                        'pivot_bars': backtest_combo[0],
                        'lower_timeframe': backtest_combo[1]
                    }
                }
                combinations.append(combination)
        
        return combinations
    
    def _save_combination_config(self, combination: Dict[str, Any], trading_date: date, index: int) -> str:
        """Save configuration for a specific combination and return the file path."""
        # Create configs directory if it doesn't exist
        configs_dir = Path("parameter_sweep_configs_by_date")
        configs_dir.mkdir(exist_ok=True)
        
        # Create subdirectory for this date
        date_str = trading_date.strftime("%Y%m%d")
        date_dir = configs_dir / date_str
        date_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"config_{date_str}_{index:05d}_{timestamp}.yaml"
        filepath = date_dir / filename
        
        # Create config for this combination and date
        config = self._create_config_for_combination(combination, trading_date)
        
        # Save to file
        with open(filepath, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return str(filepath)
    
    async def run_combination(self, combination: Dict[str, Any], trading_date: date, index: int) -> Dict[str, Any]:
        """Run pipeline for a single parameter combination on a specific date."""
        # Save config for this combination
        config_path = self._save_combination_config(combination, trading_date, index)
        
        try:
            # DIAGNOSTIC LOGGING
            logger.info(f"[DIAGNOSTIC] Creating pipeline instance for combination {index}")
            logger.info(f"[DIAGNOSTIC] Date: {trading_date}, Config: {config_path}")
            
            # Create and run pipeline with this config
            pipeline = ScreenerBacktestPipeline(config_path)
            
            logger.info(f"[DIAGNOSTIC] Pipeline created with session ID: {pipeline.pipeline_session_id}")
            logger.info(f"[DIAGNOSTIC] Queue manager session ID: {pipeline.queue_manager.screener_session_id}")
            
            # Run the pipeline (it will only process the single date in the config)
            await pipeline.run()
            
            # Return summary results
            return {
                'success': True,
                'date': trading_date.strftime('%Y-%m-%d'),
                'combination': combination,
                'config_path': config_path
            }
            
        except Exception as e:
            logger.error(f"Failed to run combination {index} for {trading_date}: {e}")
            return {
                'success': False,
                'date': trading_date.strftime('%Y-%m-%d'),
                'combination': combination,
                'config_path': config_path,
                'error': str(e)
            }
        finally:
            # Ensure cleanup
            if 'pipeline' in locals():
                await pipeline.cleanup()
    
    async def run_all_combinations_for_date(self, trading_date: date, combinations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run all parameter combinations for a specific date."""
        date_str = trading_date.strftime('%Y-%m-%d')
        logger.info(f"\n{'='*80}")
        logger.info(f"PROCESSING DATE: {date_str}")
        logger.info(f"{'='*80}")
        
        # Get completed combinations for this date
        completed_for_date = self.completed_combinations.get(date_str, set())
        
        # Track results for this date
        date_results = {
            'date': date_str,
            'total_combinations': len(combinations),
            'completed': 0,
            'skipped': 0,
            'failed': 0,
            'start_time': datetime.now().isoformat(),
            'results': []
        }
        
        # Process each combination for this date
        for i, combination in enumerate(combinations, 1):
            # Check if already completed
            combo_hash = self._generate_combination_hash(combination)
            if combo_hash in completed_for_date:
                logger.info(f"[{date_str}] Skipping combination {i}/{len(combinations)} (already completed)")
                date_results['skipped'] += 1
                continue
            
            # Run the combination
            logger.info(f"[{date_str}] Running combination {i}/{len(combinations)}")
            start_time = datetime.now()
            result = await self.run_combination(combination, trading_date, i)
            end_time = datetime.now()
            
            # Add timing info
            result['execution_time'] = (end_time - start_time).total_seconds()
            date_results['results'].append(result)
            
            # Update progress
            if result['success']:
                date_results['completed'] += 1
                self._save_progress(date_str, combo_hash)
                logger.info(f"[{date_str}] Combination {i} completed in {result['execution_time']:.1f} seconds")
            else:
                date_results['failed'] += 1
                logger.error(f"[{date_str}] Combination {i} failed: {result.get('error', 'Unknown error')}")
            
            # Log progress
            total_processed = date_results['completed'] + date_results['skipped'] + date_results['failed']
            logger.info(f"[{date_str}] Progress: {total_processed}/{len(combinations)} "
                       f"(Completed: {date_results['completed']}, Skipped: {date_results['skipped']}, "
                       f"Failed: {date_results['failed']})")
        
        date_results['end_time'] = datetime.now().isoformat()
        return date_results
    
    async def run_sweep(self):
        """Run the complete parameter sweep, processing all combinations for each date."""
        logger.info("="*80)
        logger.info("DATE-BASED PARAMETER SWEEP EXECUTION")
        logger.info("="*80)
        
        # Get trading days from config
        start_date = self.base_config['screening']['date_range']['start']
        end_date = self.base_config['screening']['date_range']['end']
        trading_days = self._get_trading_days(start_date, end_date)
        
        # Generate all combinations
        all_combinations = self._generate_all_combinations()
        
        logger.info(f"Trading days to process: {len(trading_days)} (in reverse order)")
        logger.info(f"Date range: {trading_days[-1].strftime('%Y-%m-%d')} to {trading_days[0].strftime('%Y-%m-%d')}")
        logger.info(f"Parameter combinations per day: {len(all_combinations):,}")
        logger.info(f"Total iterations: {len(trading_days) * len(all_combinations):,}")
        
        # Overall results tracking
        overall_results = {
            'start_time': datetime.now().isoformat(),
            'trading_days': len(trading_days),
            'combinations_per_day': len(all_combinations),
            'daily_results': []
        }
        
        # Process each trading day (newest to oldest)
        for day_num, trading_date in enumerate(trading_days, 1):
            logger.info(f"\n{'#'*80}")
            logger.info(f"DAY {day_num}/{len(trading_days)}: {trading_date.strftime('%Y-%m-%d')} (processing backwards)")
            logger.info(f"{'#'*80}")
            
            # Run all combinations for this date
            date_results = await self.run_all_combinations_for_date(trading_date, all_combinations)
            overall_results['daily_results'].append(date_results)
            
            # Save intermediate results
            intermediate_file = Path(f"parameter_sweep_intermediate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(intermediate_file, 'w') as f:
                json.dump(overall_results, f, indent=2)
            
            logger.info(f"\nCompleted {trading_date.strftime('%Y-%m-%d')}: "
                       f"{date_results['completed']} completed, "
                       f"{date_results['skipped']} skipped, "
                       f"{date_results['failed']} failed")
        
        # Save final results
        overall_results['end_time'] = datetime.now().isoformat()
        final_file = Path(f"parameter_sweep_by_date_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(final_file, 'w') as f:
            json.dump(overall_results, f, indent=2)
        
        # Print final summary
        logger.info("\n" + "="*80)
        logger.info("DATE-BASED PARAMETER SWEEP COMPLETED")
        logger.info("="*80)
        logger.info(f"Trading days processed: {len(trading_days)}")
        logger.info(f"Combinations per day: {len(all_combinations):,}")
        
        # Calculate totals
        total_completed = sum(d['completed'] for d in overall_results['daily_results'])
        total_skipped = sum(d['skipped'] for d in overall_results['daily_results'])
        total_failed = sum(d['failed'] for d in overall_results['daily_results'])
        
        logger.info(f"\nTotal Results:")
        logger.info(f"  Completed: {total_completed:,}")
        logger.info(f"  Skipped: {total_skipped:,}")
        logger.info(f"  Failed: {total_failed:,}")
        logger.info(f"\nFinal results saved to: {final_file}")


async def main():
    """Main entry point."""
    # Check if custom base config provided
    base_config = sys.argv[1] if len(sys.argv) > 1 else "pipeline_config.yaml"
    
    # Create and run date-based parameter sweep
    sweep = DateBasedParameterSweep(base_config)
    await sweep.run_sweep()


if __name__ == "__main__":
    asyncio.run(main())