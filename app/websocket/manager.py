"""
WebSocket Connection Manager
Real-time status updates for meeting processing.
"""

from typing import Dict, List, Optional
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

from app.core.logging import get_logger
from app.core.security import verify_access_token
from app.core.exceptions import AuthenticationError

logger = get_logger(__name__)

websocket_router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    Supports broadcasting to specific meetings or users.
    """
    
    def __init__(self):
        # Map of meeting_id -> list of connected websockets
        self.meeting_connections: Dict[str, List[WebSocket]] = {}
        # Map of user_id -> list of connected websockets
        self.user_connections: Dict[str, List[WebSocket]] = {}
        # Map of websocket -> (user_id, meeting_ids)
        self.connection_info: Dict[WebSocket, tuple] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        meeting_id: Optional[str] = None,
    ) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        # Track user connection
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)
        
        # Track meeting connection if specified
        if meeting_id:
            if meeting_id not in self.meeting_connections:
                self.meeting_connections[meeting_id] = []
            self.meeting_connections[meeting_id].append(websocket)
        
        # Store connection info
        self.connection_info[websocket] = (user_id, meeting_id)
        
        logger.info(
            "WebSocket connected",
            user_id=user_id,
            meeting_id=meeting_id,
        )
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket not in self.connection_info:
            return
        
        user_id, meeting_id = self.connection_info[websocket]
        
        # Remove from user connections
        if user_id in self.user_connections:
            self.user_connections[user_id] = [
                ws for ws in self.user_connections[user_id]
                if ws != websocket
            ]
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove from meeting connections
        if meeting_id and meeting_id in self.meeting_connections:
            self.meeting_connections[meeting_id] = [
                ws for ws in self.meeting_connections[meeting_id]
                if ws != websocket
            ]
            if not self.meeting_connections[meeting_id]:
                del self.meeting_connections[meeting_id]
        
        # Remove connection info
        del self.connection_info[websocket]
        
        logger.info(
            "WebSocket disconnected",
            user_id=user_id,
            meeting_id=meeting_id,
        )
    
    async def send_personal(
        self,
        websocket: WebSocket,
        message: dict,
    ) -> None:
        """Send message to a specific connection."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
        except Exception as e:
            logger.warning("Failed to send WebSocket message", error=str(e))
    
    async def broadcast_to_meeting(
        self,
        meeting_id: str,
        message: dict,
    ) -> None:
        """Broadcast message to all connections watching a meeting."""
        connections = self.meeting_connections.get(meeting_id, [])
        
        for websocket in connections:
            await self.send_personal(websocket, message)
    
    async def broadcast_to_user(
        self,
        user_id: str,
        message: dict,
    ) -> None:
        """Broadcast message to all connections of a user."""
        connections = self.user_connections.get(user_id, [])
        
        for websocket in connections:
            await self.send_personal(websocket, message)
    
    async def send_status_update(
        self,
        meeting_id: str,
        status: str,
        message: str,
        progress: int = 0,
    ) -> None:
        """Send a status update for meeting processing."""
        await self.broadcast_to_meeting(
            meeting_id,
            {
                "event": "status_update",
                "data": {
                    "meeting_id": meeting_id,
                    "status": status,
                    "message": message,
                    "progress": progress,
                },
            },
        )


# Global connection manager instance
manager = ConnectionManager()


@websocket_router.websocket("/meetings/{meeting_id}")
async def meeting_websocket(
    websocket: WebSocket,
    meeting_id: str,
    token: str = Query(...),
) -> None:
    """
    WebSocket endpoint for real-time meeting status updates.
    
    Connect with: ws://host/ws/meetings/{meeting_id}?token=<jwt_token>
    """
    # Authenticate user
    try:
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except AuthenticationError:
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    # Connect
    await manager.connect(websocket, user_id, meeting_id)
    
    try:
        # Send initial connection confirmation
        await manager.send_personal(
            websocket,
            {
                "event": "connected",
                "data": {"meeting_id": meeting_id},
            },
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            
            # Handle ping/pong for keep-alive
            if data == "ping":
                await websocket.send_text("pong")
            else:
                # Handle other messages if needed
                try:
                    message = json.loads(data)
                    # Process message...
                except json.JSONDecodeError:
                    pass
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@websocket_router.websocket("/user")
async def user_websocket(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    """
    WebSocket endpoint for user-level notifications.
    Receives updates for all user's meetings.
    
    Connect with: ws://host/ws/user?token=<jwt_token>
    """
    # Authenticate user
    try:
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except AuthenticationError:
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    # Connect
    await manager.connect(websocket, user_id)
    
    try:
        await manager.send_personal(
            websocket,
            {"event": "connected", "data": {"user_id": user_id}},
        )
        
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Export manager for use in other modules
def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return manager
