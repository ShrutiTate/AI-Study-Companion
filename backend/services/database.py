#database.py


from datetime import datetime
from backend.db.mongo import sessions_collection, chat_collection
from typing import Dict, Optional
import uuid

def save_learning_session(user_id: str, text: str, emotion: str, response: str, session_id: Optional[str] = None, topic: Optional[str] = None) -> Dict:
    """
    Save a learning session to the database.
    """
    try:
        session = {
            "session_id": session_id or str(uuid.uuid4()),
            "user_id": user_id,
            "input_text": text,
            "emotion": emotion,
            "response": response,
            "topic": topic,
            "timestamp": datetime.utcnow(),
            "type": "learning"
        }
        result = sessions_collection.insert_one(session)
        return {
            "success": True,
            "session_id": session["session_id"],
            "inserted_id": str(result.inserted_id)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def save_chat_message(user_id: str, original_text: str, translated_text: str, source_lang: str, target_lang: str) -> Dict:
    """
    Save a chat message (translation) to the database.
    """
    try:
        message = {
            "message_id": str(uuid.uuid4()),
            "user_id": user_id,
            "original_text": original_text,
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "timestamp": datetime.utcnow(),
            "type": "chat"
        }
        result = chat_collection.insert_one(message)
        return {
            "success": True,
            "message_id": message["message_id"],
            "inserted_id": str(result.inserted_id)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_user_sessions(user_id: str, limit: int = 10) -> list:
    """
    Get learning sessions for a user.
    """
    try:
        sessions = list(
            sessions_collection.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        # Convert ObjectId to string
        for session in sessions:
            session["_id"] = str(session["_id"])
            session["timestamp"] = session["timestamp"].isoformat()
        return sessions
    except Exception as e:
        return []

def get_user_chats(user_id: str, limit: int = 10) -> list:
    """
    Get chat messages for a user.
    """
    try:
        messages = list(
            chat_collection.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        # Convert ObjectId to string
        for msg in messages:
            msg["_id"] = str(msg["_id"])
            msg["timestamp"] = msg["timestamp"].isoformat()
        return messages
    except Exception as e:
        return []
