#!/usr/bin/env python3
"""
Parameter sweep script for systematic testing of all screener and backtest parameter combinations.

This script:
1. Generates all parameter combinations from specified ranges
2. Creates a pipeline config for each combination
3. Runs the screener-backtest pipeline for each config
4. Tracks progress and allows resuming
"""

import asyncio
import logging
import sys
import yaml
import json
from datetime import datetime
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


class ParameterSweep:
    """Manages parameter sweep execution."""
    
    def __init__(self, base_config_path: str = "pipeline_config.yaml", 
                 progress_file: str = "parameter_sweep_progress.json"):
        """Initialize parameter sweep."""
        self.base_config_path = Path(base_config_path)
        self.progress_file = Path(progress_file)
        self.base_config = self._load_base_config()
        self.completed_combinations = self._load_progress()
        
        # Define parameter ranges
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
    
    def _load_progress(self) -> set:
        """Load completed combinations from progress file."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                return set(data.get('completed', []))
        return set()
    
    def _save_progress(self, combination_hash: str):
        """Save progress after completing a combination."""
        self.completed_combinations.add(combination_hash)
        
        # Load existing progress data
        progress_data = {}
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                progress_data = json.load(f)
        
        # Update with new data
        progress_data['completed'] = list(self.completed_combinations)
        progress_data['last_updated'] = datetime.now().isoformat()
        
        # Save back to file
        with open(self.progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
    
    def _generate_combination_hash(self, params: Dict[str, Any]) -> str:
        """Generate unique hash for a parameter combination."""
        # Create a deterministic string representation
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()
    
    def _create_config_for_combination(self, combination: Dict[str, Any]) -> Dict[str, Any]:
        """Create a pipeline config for a specific parameter combination."""
        # Deep copy base config
        config = json.loads(json.dumps(self.base_config))
        
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
            # Use default values for other relative volume params if not specified
            config['screening']['filters']['relative_volume']['recent_days'] = 2
            config['screening']['filters']['relative_volume']['lookback_days'] = 20
        else:
            config['screening']['filters']['relative_volume']['enabled'] = False
        
        # Update backtest parameters
        config['backtesting']['parameters']['pivot_bars'] = combination['backtest']['pivot_bars']
        config['backtesting']['parameters']['lower_timeframe'] = combination['backtest']['lower_timeframe']
        
        # RSI
        if screener_params['rsi']['enabled']:
            config['screening']['filters']['rsi']['enabled'] = True
            config['screening']['filters']['rsi']['rsi_period'] = screener_params['rsi']['period']
            config['screening']['filters']['rsi']['threshold'] = screener_params['rsi']['threshold']
            config['screening']['filters']['rsi']['condition'] = screener_params['rsi']['condition']
        else:
            config['screening']['filters']['rsi']['enabled'] = False
        
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
    
    def _save_combination_config(self, combination: Dict[str, Any], index: int) -> str:
        """Save configuration for a specific combination and return the file path."""
        # Create configs directory if it doesn't exist
        configs_dir = Path("parameter_sweep_configs")
        configs_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"config_{index:05d}_{timestamp}.yaml"
        filepath = configs_dir / filename
        
        # Create config for this combination
        config = self._create_config_for_combination(combination)
        
        # Save to file
        with open(filepath, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return str(filepath)
    
    def _log_combination_details(self, combination: Dict[str, Any], index: int, total: int):
        """Log details about the current combination."""
        logger.info(f"\n{'='*80}")
        logger.info(f"COMBINATION {index}/{total}")
        logger.info(f"{'='*80}")
        
        # Screener parameters
        s = combination['screener']
        logger.info("Screener Parameters:")
        logger.info(f"  - Price Range: ${s['price_range'][0]} - ${s['price_range'][1]}")
        
        if s['price_vs_ma']['enabled']:
            logger.info(f"  - Price vs MA: {s['price_vs_ma']['condition']} MA{s['price_vs_ma']['period']}")
        else:
            logger.info(f"  - Price vs MA: Disabled")
        
        if s['gap']['enabled']:
            logger.info(f"  - Gap: {s['gap']['threshold']}% {s['gap']['direction']}")
        else:
            logger.info(f"  - Gap: Disabled")
        
        logger.info(f"  - Volume: ${s['prev_day_dollar_volume']:,}")
        
        if s['relative_volume']['enabled']:
            logger.info(f"  - Relative Volume: {s['relative_volume']['ratio']}x")
        else:
            logger.info(f"  - Relative Volume: Disabled")
        
        if s['rsi']['enabled']:
            logger.info(f"  - RSI: {s['rsi']['condition']} {s['rsi']['threshold']}")
        else:
            logger.info(f"  - RSI: Disabled")
        
        # Backtest parameters
        logger.info("Backtest Parameters:")
        logger.info(f"  - Pivot Bars: {combination['backtest']['pivot_bars']}")
        logger.info(f"  - Timeframe: {combination['backtest']['lower_timeframe']}")
        logger.info(f"{'='*80}")
    
    async def run_combination(self, combination: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Run pipeline for a single parameter combination."""
        # Save config for this combination
        config_path = self._save_combination_config(combination, index)
        
        try:
            # Create and run pipeline with this config
            pipeline = ScreenerBacktestPipeline(config_path)
            
            # Run the pipeline
            await pipeline.run()
            
            # Return summary results
            return {
                'success': True,
                'combination': combination,
                'config_path': config_path
            }
            
        except Exception as e:
            logger.error(f"Failed to run combination {index}: {e}")
            return {
                'success': False,
                'combination': combination,
                'config_path': config_path,
                'error': str(e)
            }
        finally:
            # Ensure cleanup
            if 'pipeline' in locals():
                await pipeline.cleanup()
    
    async def run_sweep(self):
        """Run the complete parameter sweep."""
        logger.info("="*80)
        logger.info("PARAMETER SWEEP EXECUTION")
        logger.info("="*80)
        
        # Generate all combinations
        all_combinations = self._generate_all_combinations()
        total_combinations = len(all_combinations)
        
        logger.info(f"Total parameter combinations: {total_combinations:,}")
        logger.info(f"Previously completed: {len(self.completed_combinations):,}")
        logger.info(f"Remaining to process: {total_combinations - len(self.completed_combinations):,}")
        
        # Track results
        results_summary = {
            'total': total_combinations,
            'completed': 0,
            'skipped': 0,
            'failed': 0,
            'start_time': datetime.now().isoformat(),
            'results': []
        }
        
        # Process each combination
        for i, combination in enumerate(all_combinations, 1):
            # Check if already completed
            combo_hash = self._generate_combination_hash(combination)
            if combo_hash in self.completed_combinations:
                logger.info(f"Skipping combination {i}/{total_combinations} (already completed)")
                results_summary['skipped'] += 1
                continue
            
            # Log combination details
            self._log_combination_details(combination, i, total_combinations)
            
            # Run the combination
            start_time = datetime.now()
            result = await self.run_combination(combination, i)
            end_time = datetime.now()
            
            # Add timing info
            result['execution_time'] = (end_time - start_time).total_seconds()
            results_summary['results'].append(result)
            
            # Update progress
            if result['success']:
                results_summary['completed'] += 1
                self._save_progress(combo_hash)
                logger.info(f"Combination {i} completed successfully in {result['execution_time']:.1f} seconds")
            else:
                results_summary['failed'] += 1
                logger.error(f"Combination {i} failed: {result.get('error', 'Unknown error')}")
            
            # Log progress
            logger.info(f"Progress: {results_summary['completed'] + results_summary['skipped']}/{total_combinations} "
                       f"(Completed: {results_summary['completed']}, Skipped: {results_summary['skipped']}, "
                       f"Failed: {results_summary['failed']})")
        
        # Save final summary
        results_summary['end_time'] = datetime.now().isoformat()
        summary_file = Path(f"parameter_sweep_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(summary_file, 'w') as f:
            json.dump(results_summary, f, indent=2)
        
        # Print final summary
        logger.info("\n" + "="*80)
        logger.info("PARAMETER SWEEP COMPLETED")
        logger.info("="*80)
        logger.info(f"Total combinations: {total_combinations:,}")
        logger.info(f"Completed: {results_summary['completed']:,}")
        logger.info(f"Skipped (previously completed): {results_summary['skipped']:,}")
        logger.info(f"Failed: {results_summary['failed']:,}")
        logger.info(f"Summary saved to: {summary_file}")
        
        # Calculate success rate
        attempted = results_summary['completed'] + results_summary['failed']
        if attempted > 0:
            success_rate = (results_summary['completed'] / attempted) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")


async def main():
    """Main entry point."""
    # Check if custom base config provided
    base_config = sys.argv[1] if len(sys.argv) > 1 else "pipeline_config.yaml"
    
    # Create and run parameter sweep
    sweep = ParameterSweep(base_config)
    await sweep.run_sweep()


if __name__ == "__main__":
    asyncio.run(main())