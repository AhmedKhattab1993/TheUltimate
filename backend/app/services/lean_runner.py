"""
Service for running LEAN backtests using Docker.
"""

import asyncio
import json
import logging
import shutil
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Dict, Any, Optional, List
import uuid
import docker
from docker.models.containers import Container
import fcntl
import time

from ..models.backtest import BacktestRequest
from .screener_repository import screener_repository


logger = logging.getLogger(__name__)


class LeanRunner:
    """Manages LEAN backtest execution using Docker."""
    
    def __init__(self, lean_project_path: str = "/home/ahmed/TheUltimate/backend/lean"):
        self.lean_project_path = Path(lean_project_path)
        try:
            self.docker_client = docker.from_env()
        except docker.errors.DockerException as exc:  # pragma: no cover - environment specific
            logger.warning("Docker unavailable; container management disabled: %s", exc)
            self.docker_client = None
        self.lean_image = "quantconnect/lean:latest"
        
    async def run_grid(
        self,
        job_id: str,
        request: BacktestRequest,
        project_name: str,
        job_config: Dict[str, Any],
        on_result: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """Run a Lean optimization for grid sweeps while streaming intermediate results."""

        try:
            screener_payload = (job_config or {}).get("screener_payload")
            if request.use_screener_results:
                strategy_path = self.lean_project_path / "flexible_main.py"
                if not strategy_path.exists():
                    raise Exception("Flexible strategy not found for screener results")

                if screener_payload:
                    export_symbols = list(screener_payload.get("symbols") or [])
                    export_payload = {
                        "timestamp": screener_payload.get("timestamp") or datetime.now().isoformat(),
                        "symbols": export_symbols,
                        "filters": screener_payload.get("filters") or {},
                        "metadata": screener_payload.get("metadata") or {},
                        "count": len(export_symbols),
                    }
                    if screener_payload.get("date"):
                        export_payload.setdefault("metadata", {})
                        export_payload["metadata"]["target_date"] = screener_payload["date"]
                else:
                    _, runs = await screener_repository.list_runs(limit=1)
                    if not runs:
                        raise Exception("No screener runs available for Lean optimization")

                    run_detail = await screener_repository.get_run(runs[0].id)
                    if not run_detail or not run_detail.results:
                        raise Exception("Latest screener run does not contain any symbols")

                    export_symbols = [result.symbol for result in run_detail.results]
                    export_payload = {
                        "timestamp": run_detail.created_at.isoformat(),
                        "symbols": export_symbols,
                        "filters": run_detail.filters,
                        "metadata": run_detail.metadata,
                        "count": len(export_symbols),
                    }

                if not export_symbols:
                    raise Exception("Screener payload does not contain any symbols")

                results_dir = self.lean_project_path.parent / "screener_results"
                results_dir.mkdir(parents=True, exist_ok=True)
                file_suffix = screener_payload.get("run_id") if screener_payload else datetime.now().strftime("%s")
                screener_file = results_dir / f"screener_results_{file_suffix}.json"
                screener_file.write_text(json.dumps(export_payload, indent=2))

                request.parameters["screener_results_file"] = str(screener_file)
                logger.info(f"Using screener results from {screener_file}")

            project_path = self.lean_project_path / project_name
            base_config_path = project_path / "config.json"
            temp_config_path = project_path / f"config_{job_id}.json"

            config_data = {}
            if base_config_path.exists():
                with open(base_config_path, 'r') as f:
                    config_data = json.load(f)

            if "parameters" not in config_data:
                config_data["parameters"] = {}

            # Ensure stale symbol lists do not leak between optimize runs
            config_data["parameters"].pop("symbols", None)

            config_data["parameters"]["startDate"] = request.start_date.strftime("%Y%m%d")
            config_data["parameters"]["endDate"] = request.end_date.strftime("%Y%m%d")
            config_data["parameters"]["cash"] = str(request.initial_cash)

            config_data["parameters"]["lower_timeframe"] = request.lower_timeframe
            config_data["parameters"]["pivot_bars"] = str(request.pivot_bars)

            request.parameters = request.parameters or {}

            symbol_map = (job_config or {}).get("symbol_map")
            symbol_map_path: Optional[Path] = None
            if symbol_map:
                symbol_map_path = project_path / f"symbol_mapping_{job_id}.json"
                with open(symbol_map_path, 'w') as mapping_file:
                    json.dump(symbol_map, mapping_file, indent=2)
                config_data["parameters"]["symbol_mapping_file"] = str(symbol_map_path)

            for key, value in request.parameters.items():
                config_data["parameters"][key] = str(value)

            with open(temp_config_path, 'w') as f:
                json.dump(config_data, f, indent=4)

            lock_path = base_config_path.with_suffix('.lock')
            lock_acquired = False
            start_lock_time = time.time()

            while not lock_acquired and (time.time() - start_lock_time) < 30:
                try:
                    lock_file = open(lock_path, 'w')
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                    shutil.copy2(temp_config_path, base_config_path)
                except (IOError, OSError):
                    await asyncio.sleep(0.1)
                finally:
                    if lock_acquired:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                        lock_file.close()
                        try:
                            lock_path.unlink()
                        except Exception:
                            pass

            if not lock_acquired:
                raise Exception("Failed to acquire config lock after 30 seconds")

            lean_bin = "/home/ahmed/TheUltimate/backend/lean_venv/bin/lean"
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            unique_suffix = job_id[:8]
            output_dir = self.lean_project_path / project_name / "optimizations" / f"{timestamp}_{unique_suffix}"

            optimize_config = (job_config or {}).get("optimize") or {}
            target_metric = optimize_config.get("target_metric", "SharpeRatio")
            direction = optimize_config.get("target_direction", "maximize")
            direction_flag = "max" if str(direction).lower().startswith("max") else "min"
            strategy_mode = (optimize_config.get("strategy") or "grid search").lower()
            if strategy_mode not in {"grid search", "euler search"}:
                strategy_mode = "grid search"

            lean_cmd: List[str] = [
                lean_bin,
                "optimize",
                project_name,
                "--output",
                str(output_dir),
                "--strategy",
                strategy_mode,
                "--target",
                target_metric,
                "--target-direction",
                direction_flag,
            ]

            max_concurrent = optimize_config.get("max_concurrent_backtests")
            if max_concurrent:
                lean_cmd.extend([
                    "--max-concurrent-backtests",
                    str(max_concurrent),
                ])

            for parameter in optimize_config.get("parameters", []):
                name = parameter.get("name")
                min_value = parameter.get("min")
                max_value = parameter.get("max")
                step = parameter.get("step")
                if name is None or min_value is None or max_value is None or step is None:
                    continue
                lean_cmd.extend([
                    "--parameter",
                    str(name),
                    str(min_value),
                    str(max_value),
                    str(step),
                ])

            process = await asyncio.create_subprocess_exec(
                *lean_cmd,
                cwd=str(self.lean_project_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stop_event = asyncio.Event()
            processed_dirs: set[str] = set()

            async def stream_results() -> None:
                try:
                    while not stop_event.is_set():
                        await self._collect_grid_results(
                            output_dir,
                            processed_dirs,
                            on_result,
                        )
                        await asyncio.sleep(2)
                finally:
                    await self._collect_grid_results(
                        output_dir,
                        processed_dirs,
                        on_result,
                    )

            poll_task = asyncio.create_task(stream_results())
            stdout, stderr = await process.communicate()
            stop_event.set()
            await poll_task

            try:
                temp_config_path.unlink()
            except Exception:
                pass
            if symbol_map_path:
                try:
                    symbol_map_path.unlink()
                except Exception:
                    pass

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else stdout.decode()
                logger.error(f"LEAN grid optimize failed: {error_msg}")
                raise Exception(f"LEAN grid optimize failed: {error_msg}")

            if not output_dir.exists():
                logger.warning("Grid optimization output directory not found: %s", output_dir)

            result_payload: Dict[str, Any] = {
                "result_path": str(output_dir),
                "processed_runs": len(processed_dirs),
            }
            backtest_payload = self._load_backtest_output(output_dir)
            if backtest_payload:
                backtest_payload.setdefault("result_path", str(output_dir))
                result_payload["result"] = backtest_payload

            return result_payload

        except Exception as exc:
            logger.error("Failed to run grid job %s: %s", job_id, exc)
            raise

    async def _collect_grid_results(
        self,
        results_root: Path,
        processed_dirs: set[str],
        on_result: Optional[Callable[[Dict[str, Any]], Awaitable[None]]],
    ) -> None:
        if not on_result or not results_root.exists():
            return

        candidates: List[Path] = []
        legacy_backtests = results_root / "backtests"
        if legacy_backtests.exists():
            candidates.extend(path for path in legacy_backtests.iterdir() if path.is_dir())
        else:
            for entry in results_root.iterdir():
                if not entry.is_dir():
                    continue
                if entry.name in {"code", "config"}:
                    continue
                candidates.append(entry)

        for candidate in candidates:
            if not candidate.is_dir():
                continue
            identifier = str(candidate.resolve())
            if identifier in processed_dirs:
                continue

            payload = self._load_backtest_output(candidate)
            if not payload:
                continue

            processed_dirs.add(identifier)
            result_payload = {
                "result_path": str(candidate),
                "statistics": payload.get("statistics") or {},
                "runtime_statistics": payload.get("runtime_statistics") or {},
                "raw_statistics": payload.get("raw_statistics") or {},
                "raw_runtime_statistics": payload.get("raw_runtime_statistics") or {},
                "parameters": payload.get("interpreted_parameters") or payload.get("Parameters") or {},
                "status": "completed",
            }

            await on_result(result_payload)

    
    async def get_container_status(self, container_id: str) -> Dict[str, Any]:
        """Get the status of a running container."""
        if not self.docker_client:
            return {
                "status": "unavailable",
                "logs": [],
                "running": False,
            }

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
        if not self.docker_client:
            logger.warning("Cannot stop container %s because Docker is unavailable", container_id)
            return False

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

    # ------------------------------------------------------------------
    # Result parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _load_backtest_output(result_path: Path) -> Optional[Dict[str, Any]]:
        """Load Lean backtest output (statistics/runtime stats) from result directory."""

        payload: Optional[Dict[str, Any]] = None
        source_name = None
        for candidate in ("backtest.json", "result.json", "backtest-result.json"):
            file_path = result_path / candidate
            if file_path.exists():
                try:
                    payload = json.loads(file_path.read_text())
                    source_name = candidate
                    break
                except Exception:  # pragma: no cover - IO heavy path
                    logger.warning("Failed to read %s", file_path, exc_info=True)
        if not payload:
            summary_files = sorted(result_path.glob("*-summary.json"))
            if summary_files:
                try:
                    payload = json.loads(summary_files[0].read_text())
                    source_name = summary_files[0].name
                except Exception:
                    logger.warning("Failed to read summary %s", summary_files[0], exc_info=True)
                    payload = None
        if not payload:
            return None

        stats_raw = payload.get("Statistics") or payload.get("statistics") or {}
        runtime_raw = payload.get("RuntimeStatistics") or payload.get("runtime_statistics") or {}

        # New optimizer summaries embed runtime stats under lowercase keys
        if not runtime_raw and isinstance(payload.get("runtimeStatistics"), dict):
            runtime_raw = payload.get("runtimeStatistics")
        if not stats_raw and isinstance(payload.get("statistics"), dict):
            stats_raw = payload.get("statistics")
        if not stats_raw and isinstance(payload.get("totalPerformance"), dict):
            portfolio_stats = payload.get("totalPerformance", {}).get("portfolioStatistics") or {}
            stats_raw = portfolio_stats
            runtime_raw = payload.get("runtimeStatistics") or runtime_raw

        statistics = LeanRunner._normalise_numeric_map(stats_raw)
        runtime_statistics = LeanRunner._normalise_numeric_map(runtime_raw)

        interpreted_parameters = payload.get("interpreted_parameters")
        if not interpreted_parameters and isinstance(payload.get("algorithmConfiguration"), dict):
            interpreted_parameters = payload["algorithmConfiguration"].get("parameters")

        return {
            "statistics": statistics,
            "raw_statistics": stats_raw,
            "runtime_statistics": runtime_statistics,
            "raw_runtime_statistics": runtime_raw,
            "start_time": payload.get("StartTime") or payload.get("StartDate"),
            "end_time": payload.get("EndTime") or payload.get("EndDate"),
            "interpreted_parameters": interpreted_parameters or payload.get("Parameters"),
            "source_file": source_name,
        }

    @staticmethod
    def _normalise_numeric_map(data: Dict[str, Any]) -> Dict[str, float]:
        normalised: Dict[str, float] = {}
        for key, value in (data or {}).items():
            numeric = LeanRunner._to_float(value)
            if numeric is not None:
                normalised[key] = numeric
        return normalised

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "").replace(",", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None
