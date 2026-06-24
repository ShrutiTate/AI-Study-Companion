"""
Pydantic models for friend chat messages.
Ensures strict isolation from AI tutoring schemas.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class FriendMessageCreate(BaseModel):
    """Schema for creating a new message."""
    receiver_id: str = Field(..., description="ID of the recipient user")
    text: str = Field(..., min_length=1, max_length=2000, description="Message text content")


class FriendMessageResponse(BaseModel):
    """Schema for storing/retrieving messages from DB."""
    sender_id: str
    receiver_id: str
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    timestamp: datetime
    read_status: bool = False

    class Config:
        from_attributes = True


class FriendMessageWS(BaseModel):
    """Schema for WebSocket message payload."""
    type: str = Field("message", description="Event type: 'message', 'typing', 'online', 'offline'")
    sender_id: str
    receiver_id: Optional[str] = None  # For broadcasts, can be null
    text: Optional[str] = None
    original_text: Optional[str] = None
    translated_text: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UserPreferences(BaseModel):
    """User translation preferences."""
    user_id: Optional[str] = None
    preferred_language: str = Field(default="en", description="User's preferred language code")
    auto_translate: bool = Field(default=True, description="Whether to auto-translate incoming messages")
    auto_read_aloud: bool = Field(default=False, description="Whether to auto-read aloud incoming messages")


class ChatHistoryRequest(BaseModel):
    """Schema for querying message history."""
    friend_id: str
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
