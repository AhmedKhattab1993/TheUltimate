"""
Cleanup Service for managing post-backtest cleanup operations.

This service:
- Deletes LEAN log folders after backtests
- Provides optional archiving before deletion
- Handles Docker cleanup if needed
- Manages temporary files and directories
"""

import logging
import shutil
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import asyncio

logger = logging.getLogger(__name__)


class CleanupService:
    """Manages cleanup of backtest artifacts and temporary files."""
    
    def __init__(self, archive_dir: str = "./archives"):
        """
        Initialize the cleanup service.
        
        Args:
            archive_dir: Directory to store archives before deletion
        """
        self.archive_dir = Path(archive_dir)
        if self.archive_dir:
            self.archive_dir.mkdir(exist_ok=True)
    
    async def cleanup_backtest_logs(
        self,
        result_paths: List[str],
        archive: bool = False,
        archive_format: str = 'tar.gz'
    ):
        """
        Clean up backtest log directories.
        
        Args:
            result_paths: List of result directory paths to clean up
            archive: Whether to archive before deletion
            archive_format: Format for archives ('tar.gz' or 'zip')
        """
        logger.info(f"Starting cleanup of {len(result_paths)} backtest directories")
        
        cleaned = 0
        failed = 0
        
        for result_path in result_paths:
            try:
                path = Path(result_path)
                if not path.exists():
                    logger.warning(f"Path does not exist: {result_path}")
                    continue
                
                # Archive if requested
                if archive:
                    archive_path = await self._archive_directory(path, archive_format)
                    logger.info(f"Archived {path} to {archive_path}")
                
                # Delete the directory
                if path.is_dir():
                    shutil.rmtree(path)
                    logger.info(f"Deleted directory: {path}")
                    cleaned += 1
                else:
                    logger.warning(f"Not a directory: {path}")
                    
            except Exception as e:
                logger.error(f"Failed to clean up {result_path}: {e}")
                failed += 1
        
        logger.info(f"Cleanup completed: {cleaned} cleaned, {failed} failed")
    
    async def _archive_directory(self, path: Path, format: str = 'tar.gz') -> Path:
        """
        Archive a directory before deletion.
        
        Args:
            path: Directory path to archive
            format: Archive format ('tar.gz' or 'zip')
            
        Returns:
            Path to the created archive
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{path.name}_{timestamp}"
        
        if format == 'tar.gz':
            archive_path = self.archive_dir / f"{archive_name}.tar.gz"
            await self._create_tar_archive(path, archive_path)
        elif format == 'zip':
            archive_path = self.archive_dir / f"{archive_name}.zip"
            await self._create_zip_archive(path, archive_path)
        else:
            raise ValueError(f"Unsupported archive format: {format}")
        
        return archive_path
    
    async def _create_tar_archive(self, source_dir: Path, archive_path: Path):
        """Create a tar.gz archive of a directory."""
        def _tar_creation():
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(source_dir, arcname=source_dir.name)
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _tar_creation)
    
    async def _create_zip_archive(self, source_dir: Path, archive_path: Path):
        """Create a zip archive of a directory."""
        def _zip_creation():
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in source_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(source_dir.parent)
                        zipf.write(file_path, arcname)
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _zip_creation)
    
    async def cleanup_docker_artifacts(self):
        """Clean up any Docker artifacts (containers, volumes, etc.)."""
        try:
            import docker
            client = docker.from_env()
            
            # Clean up stopped containers
            containers = client.containers.list(all=True, filters={'status': 'exited'})
            for container in containers:
                if 'lean' in container.name.lower():
                    logger.info(f"Removing stopped container: {container.name}")
                    container.remove()
            
            # Prune unused volumes
            pruned = client.volumes.prune()
            if pruned['VolumesDeleted']:
                logger.info(f"Pruned {len(pruned['VolumesDeleted'])} unused volumes")
            
        except ImportError:
            logger.warning("Docker SDK not available, skipping Docker cleanup")
        except Exception as e:
            logger.error(f"Docker cleanup failed: {e}")
    
    async def cleanup_old_archives(self, days: int = 30):
        """
        Clean up old archive files.
        
        Args:
            days: Delete archives older than this many days
        """
        if not self.archive_dir.exists():
            return
        
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        deleted_count = 0
        
        for archive_file in self.archive_dir.iterdir():
            if archive_file.is_file() and archive_file.stat().st_mtime < cutoff_time:
                try:
                    archive_file.unlink()
                    logger.info(f"Deleted old archive: {archive_file}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete archive {archive_file}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old archives")
    
    async def get_disk_usage_stats(self) -> dict:
        """Get disk usage statistics for backtest-related directories."""
        stats = {}
        
        # Check LEAN project directory
        lean_dir = Path("/home/ahmed/TheUltimate/backend/lean")
        if lean_dir.exists():
            size = sum(f.stat().st_size for f in lean_dir.rglob('*') if f.is_file())
            stats['lean_directory_mb'] = size / (1024 * 1024)
        
        # Check archive directory
        if self.archive_dir.exists():
            size = sum(f.stat().st_size for f in self.archive_dir.rglob('*') if f.is_file())
            stats['archive_directory_mb'] = size / (1024 * 1024)
        
        # Check screener results directory
        results_dir = Path("/home/ahmed/TheUltimate/backend/screener_results")
        if results_dir.exists():
            size = sum(f.stat().st_size for f in results_dir.rglob('*') if f.is_file())
            stats['screener_results_mb'] = size / (1024 * 1024)
        
        stats['total_mb'] = sum(stats.values())
        
        return stats