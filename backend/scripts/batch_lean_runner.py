#!/usr/bin/env python3
"""
Batch LEAN Runner - Runs multiple backtests in a single LEAN container

This approach amortizes the LEAN initialization cost across multiple backtests.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any
import shutil

class BatchLeanRunner:
    """Runs multiple LEAN backtests in a single container to avoid initialization overhead."""
    
    def __init__(self, project_path: str = "/home/ahmed/TheUltimate/backend/lean/MarketStructure"):
        self.project_path = Path(project_path)
        self.lean_cli = "/home/ahmed/TheUltimate/backend/lean_venv/bin/lean"
        
    def create_batch_config(self, backtests: List[Dict[str, Any]], batch_id: str) -> str:
        """Create a configuration file for batch processing."""
        # Create a temporary directory for this batch
        batch_dir = Path(f"/tmp/lean_batch_{batch_id}")
        batch_dir.mkdir(exist_ok=True)
        
        # Create multiple config files
        config_files = []
        for i, config in enumerate(backtests):
            config_file = batch_dir / f"config_{i}.json"
            
            # Create config for this specific backtest
            lean_config = {
                "algorithm-language": "Python",
                "parameters": {
                    "startDate": config.get('start_date', '20250910'),
                    "endDate": config.get('end_date', '20250910'),
                    "cash": str(config.get('initial_cash', 100000)),
                    "symbols": config.get('symbol', 'AAPL'),
                    "pivot_bars": str(config.get('pivot_bars', 5)),
                    "lower_timeframe": config.get('lower_timeframe', '1min'),
                    "use_screener_results": "false"
                }
            }
            
            with open(config_file, 'w') as f:
                json.dump(lean_config, f, indent=2)
            
            config_files.append(str(config_file))
        
        return batch_dir, config_files
    
    def run_batch_docker(self, configs: List[Dict[str, Any]], batch_id: str) -> Dict[str, Any]:
        """Run batch using direct Docker command with config mounting."""
        start_time = time.time()
        results = []
        
        # Create batch directory
        batch_dir, config_files = self.create_batch_config(configs, batch_id)
        
        # Run single Docker container with all configs
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{self.project_path}:/Algorithm",
            "-v", f"{batch_dir}:/Configs",
            "-v", f"{self.project_path}/data:/data",
            "quantconnect/lean:latest",
            "--data-folder", "/data",
            "--results-destination-folder", "/Algorithm/backtests",
            "--config", "/Lean/Launcher/config.json",
        ]
        
        # For each config, we'll modify the algorithm to process it
        # This is a simplified approach - in practice, you'd need to implement
        # the batch processing logic in the algorithm itself
        
        print(f"Running batch of {len(configs)} backtests in single container...")
        
        # Alternative: Run backtests sequentially in same container
        # This approach keeps the container warm between runs
        
        container_name = f"lean_batch_{batch_id}"
        
        # Start a long-running container
        start_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-v", f"{self.project_path}:/Algorithm",
            "-v", f"{batch_dir}:/Configs",
            "quantconnect/lean:latest",
            "tail", "-f", "/dev/null"  # Keep container running
        ]
        
        try:
            # Start container
            subprocess.run(start_cmd, check=True, capture_output=True)
            print(f"Started container: {container_name}")
            
            # Run each backtest in the same container
            for i, (config, config_file) in enumerate(zip(configs, config_files)):
                print(f"Running backtest {i+1}/{len(configs)}...")
                
                exec_cmd = [
                    "docker", "exec", container_name,
                    "dotnet", "/Lean/Launcher/bin/Debug/QuantConnect.Lean.Launcher.dll",
                    "--config", f"/Configs/config_{i}.json",
                    "--algorithm-type-name", "MarketStructureAlgorithm",
                    "--algorithm-location", "/Algorithm/main.py",
                    "--data-folder", "/Lean/Data",
                    "--results-destination-folder", f"/Algorithm/backtests/batch_{batch_id}_{i}"
                ]
                
                backtest_start = time.time()
                result = subprocess.run(exec_cmd, capture_output=True, text=True)
                backtest_duration = time.time() - backtest_start
                
                results.append({
                    'config': config,
                    'duration': backtest_duration,
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr
                })
                
                print(f"Backtest {i+1} completed in {backtest_duration:.2f}s")
        
        finally:
            # Clean up container
            subprocess.run(["docker", "stop", container_name], capture_output=True)
            subprocess.run(["docker", "rm", container_name], capture_output=True)
            
            # Clean up temp directory
            if batch_dir.exists():
                shutil.rmtree(batch_dir)
        
        total_duration = time.time() - start_time
        
        return {
            'batch_id': batch_id,
            'total_configs': len(configs),
            'total_duration': total_duration,
            'average_duration': total_duration / len(configs) if configs else 0,
            'results': results
        }

def test_batch_processing():
    """Test batch processing with sample configurations."""
    runner = BatchLeanRunner()
    
    # Create test configurations
    test_configs = [
        {'symbol': 'AAPL', 'pivot_bars': 1, 'start_date': '20250910', 'end_date': '20250910'},
        {'symbol': 'AAPL', 'pivot_bars': 2, 'start_date': '20250910', 'end_date': '20250910'},
        {'symbol': 'AAPL', 'pivot_bars': 3, 'start_date': '20250910', 'end_date': '20250910'},
        {'symbol': 'AAPL', 'pivot_bars': 5, 'start_date': '20250910', 'end_date': '20250910'},
        {'symbol': 'AAPL', 'pivot_bars': 10, 'start_date': '20250910', 'end_date': '20250910'},
    ]
    
    batch_id = f"test_{int(time.time())}"
    results = runner.run_batch_docker(test_configs, batch_id)
    
    print("\n=== Batch Processing Results ===")
    print(f"Total configs: {results['total_configs']}")
    print(f"Total duration: {results['total_duration']:.2f}s")
    print(f"Average per backtest: {results['average_duration']:.2f}s")
    
    # Compare to parallel approach
    estimated_parallel_time = 80 * results['total_configs'] / 10  # Assuming 10 parallel
    print(f"\nEstimated parallel approach time: {estimated_parallel_time:.2f}s")
    print(f"Speedup: {estimated_parallel_time / results['total_duration']:.2f}x")

if __name__ == "__main__":
    test_batch_processing()