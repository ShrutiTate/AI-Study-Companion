"""
WebSocket connection manager for real-time friend chat.
Handles connection routing, presence, typing indicators, and message delivery.
"""

import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections per user.
    Handles:
    - Connection/disconnection events
    - Message routing to specific users
    - Presence broadcasting
    - Typing indicators
    """

    def __init__(self):
        # Map of user_id -> WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}
        # Lock for thread-safe dict operations
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, user_id: str) -> None:
        """Unregister a WebSocket connection."""
        async with self._lock:
            if user_id in self.active_connections:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected. Total connections: {len(self.active_connections)}")

    async def is_online(self, user_id: str) -> bool:
        """Check if user is currently online."""
        async with self._lock:
            return user_id in self.active_connections

    async def get_online_users(self) -> Set[str]:
        """Get set of all online user IDs."""
        async with self._lock:
            return set(self.active_connections.keys())

    async def send_personal_message(self, user_id: str, message: dict) -> bool:
        """
        Send a message to a specific user if they're online.
        Returns True if delivered, False if user offline.
        """
        async with self._lock:
            websocket = self.active_connections.get(user_id)

        if not websocket:
            logger.debug(f"User {user_id} offline - message queued for later delivery")
            return False

        try:
            await websocket.send_json(message)
            logger.debug(f"Message sent to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
            await self.disconnect(user_id)
            return False

    async def broadcast_to_user_group(self, user_ids: list, message: dict) -> Dict[str, bool]:
        """
        Broadcast message to multiple users.
        Returns dict mapping user_id -> delivery_status.
        """
        results = {}
        for user_id in user_ids:
            results[user_id] = await self.send_personal_message(user_id, message)
        return results

    async def send_typing_indicator(self, from_user: str, to_user: str, is_typing: bool = True) -> bool:
        """Send typing indicator from one user to another."""
        message = {
            "type": "typing",
            "sender_id": from_user,
            "is_typing": is_typing,
        }
        return await self.send_personal_message(to_user, message)

    async def broadcast_presence(self, user_id: str, status: str) -> None:
        """
        Broadcast online/offline status to all connected users.
        status: 'online' or 'offline'
        """
        message = {
            "type": "presence",
            "user_id": user_id,
            "status": status,
        }
        online_users = await self.get_online_users()
        for other_user in online_users:
            if other_user != user_id:
                await self.send_personal_message(other_user, message)

    async def broadcast_friend_request(self, receiver_id: str, sender_id: str, sender_name: str) -> bool:
        """Broadcast a friend request notification to the receiver."""
        message = {
            "type": "friend_request",
            "sender_id": sender_id,
            "from": sender_name
        }
        return await self.send_personal_message(receiver_id, message)

    async def broadcast_friend_accepted(self, sender_id: str, friend_id: str, friend_name: str) -> bool:
        """Broadcast a friend request acceptance notification."""
        message = {
            "type": "friend_accepted",
            "friend_id": friend_id,
            "from": friend_name
        }
        return await self.send_personal_message(sender_id, message)

    async def broadcast_friend_request_cancelled(self, receiver_id: str, sender_id: str) -> bool:
        """Broadcast a friend request cancellation notification."""
        message = {
            "type": "friend_request_cancelled",
            "sender_id": sender_id
        }
        return await self.send_personal_message(receiver_id, message)


# Global instance
connection_manager = ConnectionManager()
