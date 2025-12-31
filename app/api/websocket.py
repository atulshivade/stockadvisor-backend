# websocket.py
# StockAdvisor Backend - WebSocket API for Real-time Updates
# Created by Digital COE Gen AI Team

import json
import asyncio
from typing import Dict, Set, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger

from app.config import settings

router = APIRouter()


class WebSocketManager:
    """Manager for WebSocket connections and price broadcasting."""
    
    _connections: Dict[str, Set[WebSocket]] = {}  # symbol -> set of connections
    _user_connections: Dict[str, WebSocket] = {}  # user_id -> connection
    _heartbeat_interval = settings.WS_HEARTBEAT_INTERVAL
    
    @classmethod
    async def connect(cls, websocket: WebSocket, user_id: str = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        if user_id:
            cls._user_connections[user_id] = websocket
            
        logger.info(f"WebSocket connected: {user_id or 'anonymous'}")
    
    @classmethod
    async def disconnect(cls, websocket: WebSocket, user_id: str = None):
        """Handle WebSocket disconnection."""
        # Remove from symbol subscriptions
        for symbol in list(cls._connections.keys()):
            cls._connections[symbol].discard(websocket)
            if not cls._connections[symbol]:
                del cls._connections[symbol]
        
        # Remove user connection
        if user_id and user_id in cls._user_connections:
            del cls._user_connections[user_id]
            
        logger.info(f"WebSocket disconnected: {user_id or 'anonymous'}")
    
    @classmethod
    async def subscribe(cls, websocket: WebSocket, symbols: List[str]):
        """Subscribe connection to price updates for symbols."""
        for symbol in symbols:
            if symbol not in cls._connections:
                cls._connections[symbol] = set()
            cls._connections[symbol].add(websocket)
            
        logger.debug(f"Subscribed to: {symbols}")
    
    @classmethod
    async def unsubscribe(cls, websocket: WebSocket, symbols: List[str]):
        """Unsubscribe connection from price updates for symbols."""
        for symbol in symbols:
            if symbol in cls._connections:
                cls._connections[symbol].discard(websocket)
                if not cls._connections[symbol]:
                    del cls._connections[symbol]
    
    @classmethod
    async def broadcast_price_update(cls, update: dict):
        """Broadcast price update to all subscribed connections."""
        symbol = update.get("symbol")
        if not symbol or symbol not in cls._connections:
            return
            
        message = json.dumps({
            "type": "price_update",
            "data": update
        })
        
        dead_connections = set()
        
        for websocket in cls._connections[symbol]:
            try:
                await websocket.send_text(message)
            except Exception:
                dead_connections.add(websocket)
        
        # Remove dead connections
        for ws in dead_connections:
            cls._connections[symbol].discard(ws)
    
    @classmethod
    async def send_to_user(cls, user_id: str, message: dict):
        """Send message to specific user."""
        if user_id in cls._user_connections:
            try:
                await cls._user_connections[user_id].send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send to user {user_id}: {e}")
    
    @classmethod
    async def broadcast_all(cls, message: dict):
        """Broadcast message to all connected users."""
        message_text = json.dumps(message)
        
        for websocket in cls._user_connections.values():
            try:
                await websocket.send_text(message_text)
            except Exception:
                pass
    
    @classmethod
    async def heartbeat(cls, websocket: WebSocket):
        """Send periodic heartbeat to keep connection alive."""
        while True:
            try:
                await asyncio.sleep(cls._heartbeat_interval)
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
            except Exception:
                break


@router.websocket("/prices")
async def websocket_prices(
    websocket: WebSocket,
    token: str = Query(default=None)
):
    """
    WebSocket endpoint for real-time price updates.
    
    Connect to this endpoint and send subscription messages:
    
    ```json
    {
        "action": "subscribe",
        "symbols": ["AAPL", "MSFT", "GOOGL"]
    }
    ```
    
    Receive price updates:
    
    ```json
    {
        "type": "price_update",
        "data": {
            "symbol": "AAPL",
            "price": 185.50,
            "change": 2.30,
            "change_percent": 1.25,
            "volume": 52345678,
            "timestamp": "2024-01-15T14:30:00Z"
        }
    }
    ```
    """
    user_id = None
    
    # Validate token if provided
    if token:
        try:
            from jose import jwt
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("sub")
        except Exception:
            pass
    
    await WebSocketManager.connect(websocket, user_id)
    
    # Start heartbeat task
    heartbeat_task = asyncio.create_task(WebSocketManager.heartbeat(websocket))
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                action = message.get("action")
                
                if action == "subscribe":
                    symbols = message.get("symbols", [])
                    await WebSocketManager.subscribe(websocket, symbols)
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "symbols": symbols
                    }))
                    
                elif action == "unsubscribe":
                    symbols = message.get("symbols", [])
                    await WebSocketManager.unsubscribe(websocket, symbols)
                    await websocket.send_text(json.dumps({
                        "type": "unsubscribed",
                        "symbols": symbols
                    }))
                    
                elif action == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        heartbeat_task.cancel()
        await WebSocketManager.disconnect(websocket, user_id)


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket endpoint for user notifications.
    
    Requires authentication token.
    
    Receive notifications:
    
    ```json
    {
        "type": "notification",
        "data": {
            "id": "notif_123",
            "title": "Price Alert",
            "message": "AAPL reached your target price of $190",
            "category": "alert",
            "timestamp": "2024-01-15T14:30:00Z"
        }
    }
    ```
    """
    # Validate token
    try:
        from jose import jwt
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
            
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    await WebSocketManager.connect(websocket, user_id)
    
    try:
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "Connected to notifications"
        }))
        
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("action") == "ack":
                    # Acknowledge notification received
                    notification_id = message.get("notification_id")
                    logger.debug(f"Notification {notification_id} acknowledged by {user_id}")
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Notification WebSocket error: {e}")
    finally:
        await WebSocketManager.disconnect(websocket, user_id)

