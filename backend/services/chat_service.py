"""
Chat service for friend message persistence.
Handles all MongoDB operations for friend messages.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict
from pymongo import DESCENDING
from pymongo.errors import PyMongoError
from backend.db.mongo import db

logger = logging.getLogger(__name__)

FRIEND_MESSAGES_COLLECTION = "friend_messages"
FRIEND_USERS_COLLECTION = "users"


class ChatService:
    """Service for managing friend chat messages in MongoDB."""

    @staticmethod
    def _get_collection():
        """Get the friend_messages collection."""
        if db is None:
            raise RuntimeError("MongoDB not connected")
        return db[FRIEND_MESSAGES_COLLECTION]

    @staticmethod
    def _get_users_collection():
        """Get the users collection."""
        if db is None:
            raise RuntimeError("MongoDB not connected")
        return db[FRIEND_USERS_COLLECTION]

    @staticmethod
    async def save_message(
        sender_id: str,
        receiver_id: str,
        original_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
    ) -> str:
        """
        Save a friend message to database.
        Returns the inserted message ID.
        """
        try:
            collection = ChatService._get_collection()
            message_doc = {
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "original_text": original_text,
                "translated_text": translated_text,
                "source_language": source_language,
                "target_language": target_language,
                "timestamp": datetime.utcnow(),
                "read_status": False,
            }
            result = collection.insert_one(message_doc)
            logger.info(f"Message saved: {result.inserted_id}")
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to save message: {e}")
            raise

    @staticmethod
    async def get_message_history(
        user_id: str,
        friend_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict:
        """
        Fetch paginated message history between two users.
        User can only access chats they participate in.
        """
        try:
            collection = ChatService._get_collection()
            skip = (page - 1) * page_size

            # Query: messages where user is either sender or receiver
            query = {
                "$or": [
                    {"sender_id": user_id, "receiver_id": friend_id},
                    {"sender_id": friend_id, "receiver_id": user_id},
                ]
            }

            # Count total messages
            total = collection.count_documents(query)

            # Fetch paginated results (newest first)
            messages = list(
                collection.find(query)
                .sort("timestamp", DESCENDING)
                .skip(skip)
                .limit(page_size)
            )

            # Convert ObjectId to string and datetime to ISO format
            for msg in messages:
                msg["_id"] = str(msg["_id"])
                if "timestamp" in msg and msg["timestamp"]:
                    msg["timestamp"] = msg["timestamp"].isoformat()

            return {
                "messages": messages,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            }
        except PyMongoError as e:
            logger.error(f"Failed to fetch message history: {e}")
            raise

    @staticmethod
    async def mark_as_read(message_id: str) -> bool:
        """Mark a message as read."""
        try:
            from bson.objectid import ObjectId

            collection = ChatService._get_collection()
            result = collection.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": {"read_status": True}},
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to mark message as read: {e}")
            return False

    @staticmethod
    async def get_user_preferences(user_id: str) -> Dict:
        """
        Fetch user's translation preferences.
        Returns default preferences if user doc doesn't exist.
        """
        try:
            users_collection = ChatService._get_users_collection()
            user_doc = users_collection.find_one({"user_id": user_id})

            prefs = {
                "preferred_language": user_doc.get("preferred_language", "en")
                if user_doc is not None
                else "en",
                "auto_translate": user_doc.get("auto_translate", True) if user_doc is not None else True,
                "auto_read_aloud": user_doc.get("auto_read_aloud", True) if user_doc is not None else True,
            }
            
            logger.info(f"[PREFS] User {user_id}: {prefs}")
            return prefs
            
        except PyMongoError as e:
            logger.error(f"Failed to fetch user preferences: {e}")
            return {"preferred_language": "en", "auto_translate": True, "auto_read_aloud": True}

    @staticmethod
    async def update_user_preferences(user_id: str, preferences: Dict) -> bool:
        """Update user's translation preferences."""
        try:
            users_collection = ChatService._get_users_collection()
            result = users_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "preferred_language": preferences.get("preferred_language", "en"),
                        "auto_translate": preferences.get("auto_translate", True),
                        "auto_read_aloud": preferences.get("auto_read_aloud", False),
                    }
                },
                upsert=True,
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except PyMongoError as e:
            logger.error(f"Failed to update user preferences: {e}")
            return False

    @staticmethod
    async def delete_message(message_id: str, user_id: str) -> bool:
        """
        Delete a message (only sender can delete).
        """
        try:
            from bson.objectid import ObjectId

            collection = ChatService._get_collection()
            result = collection.delete_one(
                {"_id": ObjectId(message_id), "sender_id": user_id}
            )
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to delete message: {e}")
            return False
