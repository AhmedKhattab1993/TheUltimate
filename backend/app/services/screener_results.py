"""
Service for managing screener results that can be accessed by backtests.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ScreenerResultsManager:
    """Manages saving and loading screener results for backtests."""
    
    def __init__(self, results_dir: str = "/home/ahmed/TheUltimate/backend/screener_results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    def save_results(self, symbols: List[str], filters: Dict[str, Any], 
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save screener results to a file.
        
        Args:
            symbols: List of stock symbols from the screener
            filters: The filters used in the screener
            metadata: Additional metadata about the screening
            
        Returns:
            Path to the saved results file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_id = f"screener_results_{timestamp}"
            filename = f"{result_id}.json"
            filepath = self.results_dir / filename
            
            results = {
                "timestamp": datetime.now().isoformat(),
                "symbols": symbols,
                "filters": filters,
                "metadata": metadata or {},
                "count": len(symbols)
            }
            
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"Saved screener results to {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save screener results: {e}")
            raise
    
    def load_results(self, filepath: str) -> Dict[str, Any]:
        """
        Load screener results from a file.
        
        Args:
            filepath: Path to the results file
            
        Returns:
            Dict containing the screener results
        """
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load screener results from {filepath}: {e}")
            raise
    
    def get_latest_results(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent screener results.
        
        Returns:
            Dict containing the latest results or None if no results exist
        """
        try:
            # Find all result files
            result_files = list(self.results_dir.glob("screener_results_*.json"))
            
            if not result_files:
                return None
            
            # Sort by modification time and get the latest
            latest_file = max(result_files, key=lambda f: f.stat().st_mtime)
            
            return self.load_results(str(latest_file))
            
        except Exception as e:
            logger.error(f"Failed to get latest screener results: {e}")
            return None
    
    def list_results(self) -> List[Dict[str, Any]]:
        """
        List all available screener results.
        
        Returns:
            List of result summaries
        """
        try:
            result_files = sorted(
                self.results_dir.glob("screener_results_*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            results = []
            for file in result_files:
                try:
                    data = self.load_results(str(file))
                    results.append({
                        "filepath": str(file),
                        "filename": file.name,
                        "timestamp": data.get("timestamp"),
                        "symbol_count": data.get("count", 0),
                        "filters": data.get("filters", {}),
                        "metadata": data.get("metadata", {})
                    })
                except Exception as e:
                    logger.warning(f"Failed to load {file}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to list screener results: {e}")
            return []


# Global instance
screener_results_manager = ScreenerResultsManager()