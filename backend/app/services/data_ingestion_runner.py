"""Runs data ingestion tasks through existing scripts."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class DataIngestionRunner:
    """Executes ingestion scripts and surfaces basic metadata."""

    def __init__(self, scripts_path: Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[2] / 'backend' / 'scripts'
        self.scripts_path = scripts_path or default_path

    async def run(self, job_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        dataset = config.get('dataset', 'minute')
        if dataset != 'minute':  # pragma: no cover - defensive
            raise ValueError(f'Unsupported dataset: {dataset}')

        start_date = config.get('start_date')
        end_date = config.get('end_date')
        if not start_date or not end_date:
            raise ValueError('start_date and end_date are required for ingestion jobs')

        resume = config.get('resume', False)

        script_path = self.scripts_path / 'download_historical_minute_data.py'
        if not script_path.exists():  # pragma: no cover - defensive
            raise FileNotFoundError(f'Ingestion script missing: {script_path}')

        args = [
            'python3',
            str(script_path),
            '--start',
            str(start_date),
            '--end',
            str(end_date),
        ]
        if resume:
            args.append('--resume')

        logger.info('Running ingestion job %s with args: %s', job_id, args)

        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(self.scripts_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode() if stderr else stdout.decode()
            logger.error('Ingestion job %s failed: %s', job_id, error_message)
            raise RuntimeError(f'Data ingestion failed: {error_message}')

        log_path = self.scripts_path / 'historical_minute_download.log'
        logger.info('Ingestion job %s completed', job_id)

        return {
            'result_path': str(log_path) if log_path.exists() else None,
            'stdout': stdout.decode(),
        }


__all__ = ['DataIngestionRunner']
