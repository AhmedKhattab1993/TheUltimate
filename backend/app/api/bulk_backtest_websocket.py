"""
Simplified WebSocket handler for bulk backtest completion notifications.
"""

import asyncio
import logging
from typing import Dict, List
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class BulkBacktestWebSocketManager:
    """Manages WebSocket connections for bulk backtest completion notifications."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}  # bulk_id -> [websockets]
        self.bulk_status: Dict[str, bool] = {}  # bulk_id -> is_complete
        
    async def connect(self, bulk_id: str, websocket: WebSocket):
        """Connect a WebSocket for bulk backtest monitoring."""
        logger.info(f"[BulkWebSocket] CONNECT START - bulk_id: {bulk_id}")
        logger.info(f"[BulkWebSocket] Current bulk_status: {self.bulk_status}")
        logger.info(f"[BulkWebSocket] Current active_connections: {list(self.active_connections.keys())}")
        
        await websocket.accept()
        if bulk_id not in self.active_connections:
            self.active_connections[bulk_id] = []
        self.active_connections[bulk_id].append(websocket)
        logger.info(f"[BulkWebSocket] WebSocket connected for bulk backtest {bulk_id} - total connections: {len(self.active_connections[bulk_id])}")
        
        # Check if this bulk backtest is already completed (race condition fix)
        bulk_completed = bulk_id in self.bulk_status and self.bulk_status[bulk_id]
        logger.info(f"[BulkWebSocket] Checking completion status for {bulk_id}: {bulk_completed}")
        
        if bulk_completed:
            logger.info(f"[BulkWebSocket] Bulk backtest {bulk_id} already completed, sending immediate completion message")
            message = {
                "type": "all_complete",
                "bulk_id": bulk_id
            }
            try:
                await websocket.send_json(message)
                logger.info(f"[BulkWebSocket] Successfully sent immediate completion notification to {bulk_id}")
            except Exception as e:
                logger.warning(f"[BulkWebSocket] Failed to send immediate completion notification to {bulk_id}: {e}")
        else:
            logger.info(f"[BulkWebSocket] Bulk backtest {bulk_id} not yet completed, waiting for completion notification")
    
    def disconnect(self, bulk_id: str, websocket: WebSocket):
        """Disconnect a WebSocket."""
        logger.info(f"[BulkWebSocket] DISCONNECT START - bulk_id: {bulk_id}")
        if bulk_id in self.active_connections:
            self.active_connections[bulk_id].remove(websocket)
            remaining = len(self.active_connections[bulk_id])
            logger.info(f"[BulkWebSocket] Removed WebSocket, remaining connections for {bulk_id}: {remaining}")
            if not self.active_connections[bulk_id]:
                del self.active_connections[bulk_id]
                logger.info(f"[BulkWebSocket] No more connections for {bulk_id}, removed from active_connections")
        else:
            logger.warning(f"[BulkWebSocket] Tried to disconnect {bulk_id} but not in active_connections")
        logger.info(f"[BulkWebSocket] WebSocket disconnected for bulk backtest {bulk_id}")
    
    def register_bulk_backtest(self, bulk_id: str):
        """Register a new bulk backtest operation."""
        logger.info(f"[BulkWebSocket] REGISTER START - bulk_id: {bulk_id}")
        logger.info(f"[BulkWebSocket] Previous bulk_status: {self.bulk_status}")
        self.bulk_status[bulk_id] = False
        logger.info(f"[BulkWebSocket] Registered bulk backtest {bulk_id} - status set to False")
        logger.info(f"[BulkWebSocket] Updated bulk_status: {self.bulk_status}")
    
    async def notify_completion(self, bulk_id: str):
        """Notify all clients that bulk backtest is complete."""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        logger.info(f"[BulkWebSocket] NOTIFY_COMPLETION START at {timestamp} - bulk_id: {bulk_id}")
        logger.info(f"[BulkWebSocket] Previous bulk_status: {self.bulk_status}")
        logger.info(f"[BulkWebSocket] Current active_connections: {list(self.active_connections.keys())}")
        
        # Always mark as completed - this is critical for race condition handling
        self.bulk_status[bulk_id] = True
        logger.info(f"[BulkWebSocket] Marked {bulk_id} as completed - bulk_status: {self.bulk_status}")
        
        if bulk_id not in self.active_connections:
            logger.warning(f"[BulkWebSocket] No active connections for bulk_id: {bulk_id} - completion notification stored for race condition fix")
            return
        
        connection_count = len(self.active_connections[bulk_id])
        logger.info(f"[BulkWebSocket] Found {connection_count} active connections for {bulk_id}")
        
        message = {
            "type": "all_complete",
            "bulk_id": bulk_id
        }
        
        disconnected = []
        for i, websocket in enumerate(self.active_connections[bulk_id]):
            try:
                await websocket.send_json(message)
                logger.info(f"[BulkWebSocket] Successfully sent completion notification to connection {i+1}/{connection_count} for {bulk_id}")
            except Exception as e:
                logger.warning(f"[BulkWebSocket] Failed to send completion notification to connection {i+1}: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        logger.info(f"[BulkWebSocket] Removing {len(disconnected)} disconnected clients")
        for ws in disconnected:
            self.disconnect(bulk_id, ws)
        
        logger.info(f"[BulkWebSocket] NOTIFY_COMPLETION COMPLETE for {bulk_id}")
    
    def cleanup_completed(self, bulk_id: str):
        """Clean up completed bulk backtest data."""
        if bulk_id in self.bulk_status:
            del self.bulk_status[bulk_id]
        
        if bulk_id in self.active_connections:
            del self.active_connections[bulk_id]


# Global instance
bulk_websocket_manager = BulkBacktestWebSocketManager()