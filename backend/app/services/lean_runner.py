"""
Service for running LEAN backtests using Docker.
"""

import os
import asyncio
import json
import logging
import shutil
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import uuid
import docker
from docker.models.containers import Container
import fcntl
import time

from ..models.backtest import BacktestRequest, BacktestStatus


logger = logging.getLogger(__name__)


class LeanRunner:
    """Manages LEAN backtest execution using Docker."""
    
    def __init__(self, lean_project_path: str = "/home/ahmed/TheUltimate/backend/lean"):
        self.lean_project_path = Path(lean_project_path)
        self.docker_client = docker.from_env()
        self.lean_image = "quantconnect/lean:latest"
        
    async def run_backtest(self, 
                          backtest_id: str,
                          request: BacktestRequest,
                          project_name: str) -> Dict[str, Any]:
        """
        Run a LEAN backtest using LEAN CLI.
        
        Args:
            backtest_id: Unique identifier for this backtest
            request: Backtest configuration
            strategy_path: Path to the strategy Python file
            
        Returns:
            Dict containing container_id and result_path
        """
        try:
            # Check if we should use flexible strategy for screener results
            if request.use_screener_results:
                # Use the flexible strategy that can read screener results
                strategy_path = self.lean_project_path / "flexible_main.py"
                if not strategy_path.exists():
                    raise Exception("Flexible strategy not found for screener results")
                
                # Get the latest screener results file
                from ..services.screener_results import screener_results_manager
                latest_results = screener_results_manager.get_latest_results()
                if latest_results:
                    # Save the filepath in parameters
                    results_files = screener_results_manager.list_results()
                    if results_files:
                        screener_file = results_files[0]["filepath"]
                        request.parameters["screener_results_file"] = screener_file
                        logger.info(f"Using screener results from {screener_file}")
            
            # Record timestamp before running LEAN for deterministic folder detection
            start_time = datetime.now()
            
            # No longer need delay since we're using unique output directories
            
            # Create a unique config file for this backtest to avoid race conditions
            project_path = self.lean_project_path / project_name
            base_config_path = project_path / "config.json"
            
            # Create a temporary config file with unique name
            temp_config_path = project_path / f"config_{backtest_id}.json"
            
            # Load base config
            config_data = {}
            if base_config_path.exists():
                with open(base_config_path, 'r') as f:
                    config_data = json.load(f)
            
            # Ensure parameters field exists
            if "parameters" not in config_data:
                config_data["parameters"] = {}
            
            # Update parameters for this backtest
            config_data["parameters"]["startDate"] = request.start_date.strftime("%Y%m%d")
            config_data["parameters"]["endDate"] = request.end_date.strftime("%Y%m%d")
            config_data["parameters"]["cash"] = str(request.initial_cash)
            
            # Add symbols if provided directly
            if request.symbols and not request.use_screener_results:
                config_data["parameters"]["symbols"] = ",".join(request.symbols)
                logger.info(f"Setting symbols parameter for {backtest_id}: {','.join(request.symbols)}")
            
            # Add any custom parameters from the request
            logger.info(f"Request parameters for {backtest_id}: {request.parameters}")
            for key, value in request.parameters.items():
                config_data["parameters"][key] = str(value)
                logger.info(f"Setting parameter {key} = {value} for {backtest_id}")
            
            # Write the temporary config file
            with open(temp_config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            
            logger.info(f"Written config to {temp_config_path} with parameters: {config_data.get('parameters', {})}")
            
            # Acquire a lock before modifying base config
            lock_path = base_config_path.with_suffix('.lock')
            lock_acquired = False
            start_lock_time = time.time()
            
            while not lock_acquired and (time.time() - start_lock_time) < 30:  # 30 second timeout
                try:
                    lock_file = open(lock_path, 'w')
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                    
                    # Copy temp config to base config atomically
                    shutil.copy2(temp_config_path, base_config_path)
                    logger.info(f"Updated config.json with symbols: {config_data['parameters'].get('symbols', 'none')}")
                    
                    # Give LEAN sufficient time to read the config before another process can change it
                    await asyncio.sleep(2.0)
                    
                except (IOError, OSError):
                    # Lock is held by another process, wait and retry
                    await asyncio.sleep(0.1)
                finally:
                    if lock_acquired:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                        lock_file.close()
                        try:
                            lock_path.unlink()
                        except:
                            pass
            
            if not lock_acquired:
                raise Exception("Failed to acquire config lock after 30 seconds")
            
            # Use LEAN CLI from lean_venv (direct command)
            lean_bin = "/home/ahmed/TheUltimate/backend/lean_venv/bin/lean"
            
            # Get Polygon API key from config
            from ..config import settings
            polygon_api_key = settings.polygon_api_key
            
            # Create a unique output directory for this backtest
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            unique_suffix = backtest_id[:8]  # Use first 8 chars of UUID
            output_dir = self.lean_project_path / project_name / "backtests" / f"{timestamp}_{unique_suffix}"
            
            # Build LEAN command with Polygon data provider and output directory
            lean_cmd = [
                lean_bin, 
                "backtest", 
                project_name,
                "--output", str(output_dir),
                "--data-provider-historical", "polygon",
                "--polygon-api-key", polygon_api_key
            ]
            
            # Run the backtest command
            process = await asyncio.create_subprocess_exec(
                *lean_cmd,
                cwd=str(self.lean_project_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Clean up temporary config file
            try:
                temp_config_path.unlink()
            except Exception:
                pass  # Ignore cleanup errors
            
            # Release the lock if we still have it
            try:
                if 'lock_file' in locals() and not lock_file.closed:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
            except:
                pass
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else stdout.decode()
                logger.error(f"LEAN CLI failed: {error_msg}")
                raise Exception(f"LEAN CLI failed: {error_msg}")
            
            # We know the result path since we specified it
            result_path = output_dir
            logger.info(f"LEAN completed successfully. Results in: {result_path}")
            
            if not result_path:
                raise Exception("Could not find LEAN result directory in backtests folder")
            
            # For local LEAN runs (no Docker), we don't have a container ID
            # Check if config file exists for additional info
            config_file = result_path / "config"
            container_id = None
            
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        config_data = json.load(f)
                    container_id = config_data.get("container")
                except:
                    pass  # Config file might not be JSON format for local runs
            
            logger.info(f"Completed backtest {backtest_id} at {result_path}")
            
            return {
                "container_id": container_id,
                "result_path": str(result_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to start backtest {backtest_id}: {e}")
            raise
    
    
    async def get_container_status(self, container_id: str) -> Dict[str, Any]:
        """Get the status of a running container."""
        try:
            container = self.docker_client.containers.get(container_id)
            status = container.status
            
            # Get logs
            logs = container.logs(tail=50).decode('utf-8').split('\n')
            
            return {
                "status": status,
                "logs": logs,
                "running": status == "running"
            }
        except docker.errors.NotFound:
            return {
                "status": "not_found",
                "logs": [],
                "running": False
            }
        except Exception as e:
            logger.error(f"Error getting container status: {e}")
            raise
    
    async def stop_backtest(self, container_id: str) -> bool:
        """Stop a running backtest container."""
        try:
            container = self.docker_client.containers.get(container_id)
            container.stop(timeout=10)
            container.remove()
            logger.info(f"Stopped and removed container {container_id}")
            return True
        except docker.errors.NotFound:
            logger.warning(f"Container {container_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error stopping container {container_id}: {e}")
            raise
    
    def list_strategies(self) -> List[Dict[str, Any]]:
        """List available LEAN strategy projects."""
        strategies = []
        
        # Look for LEAN project directories
        lean_base_dir = self.lean_project_path
        
        # Look for directories that contain main.py (LEAN projects)
        for project_dir in lean_base_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                main_py = project_dir / "main.py"
                config_json = project_dir / "config.json"
                
                # Check if this looks like a LEAN project
                if main_py.exists() and (config_json.exists() or project_dir.name == "test-project"):
                    strategies.append({
                        "name": project_dir.name,
                        "project_path": str(project_dir),
                        "main_py_path": str(main_py),
                        "description": f"LEAN strategy project: {project_dir.name}",
                        "last_modified": datetime.fromtimestamp(main_py.stat().st_mtime)
                    })
        
        return strategies
    
    def get_strategy_details(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get details about a specific strategy project."""
        strategies = self.list_strategies()
        
        for strategy in strategies:
            if strategy["name"] == strategy_name:
                # Read the strategy file to extract parameters
                try:
                    with open(strategy["main_py_path"], 'r') as f:
                        content = f.read()
                        
                    # Simple parameter extraction (can be enhanced)
                    parameters = {}
                    if "self.GetParameter" in content:
                        # Extract parameter names from GetParameter calls
                        import re
                        pattern = r'self\.GetParameter\(["\']([^"\']+)["\']'
                        matches = re.findall(pattern, content)
                        for param in matches:
                            parameters[param] = {"type": "string", "required": False}
                    
                    strategy["parameters"] = parameters
                    strategy["content_preview"] = content[:500] + "..." if len(content) > 500 else content
                    
                except Exception as e:
                    logger.error(f"Error reading strategy file: {e}")
                
                return strategy
        
        return None
    
    async def cleanup_backtest_logs(self, result_paths: List[str], keep_results: bool = True):
        """
        Clean up LEAN backtest log directories.
        
        Args:
            result_paths: List of backtest result directory paths
            keep_results: If True, keep result JSON files and only delete logs
        """
        cleaned_count = 0
        
        for result_path in result_paths:
            try:
                path = Path(result_path)
                if not path.exists():
                    logger.warning(f"Result path does not exist: {result_path}")
                    continue
                
                if keep_results:
                    # Only delete log files, keep JSON results
                    log_files = list(path.glob("*.txt")) + list(path.glob("*.log"))
                    for log_file in log_files:
                        log_file.unlink()
                        logger.debug(f"Deleted log file: {log_file}")
                    cleaned_count += 1
                else:
                    # Delete entire directory
                    shutil.rmtree(path)
                    logger.info(f"Deleted backtest directory: {path}")
                    cleaned_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to clean up {result_path}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} backtest directories")
        return cleaned_count