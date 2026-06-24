from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FriendRequestStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class FriendRequestCreate(BaseModel):
    receiver_id: str

class FriendRespond(BaseModel):
    request_id: str
    action: str  # "accept" or "reject"

class FriendRequestResponse(BaseModel):
    id: str = Field(alias="_id")
    sender_id: str
    receiver_id: str
    status: FriendRequestStatus
    created_at: datetime
    
    class Config:
        populate_by_name = True

class FriendUserResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None # "pending", "friends", or None

class FriendListResponse(BaseModel):
    user_id: str
    friend_id: str
    became_friends_at: datetime
