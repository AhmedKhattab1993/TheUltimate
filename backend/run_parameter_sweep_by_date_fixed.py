#!/usr/bin/env python3
"""
Parameter sweep script that processes all combinations for each date before moving to the next date.
FIXED VERSION: Ensures all combinations for a date use the same session ID.

This script:
1. For each trading day:
   - Generates all parameter combinations
   - Runs all combinations for that specific day with the SAME session ID
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
from uuid import uuid4, UUID

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent))

from run_screener_backtest_pipeline import ScreenerBacktestPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DateBasedParameterSweepFixed:
    """Manages parameter sweep execution by date with shared session IDs."""
    
    def __init__(self, base_config_path: str = "pipeline_config.yaml", 
                 progress_file: str = "parameter_sweep_by_date_progress_fixed.json"):
        """Initialize parameter sweep."""
        self.base_config_path = Path(base_config_path)
        self.progress_file = Path(progress_file)
        self.base_config = self._load_base_config()
        self.completed_combinations = self._load_progress()
        
        # Define parameter ranges (same as before)
        self.parameter_ranges = {
            'screener': {
                'price_range': [
                    {'min_price': 1, 'max_price': 20},
                    {'min_price': 20, 'max_price': 10000},
                    {'min_price': 20, 'max_price': 100},
                    {'min_price': 100, 'max_price': 10000}
                ],
                'price_vs_ma': [
                    {'enabled': False},
                    {'enabled': True, 'ma_period': 50, 'condition': 'above'},
                    {'enabled': True, 'ma_period': 50, 'condition': 'below'},
                    {'enabled': True, 'ma_period': 200, 'condition': 'above'},
                    {'enabled': True, 'ma_period': 200, 'condition': 'below'}
                ],
                'rsi': [
                    {'enabled': False},
                    {'enabled': True, 'period': 14, 'condition': 'above', 'threshold': 50},
                    {'enabled': True, 'period': 14, 'condition': 'above', 'threshold': 60},
                    {'enabled': True, 'period': 14, 'condition': 'above', 'threshold': 70},
                    {'enabled': True, 'period': 14, 'condition': 'above', 'threshold': 80},
                    {'enabled': True, 'period': 14, 'condition': 'above', 'threshold': 90},
                    {'enabled': True, 'period': 14, 'condition': 'below', 'threshold': 50},
                    {'enabled': True, 'period': 14, 'condition': 'below', 'threshold': 40},
                    {'enabled': True, 'period': 14, 'condition': 'below', 'threshold': 30},
                    {'enabled': True, 'period': 14, 'condition': 'below', 'threshold': 20},
                    {'enabled': True, 'period': 14, 'condition': 'below', 'threshold': 10}
                ],
                'gap': [
                    {'enabled': False},
                    {'enabled': True, 'gap_threshold': 1, 'direction': 'up'},
                    {'enabled': True, 'gap_threshold': 2, 'direction': 'up'},
                    {'enabled': True, 'gap_threshold': 3, 'direction': 'up'},
                    {'enabled': True, 'gap_threshold': 4, 'direction': 'up'},
                    {'enabled': True, 'gap_threshold': 5, 'direction': 'up'},
                    {'enabled': True, 'gap_threshold': 1, 'direction': 'down'},
                    {'enabled': True, 'gap_threshold': 2, 'direction': 'down'},
                    {'enabled': True, 'gap_threshold': 3, 'direction': 'down'},
                    {'enabled': True, 'gap_threshold': 4, 'direction': 'down'},
                    {'enabled': True, 'gap_threshold': 5, 'direction': 'down'},
                    {'enabled': True, 'gap_threshold': 1, 'direction': 'both'},
                    {'enabled': True, 'gap_threshold': 2, 'direction': 'both'},
                    {'enabled': True, 'gap_threshold': 3, 'direction': 'both'},
                    {'enabled': True, 'gap_threshold': 4, 'direction': 'both'},
                    {'enabled': True, 'gap_threshold': 5, 'direction': 'both'}
                ],
                'prev_day_dollar_volume': [
                    {'enabled': True, 'min_dollar_volume': 10000000},    # 10M
                    {'enabled': True, 'min_dollar_volume': 100000000},   # 100M
                    {'enabled': True, 'min_dollar_volume': 1000000000}   # 1B
                ],
                'relative_volume': [
                    {'enabled': False},
                    {'enabled': True, 'recent_days': 1, 'lookback_days': 10, 'min_ratio': 2},
                    {'enabled': True, 'recent_days': 1, 'lookback_days': 10, 'min_ratio': 3}
                ]
            },
            'backtest': {
                'pivot_bars': list(range(1, 11))  # 1 to 10
            }
        }
    
    def _load_base_config(self) -> Dict[str, Any]:
        """Load base configuration from YAML file."""
        if not self.base_config_path.exists():
            raise FileNotFoundError(f"Base configuration file not found: {self.base_config_path}")
        
        with open(self.base_config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _load_progress(self) -> Dict[str, set]:
        """Load progress data from JSON file."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                # Convert lists back to sets
                return {date_str: set(combos) for date_str, combos in data.items()}
        return {}
    
    def _save_progress(self, date_str: str, combination_hash: str):
        """Save progress for a completed combination."""
        if date_str not in self.completed_combinations:
            self.completed_combinations[date_str] = set()
        
        self.completed_combinations[date_str].add(combination_hash)
        
        # Convert sets to lists for JSON serialization
        data_to_save = {date_str: list(combos) for date_str, combos in self.completed_combinations.items()}
        
        with open(self.progress_file, 'w') as f:
            json.dump(data_to_save, f, indent=2)
    
    def _generate_combination_hash(self, combination: Dict[str, Any]) -> str:
        """Generate a unique hash for a parameter combination."""
        combo_str = json.dumps(combination, sort_keys=True)
        return hashlib.md5(combo_str.encode()).hexdigest()
    
    def _generate_all_combinations(self) -> List[Dict[str, Any]]:
        """Generate all parameter combinations."""
        screener_params = self.parameter_ranges['screener']
        backtest_params = self.parameter_ranges['backtest']
        
        # Create all screener combinations
        screener_combinations = list(product(
            screener_params['price_range'],
            screener_params['price_vs_ma'],
            screener_params['rsi'],
            screener_params['gap'],
            screener_params['prev_day_dollar_volume'],
            screener_params['relative_volume']
        ))
        
        # Create all combinations including backtest parameters
        all_combinations = []
        for screener_combo in screener_combinations:
            for pivot_bars in backtest_params['pivot_bars']:
                combination = {
                    'screener': {
                        'price_range': screener_combo[0],
                        'price_vs_ma': screener_combo[1],
                        'rsi': screener_combo[2],
                        'gap': screener_combo[3],
                        'prev_day_dollar_volume': screener_combo[4],
                        'relative_volume': screener_combo[5]
                    },
                    'backtest': {
                        'pivot_bars': pivot_bars
                    }
                }
                all_combinations.append(combination)
        
        return all_combinations
    
    def _get_trading_days(self, start_date: str, end_date: str) -> List[date]:
        """
        Get all trading days between start and end dates (backward order).
        Excludes weekends (Saturday=5, Sunday=6).
        """
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        trading_days = []
        current = end
        
        while current >= start:
            # Check if it's a weekday (Monday=0 to Friday=4)
            if current.weekday() < 5:
                trading_days.append(current)
            current = current - timedelta(days=1)
        
        return trading_days
    
    def _save_combination_config(self, combination: Dict[str, Any], trading_date: date, index: int) -> str:
        """Save configuration for a specific parameter combination and date."""
        # Create a deep copy of base config
        config = json.loads(json.dumps(self.base_config))
        
        # Update date range to single day
        date_str = trading_date.strftime('%Y-%m-%d')
        config['screening']['date_range']['start'] = date_str
        config['screening']['date_range']['end'] = date_str
        
        # Apply screener parameters
        screener_params = combination['screener']
        filters = config['screening']['filters']
        
        # Price range
        pr = screener_params['price_range']
        filters['price_range']['enabled'] = True
        filters['price_range']['min_price'] = pr['min_price']
        filters['price_range']['max_price'] = pr['max_price']
        
        # Price vs MA
        pma = screener_params['price_vs_ma']
        filters['price_vs_ma']['enabled'] = pma['enabled']
        if pma['enabled']:
            filters['price_vs_ma']['ma_period'] = pma['ma_period']
            filters['price_vs_ma']['condition'] = pma['condition']
        
        # RSI
        rsi = screener_params['rsi']
        filters['rsi']['enabled'] = rsi['enabled']
        if rsi['enabled']:
            filters['rsi']['period'] = rsi['period']
            filters['rsi']['condition'] = rsi['condition']
            filters['rsi']['threshold'] = rsi['threshold']
        
        # Gap
        gap = screener_params['gap']
        filters['gap']['enabled'] = gap['enabled']
        if gap['enabled']:
            filters['gap']['gap_threshold'] = gap['gap_threshold']
            filters['gap']['direction'] = gap['direction']
        
        # Previous day dollar volume
        pddv = screener_params['prev_day_dollar_volume']
        filters['prev_day_dollar_volume']['enabled'] = pddv['enabled']
        filters['prev_day_dollar_volume']['min_dollar_volume'] = pddv['min_dollar_volume']
        
        # Relative volume
        rv = screener_params['relative_volume']
        filters['relative_volume']['enabled'] = rv['enabled']
        if rv['enabled']:
            filters['relative_volume']['recent_days'] = rv['recent_days']
            filters['relative_volume']['lookback_days'] = rv['lookback_days']
            filters['relative_volume']['min_ratio'] = rv['min_ratio']
        
        # Apply backtest parameters
        config['backtesting']['parameters']['pivot_bars'] = combination['backtest']['pivot_bars']
        
        # Create unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"config_{index:05d}_{timestamp}.yaml"
        filepath = Path("parameter_sweep_configs") / filename
        filepath.parent.mkdir(exist_ok=True)
        
        # Save to file
        with open(filepath, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return str(filepath)
    
    async def run_combination(self, combination: Dict[str, Any], trading_date: date, index: int, session_id: UUID) -> Dict[str, Any]:
        """Run pipeline for a single parameter combination on a specific date with shared session ID."""
        # Save config for this combination
        config_path = self._save_combination_config(combination, trading_date, index)
        
        try:
            # DIAGNOSTIC LOGGING
            logger.info(f"[DIAGNOSTIC] ========== COMBINATION {index} ==========")
            logger.info(f"[DIAGNOSTIC] Date: {trading_date}")
            logger.info(f"[DIAGNOSTIC] Shared session ID for date: {session_id}")
            logger.info(f"[DIAGNOSTIC] Config path: {config_path}")
            
            # Create pipeline with this config
            pipeline = ScreenerBacktestPipeline(config_path)
            
            logger.info(f"[DIAGNOSTIC] Pipeline created with auto-generated session ID: {pipeline.pipeline_session_id}")
            logger.info(f"[DIAGNOSTIC] Queue manager initial session ID: {pipeline.queue_manager.screener_session_id}")
            
            # CRITICAL FIX: Override the session ID to use the shared one for this date
            pipeline.pipeline_session_id = session_id
            pipeline.queue_manager.screener_session_id = session_id
            
            logger.info(f"[DIAGNOSTIC] OVERRIDE: Pipeline session ID set to: {pipeline.pipeline_session_id}")
            logger.info(f"[DIAGNOSTIC] OVERRIDE: Queue manager session ID set to: {pipeline.queue_manager.screener_session_id}")
            logger.info(f"[DIAGNOSTIC] Verifying they match: {pipeline.pipeline_session_id == pipeline.queue_manager.screener_session_id}")
            
            # Run the pipeline (it will only process the single date in the config)
            await pipeline.run()
            
            # DIAGNOSTIC: Verify data was saved correctly
            logger.info(f"[DIAGNOSTIC] Pipeline run completed for combination {index}")
            
            # Add a small delay to ensure database writes complete
            await asyncio.sleep(0.5)
            
            # Verify screener results and links
            try:
                from app.services.database import db_pool
                
                # Ensure db_pool is initialized
                if db_pool is None:
                    logger.warning("[DIAGNOSTIC] db_pool is None, skipping verification")
                    screener_count = -1
                    link_count = -1
                else:
                    # Check screener results
                    screener_count = await db_pool.fetchval("""
                        SELECT COUNT(*) FROM screener_results 
                        WHERE session_id = $1 AND data_date = $2
                    """, session_id, trading_date)
                    
                    # Check backtest links
                    link_count = await db_pool.fetchval("""
                        SELECT COUNT(*) FROM screener_backtest_links
                        WHERE screener_session_id = $1 AND data_date = $2
                    """, session_id, trading_date)
            except Exception as e:
                logger.warning(f"[DIAGNOSTIC] Error during verification: {e}")
                screener_count = -1
                link_count = -1
            
            logger.info(f"[DIAGNOSTIC] VERIFICATION for combination {index}:")
            logger.info(f"[DIAGNOSTIC]   - Screener results with session {session_id}: {screener_count}")
            logger.info(f"[DIAGNOSTIC]   - Backtest links with session {session_id}: {link_count}")
            
            # Return summary results
            return {
                'success': True,
                'date': trading_date.strftime('%Y-%m-%d'),
                'combination': combination,
                'config_path': config_path,
                'session_id': str(session_id),
                'screener_count': screener_count,
                'link_count': link_count
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
        """Run all parameter combinations for a specific date with shared session ID."""
        date_str = trading_date.strftime('%Y-%m-%d')
        logger.info(f"\n{'='*80}")
        logger.info(f"PROCESSING DATE: {date_str}")
        logger.info(f"{'='*80}")
        
        # Generate a single session ID for all combinations on this date
        date_session_id = uuid4()
        logger.info(f"[DIAGNOSTIC] ============================================")
        logger.info(f"[DIAGNOSTIC] STARTING DATE: {date_str}")
        logger.info(f"[DIAGNOSTIC] Generated session ID for ALL combinations on this date: {date_session_id}")
        logger.info(f"[DIAGNOSTIC] ============================================")
        
        # Get completed combinations for this date
        completed_for_date = self.completed_combinations.get(date_str, set())
        
        # Track results for this date
        date_results = {
            'date': date_str,
            'session_id': str(date_session_id),
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
            
            # Run the combination with shared session ID
            logger.info(f"[{date_str}] Running combination {i}/{len(combinations)} with session {date_session_id}")
            start_time = datetime.now()
            result = await self.run_combination(combination, trading_date, i, date_session_id)
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
        logger.info("DATE-BASED PARAMETER SWEEP EXECUTION (FIXED)")
        logger.info("="*80)
        
        # Generate all combinations
        all_combinations = self._generate_all_combinations()
        
        # Calculate screener-only combinations (for caching efficiency)
        screener_only_combinations = len(self.parameter_ranges['screener']['price_range']) * \
                                   len(self.parameter_ranges['screener']['price_vs_ma']) * \
                                   len(self.parameter_ranges['screener']['rsi']) * \
                                   len(self.parameter_ranges['screener']['gap']) * \
                                   len(self.parameter_ranges['screener']['prev_day_dollar_volume']) * \
                                   len(self.parameter_ranges['screener']['relative_volume'])
        
        logger.info(f"Total parameter combinations: {len(all_combinations)}")
        logger.info(f"Unique screener combinations: {screener_only_combinations}")
        logger.info(f"Backtest variations per screener: {len(self.parameter_ranges['backtest']['pivot_bars'])}")
        
        # Get trading days to process (in backward order)
        start_date = self.base_config['screening']['date_range']['start']
        end_date = self.base_config['screening']['date_range']['end']
        trading_days = self._get_trading_days(start_date, end_date)
        
        logger.info(f"Trading days to process: {len(trading_days)} (from {end_date} to {start_date})")
        logger.info("="*80)
        
        # Track overall progress
        overall_results = {
            'start_time': datetime.now().isoformat(),
            'total_days': len(trading_days),
            'total_combinations_per_day': len(all_combinations),
            'days_completed': 0,
            'daily_results': []
        }
        
        # Process each trading day
        for day_index, trading_date in enumerate(trading_days, 1):
            logger.info(f"\n[DAY {day_index}/{len(trading_days)}] Starting processing for {trading_date}")
            
            # Run all combinations for this date
            date_results = await self.run_all_combinations_for_date(trading_date, all_combinations)
            overall_results['daily_results'].append(date_results)
            overall_results['days_completed'] += 1
            
            # Summary for this date
            logger.info(f"\n[DAY {day_index}/{len(trading_days)}] Completed {trading_date}:")
            logger.info(f"  Completed: {date_results['completed']}")
            logger.info(f"  Skipped: {date_results['skipped']}")
            logger.info(f"  Failed: {date_results['failed']}")
            logger.info(f"  Session ID: {date_results['session_id']}")
        
        overall_results['end_time'] = datetime.now().isoformat()
        
        # Final summary
        logger.info("\n" + "="*80)
        logger.info("PARAMETER SWEEP COMPLETED")
        logger.info("="*80)
        logger.info(f"Total days processed: {overall_results['days_completed']}")
        
        total_completed = sum(dr['completed'] for dr in overall_results['daily_results'])
        total_skipped = sum(dr['skipped'] for dr in overall_results['daily_results'])
        total_failed = sum(dr['failed'] for dr in overall_results['daily_results'])
        
        logger.info(f"Total combinations completed: {total_completed}")
        logger.info(f"Total combinations skipped: {total_skipped}")
        logger.info(f"Total combinations failed: {total_failed}")
        
        # Save final results
        results_file = Path(f"parameter_sweep_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(results_file, 'w') as f:
            json.dump(overall_results, f, indent=2)
        
        logger.info(f"\nResults saved to: {results_file}")


async def main():
    """Main entry point."""
    sweep = DateBasedParameterSweepFixed()
    await sweep.run_sweep()


if __name__ == "__main__":
    asyncio.run(main())