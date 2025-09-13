#!/usr/bin/env python3
"""
Regenerate metadata files to include orders data.
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the Python path
sys.path.append(str(Path(__file__).parent))

from app.services.backtest_storage import BacktestStorage


async def regenerate_metadata():
    """Regenerate all metadata files in MarketStructure backtests."""
    base_path = Path("/home/ahmed/TheUltimate/backend/lean/MarketStructure/backtests")
    storage = BacktestStorage(strategy_name="MarketStructure")
    
    count = 0
    for backtest_dir in sorted(base_path.iterdir()):
        if not backtest_dir.is_dir():
            continue
            
        metadata_file = backtest_dir / "backtest_metadata.json"
        
        # Regenerate the metadata by calling save_result again
        print(f"Regenerating metadata for {backtest_dir.name}...")
        
        # Get the config file to extract parameters
        config_file = backtest_dir / "config"
        if config_file.exists():
            import json
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            params = config_data.get("parameters", {})
            from datetime import datetime
            
            # Parse dates
            start_date = datetime.strptime(params.get("startDate", "20130101"), "%Y%m%d").date()
            end_date = datetime.strptime(params.get("endDate", "20131231"), "%Y%m%d").date()
            initial_cash = float(params.get("cash", 100000))
            
            # Regenerate the result
            result = await storage.save_result(
                backtest_id=backtest_dir.name,
                symbol=params.get("symbols", "UNKNOWN"),
                strategy_name="MarketStructure",
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                result_path=str(backtest_dir)
            )
            
            if result:
                count += 1
                print(f"✓ Regenerated {backtest_dir.name} - {len(result.orders or [])} orders")
            else:
                print(f"✗ Failed to regenerate {backtest_dir.name}")
    
    print(f"\nRegenerated {count} metadata files")


if __name__ == "__main__":
    asyncio.run(regenerate_metadata())