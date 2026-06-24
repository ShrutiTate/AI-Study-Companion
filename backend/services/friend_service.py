import logging
from datetime import datetime
from bson import ObjectId
from backend.services.websocket_manager import connection_manager

from backend.db.mongo import users_collection, friend_requests_collection, friends_list_collection
from backend.models.friend_model import FriendRequestStatus

logger = logging.getLogger(__name__)

class FriendService:
    @staticmethod
    async def search_users(query: str, current_user_id: str):
        """Search for users by name or email, excluding the current user."""
        try:
            # Basic regex search for name or email
            search_regex = {"$regex": query, "$options": "i"}
            
            # Find users matching the query, excluding the current user
            users = list(users_collection.find(
                {
                    "$and": [
                        {"user_id": {"$ne": current_user_id}},
                        {"$or": [{"name": search_regex}, {"email": search_regex}, {"user_id": search_regex}]}
                    ]
                },
                {"_id": 0, "user_id": 1, "name": 1, "email": 1}
            ).limit(20))
            
            # For each user, determine the friendship status with the current user
            result = []
            for user in users:
                target_id = user["user_id"]
                
                # Check if they are already friends
                is_friend = friends_list_collection.find_one({
                    "user_id": current_user_id,
                    "friend_id": target_id
                })
                
                if is_friend:
                    user["status"] = "friends"
                else:
                    # Check if there's a pending request in either direction
                    pending_request = friend_requests_collection.find_one({
                        "$or": [
                            {"sender_id": current_user_id, "receiver_id": target_id, "status": FriendRequestStatus.PENDING.value},
                            {"sender_id": target_id, "receiver_id": current_user_id, "status": FriendRequestStatus.PENDING.value}
                        ]
                    })
                    
                    if pending_request:
                        user["status"] = "pending"
                    else:
                        user["status"] = None
                
                result.append(user)
                
            return result
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []

    @staticmethod
    async def send_friend_request(sender_id: str, receiver_id: str):
        """Send a friend request from sender to receiver."""
        try:
            if sender_id == receiver_id:
                return {"success": False, "message": "Cannot send a friend request to yourself"}

            # Check if target user exists
            target_user = users_collection.find_one({"user_id": receiver_id})
            if not target_user:
                return {"success": False, "message": "User not found"}

            # Check if they are already friends
            is_friend = friends_list_collection.find_one({
                "user_id": sender_id,
                "friend_id": receiver_id
            })
            if is_friend:
                return {"success": False, "message": "You are already friends"}

            # Check for existing pending request (in either direction)
            existing_request = friend_requests_collection.find_one({
                "$or": [
                    {"sender_id": sender_id, "receiver_id": receiver_id, "status": FriendRequestStatus.PENDING.value},
                    {"sender_id": receiver_id, "receiver_id": sender_id, "status": FriendRequestStatus.PENDING.value}
                ]
            })
            
            if existing_request:
                return {"success": False, "message": "A friend request is already pending"}

            # Create new request
            new_request = {
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "status": FriendRequestStatus.PENDING.value,
                "created_at": datetime.utcnow()
            }
            
            result = friend_requests_collection.insert_one(new_request)
            
            # Fetch sender name for notification
            sender_user = users_collection.find_one({"user_id": sender_id})
            sender_name = sender_user.get("name", sender_id) if sender_user else sender_id

            # Broadcast friend request notification via WebSocket
            await connection_manager.broadcast_friend_request(receiver_id, sender_id, sender_name)
            
            return {
                "success": True, 
                "request_id": str(result.inserted_id),
                "sender_name": sender_name
            }
        except Exception as e:
            logger.error(f"Error sending friend request: {e}")
            return {"success": False, "message": "Failed to send request"}

    @staticmethod
    async def respond_to_request(request_id: str, action: str):
        """Accept or reject a friend request."""
        try:
            request = friend_requests_collection.find_one({"_id": ObjectId(request_id)})
            
            if not request:
                return {"success": False, "message": "Friend request not found"}
                
            if request["status"] != FriendRequestStatus.PENDING.value:
                return {"success": False, "message": f"Request is already {request['status']}"}

            sender_id = request["sender_id"]
            receiver_id = request["receiver_id"]

            if action == "accept":
                # Update request status
                friend_requests_collection.update_one(
                    {"_id": ObjectId(request_id)},
                    {"$set": {"status": FriendRequestStatus.ACCEPTED.value}}
                )
                
                # Insert mutual friendship (two documents)
                now = datetime.utcnow()
                friends_list_collection.insert_many([
                    {
                        "user_id": sender_id,
                        "friend_id": receiver_id,
                        "became_friends_at": now
                    },
                    {
                        "user_id": receiver_id,
                        "friend_id": sender_id,
                        "became_friends_at": now
                    }
                ])
                
                # Fetch receiver name for notification to sender
                receiver_user = users_collection.find_one({"user_id": receiver_id})
                receiver_name = receiver_user.get("name", receiver_id) if receiver_user else receiver_id

                # Broadcast acceptance notification via WebSocket
                await connection_manager.broadcast_friend_accepted(sender_id, receiver_id, receiver_name)
                
                return {
                    "success": True, 
                    "status": "accepted", 
                    "sender_id": sender_id, 
                    "receiver_id": receiver_id,
                    "receiver_name": receiver_name
                }
                
            elif action == "reject":
                # Update request status
                friend_requests_collection.update_one(
                    {"_id": ObjectId(request_id)},
                    {"$set": {"status": FriendRequestStatus.REJECTED.value}}
                )
                return {
                    "success": True, 
                    "status": "rejected"
                }
            else:
                return {"success": False, "message": "Invalid action"}
                
        except Exception as e:
            logger.error(f"Error responding to friend request: {e}")
            return {"success": False, "message": "Failed to respond to request"}

    @staticmethod
    async def get_friends_list(user_id: str):
        """Get the list of accepted friends for a user."""
        try:
            friends = list(friends_list_collection.find({"user_id": user_id}))
            
            friend_details = []
            for friend in friends:
                friend_id = friend["friend_id"]
                user = users_collection.find_one({"user_id": friend_id}, {"_id": 0, "user_id": 1, "name": 1, "email": 1})
                if user:
                    user["became_friends_at"] = friend["became_friends_at"]
                    friend_details.append(user)
                    
            return friend_details
        except Exception as e:
            logger.error(f"Error fetching friends list: {e}")
            return []

    @staticmethod
    async def get_pending_requests(user_id: str):
        """Get incoming pending friend requests for a user."""
        try:
            requests = list(friend_requests_collection.find({
                "receiver_id": user_id,
                "status": FriendRequestStatus.PENDING.value
            }))
            
            # Enrich with sender details
            for req in requests:
                req["_id"] = str(req["_id"])
                sender = users_collection.find_one({"user_id": req["sender_id"]}, {"_id": 0, "name": 1, "email": 1})
                if sender:
                    req["sender_name"] = sender.get("name")
                    req["sender_email"] = sender.get("email")
                else:
                    req["sender_name"] = req["sender_id"]
                    
            return requests
        except Exception as e:
            logger.error(f"Error fetching pending requests: {e}")
            return []

    @staticmethod
    async def remove_friend(user_id: str, friend_id: str):
        """Remove a friend (mutual deletion)."""
        try:
            # Delete mutual friendship documents
            result1 = friends_list_collection.delete_one({
                "user_id": user_id,
                "friend_id": friend_id
            })
            result2 = friends_list_collection.delete_one({
                "user_id": friend_id,
                "friend_id": user_id
            })
            
            # Optionally, you could also delete/update the original accepted request, 
            # but usually it's left as a historical record or removed. We'll leave it.
            
            return (result1.deleted_count > 0 or result2.deleted_count > 0)
        except Exception as e:
            logger.error(f"Error removing friend: {e}")
            return False

    @staticmethod
    async def are_friends(user_id: str, friend_id: str) -> bool:
        """Check if two users are friends (useful for chat message validation)."""
        try:
            # Also allow demo friends
            if friend_id in ["maria_spanish", "yuki_japanese", "jean_french", "amit_hindi"]:
                return True
                
            is_friend = friends_list_collection.find_one({
                "user_id": user_id,
                "friend_id": friend_id
            })
            return bool(is_friend)
        except Exception as e:
            logger.error(f"Error checking friendship status: {e}")
            return False

    @staticmethod
    async def cancel_friend_request(sender_id: str, receiver_id: str):
        """Cancel a pending friend request (only the sender can cancel)."""
        try:
            result = friend_requests_collection.delete_one({
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "status": FriendRequestStatus.PENDING.value
            })
            
            if result.deleted_count > 0:
                # Notify the receiver so their UI updates
                await connection_manager.broadcast_friend_request_cancelled(receiver_id, sender_id)
                return {"success": True, "message": "Friend request cancelled"}
            else:
                return {"success": False, "message": "No pending request found to cancel"}
        except Exception as e:
            logger.error(f"Error cancelling friend request: {e}")
            return {"success": False, "message": "Failed to cancel request"}

    @staticmethod
    async def get_sent_pending_requests(user_id: str):
        """Get outgoing pending friend requests sent by the user."""
        try:
            requests = list(friend_requests_collection.find({
                "sender_id": user_id,
                "status": FriendRequestStatus.PENDING.value
            }))
            
            for req in requests:
                req["_id"] = str(req["_id"])
                receiver = users_collection.find_one({"user_id": req["receiver_id"]}, {"_id": 0, "name": 1, "email": 1})
                if receiver:
                    req["receiver_name"] = receiver.get("name")
                    req["receiver_email"] = receiver.get("email")
                else:
                    req["receiver_name"] = req["receiver_id"]
                    
            return requests
        except Exception as e:
            logger.error(f"Error fetching sent pending requests: {e}")
            return []
