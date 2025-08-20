"""
WebSocket handler for bulk backtest progress updates.
"""

import asyncio
import logging
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class BulkBacktestWebSocketManager:
    """Manages WebSocket connections for bulk backtest progress updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}  # bulk_id -> [websockets]
        self.bulk_backtest_info: Dict[str, Dict] = {}  # bulk_id -> info
        self.backtest_to_bulk: Dict[str, str] = {}  # backtest_id -> bulk_id
        
    async def connect(self, bulk_id: str, websocket: WebSocket):
        """Connect a WebSocket for bulk backtest monitoring."""
        await websocket.accept()
        if bulk_id not in self.active_connections:
            self.active_connections[bulk_id] = []
        self.active_connections[bulk_id].append(websocket)
        logger.info(f"WebSocket connected for bulk backtest {bulk_id}")
        
        # Send initial status if available
        if bulk_id in self.bulk_backtest_info:
            await self.send_status_update(bulk_id, websocket)
    
    def disconnect(self, bulk_id: str, websocket: WebSocket):
        """Disconnect a WebSocket."""
        if bulk_id in self.active_connections:
            self.active_connections[bulk_id].remove(websocket)
            if not self.active_connections[bulk_id]:
                del self.active_connections[bulk_id]
        logger.info(f"WebSocket disconnected for bulk backtest {bulk_id}")
    
    def register_bulk_backtest(self, bulk_id: str, total_backtests: int, backtests: List[Dict]):
        """Register a new bulk backtest operation."""
        self.bulk_backtest_info[bulk_id] = {
            "total": total_backtests,
            "completed": 0,
            "failed": 0,
            "running": 0,
            "backtests": backtests,
            "status_by_id": {},
            "start_time": datetime.now()
        }
        
        # Map individual backtest IDs to bulk ID
        for backtest in backtests:
            if backtest.get("backtest_id"):
                self.backtest_to_bulk[backtest["backtest_id"]] = bulk_id
    
    async def update_backtest_status(self, backtest_id: str, status: str, details: Dict = None):
        """Update the status of an individual backtest."""
        if backtest_id not in self.backtest_to_bulk:
            return
            
        bulk_id = self.backtest_to_bulk[backtest_id]
        if bulk_id not in self.bulk_backtest_info:
            return
            
        info = self.bulk_backtest_info[bulk_id]
        
        # Update status
        old_status = info["status_by_id"].get(backtest_id, "pending")
        info["status_by_id"][backtest_id] = status
        
        # Update counters
        if old_status == "running" and status == "completed":
            info["running"] -= 1
            info["completed"] += 1
        elif old_status == "running" and status == "failed":
            info["running"] -= 1
            info["failed"] += 1
        elif old_status == "pending" and status == "running":
            info["running"] += 1
        elif old_status == "pending" and status == "completed":
            info["completed"] += 1
        elif old_status == "pending" and status == "failed":
            info["failed"] += 1
        
        # Find the backtest in the list and update its info
        for backtest in info["backtests"]:
            if backtest.get("backtest_id") == backtest_id:
                backtest["status"] = status
                if details:
                    backtest.update(details)
                break
        
        # Send update to all connected clients
        await self.broadcast_update(bulk_id)
    
    async def broadcast_update(self, bulk_id: str):
        """Broadcast status update to all connected clients."""
        if bulk_id not in self.active_connections:
            return
            
        disconnected = []
        for websocket in self.active_connections[bulk_id]:
            try:
                await self.send_status_update(bulk_id, websocket)
            except Exception as e:
                logger.warning(f"Failed to send update: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for ws in disconnected:
            self.disconnect(bulk_id, ws)
    
    async def send_status_update(self, bulk_id: str, websocket: WebSocket):
        """Send current status to a specific WebSocket."""
        if bulk_id not in self.bulk_backtest_info:
            return
            
        info = self.bulk_backtest_info[bulk_id]
        
        # Calculate overall progress
        progress = 0
        if info["total"] > 0:
            progress = int((info["completed"] + info["failed"]) / info["total"] * 100)
        
        # Find current running backtest
        current_backtest = None
        for backtest in info["backtests"]:
            if info["status_by_id"].get(backtest.get("backtest_id")) == "running":
                current_backtest = backtest
                break
        
        message = {
            "type": "bulk_progress",
            "bulk_id": bulk_id,
            "progress": {
                "total": info["total"],
                "completed": info["completed"],
                "failed": info["failed"],
                "running": info["running"],
                "percentage": progress
            },
            "current": current_backtest,
            "backtests": info["backtests"][:10],  # Send first 10 for UI display
            "is_complete": info["completed"] + info["failed"] == info["total"]
        }
        
        await websocket.send_json(message)
    
    def cleanup_completed(self, bulk_id: str):
        """Clean up completed bulk backtest data."""
        if bulk_id in self.bulk_backtest_info:
            # Remove individual mappings
            for backtest in self.bulk_backtest_info[bulk_id]["backtests"]:
                backtest_id = backtest.get("backtest_id")
                if backtest_id and backtest_id in self.backtest_to_bulk:
                    del self.backtest_to_bulk[backtest_id]
            
            del self.bulk_backtest_info[bulk_id]
        
        if bulk_id in self.active_connections:
            del self.active_connections[bulk_id]


# Global instance
bulk_websocket_manager = BulkBacktestWebSocketManager()