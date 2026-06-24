#session_service.py

"""
Session Service - Manages conversation memory for learning sessions

Handles:
- Saving messages to MongoDB
- Retrieving conversation history
- Managing session state
"""

from backend.db.mongo import sessions_collection
from datetime import datetime


def save_message(session_id: str, role: str, text: str, emotion: str = None) -> bool:
    """
    Save a message to the session conversation history in MongoDB.
    
    Args:
        session_id: Session ID
        role: "student" or "ai"
        text: Message text
        emotion: Detected emotion (for AI messages)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        message_obj = {
            "role": role,
            "text": text,
            "timestamp": datetime.utcnow()
        }
        
        # Add emotion if provided (for AI messages)
        if emotion:
            message_obj["emotion"] = emotion
        
        result = sessions_collection.update_one(
            {"session_id": session_id},
            {"$push": {"messages": message_obj}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"[SESSION_SERVICE] Error saving message: {e}")
        return False


def get_session_history(session_id: str, limit: int = 10) -> list:
    """
    Get conversation history for a session from MongoDB.
    
    Args:
        session_id: Session ID
        limit: Maximum number of recent messages to retrieve
    
    Returns:
        list: List of messages [{role, text, timestamp}, ...]
    """
    try:
        session = sessions_collection.find_one({"session_id": session_id})
        
        if not session:
            print(f"[SESSION_SERVICE] Session not found: {session_id}")
            return []
        
        messages = session.get("messages", [])
        
        # Return last N messages
        return messages[-limit:] if limit else messages
    
    except Exception as e:
        print(f"[SESSION_SERVICE] Error retrieving history: {e}")
        return []


def clear_session_messages(session_id: str) -> bool:
    """
    Clear all messages from a session (for testing or reset).
    
    Args:
        session_id: Session ID
    
    Returns:
        bool: True if successful
    """
    try:
        sessions_collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "messages": []
                }
            }
        )
        return True
    except Exception as e:
        print(f"[SESSION_SERVICE] Error clearing messages: {e}")
        return False


def get_session_summary(session_id: str) -> dict:
    """
    Get session summary including message count and latest emotion/understanding.
    
    Args:
        session_id: Session ID
    
    Returns:
        dict: {message_count, topic, emotion, understanding, status, ...}
    """
    try:
        session = sessions_collection.find_one({"session_id": session_id})
        
        if not session:
            return {"error": "Session not found"}
        
        messages = session.get("messages", [])
        
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "topic": session.get("topic", "unknown"),
            "emotion": session.get("emotion", "neutral"),
            "understanding": session.get("understanding", "medium"),
            "status": session.get("status", "active"),
            "created_at": session.get("start_time", "unknown")
        }
    
    except Exception as e:
        print(f"[SESSION_SERVICE] Error getting summary: {e}")
        return {"error": str(e)}
