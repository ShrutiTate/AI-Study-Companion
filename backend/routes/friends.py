import logging
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from backend.models.friend_model import FriendRequestCreate, FriendRespond
from backend.services.friend_service import FriendService
from backend.services.websocket_manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["friends"])

@router.get("/users/search")
async def search_users(
    query: str = Query(..., min_length=1),
    user_id: str = Query(...)
):
    """Search for users by name or email."""
    try:
        users = await FriendService.search_users(query, user_id)
        return JSONResponse(status_code=200, content=jsonable_encoder(users))
    except Exception as e:
        logger.error(f"Error in user search: {e}")
        raise HTTPException(status_code=500, detail="Failed to search users")

@router.post("/friends/request")
async def send_friend_request(
    request: FriendRequestCreate,
    user_id: str = Query(...)
):
    """Send a friend request."""
    try:
        result = await FriendService.send_friend_request(
            sender_id=user_id,
            receiver_id=request.receiver_id
        )
        
        if result.get("success"):
            return JSONResponse(status_code=200, content={"message": "Friend request sent", "request_id": result.get("request_id")})
        else:
            raise HTTPException(status_code=400, detail=result.get("message"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending friend request: {e}")
        raise HTTPException(status_code=500, detail="Failed to send friend request")

@router.put("/friends/respond")
async def respond_to_friend_request(
    response: FriendRespond,
    user_id: str = Query(...)
):
    """Accept or reject a friend request."""
    try:
        result = await FriendService.respond_to_request(
            request_id=response.request_id,
            action=response.action
        )
        
        if result.get("success"):
            return JSONResponse(status_code=200, content={"message": f"Request {result.get('status')}"})
        else:
            raise HTTPException(status_code=400, detail=result.get("message"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error responding to friend request: {e}")
        raise HTTPException(status_code=500, detail="Failed to respond to request")

@router.get("/friends/list")
async def get_friends_list(user_id: str = Query(...)):
    """Get user's friends list."""
    try:
        friends = await FriendService.get_friends_list(user_id)
        return JSONResponse(status_code=200, content=jsonable_encoder(friends))
    except Exception as e:
        logger.error(f"Error getting friends list: {e}")
        raise HTTPException(status_code=500, detail="Failed to get friends list")

@router.get("/friends/requests/pending")
async def get_pending_requests(user_id: str = Query(...)):
    """Get pending incoming friend requests for the user."""
    try:
        requests = await FriendService.get_pending_requests(user_id)
        return JSONResponse(status_code=200, content=jsonable_encoder(requests))
    except Exception as e:
        logger.error(f"Error getting pending requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending requests")

@router.delete("/friends/remove")
async def remove_friend(
    friend_id: str = Query(...),
    user_id: str = Query(...)
):
    """Remove a friend."""
    try:
        success = await FriendService.remove_friend(user_id, friend_id)
        if success:
            return JSONResponse(status_code=200, content={"message": "Friend removed"})
        else:
            raise HTTPException(status_code=400, detail="Failed to remove friend or friend not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing friend: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove friend")

@router.delete("/friends/request/cancel")
async def cancel_friend_request(
    receiver_id: str = Query(...),
    user_id: str = Query(...)
):
    """Cancel an outgoing pending friend request (sender cancels)."""
    try:
        result = await FriendService.cancel_friend_request(
            sender_id=user_id,
            receiver_id=receiver_id
        )
        
        if result.get("success"):
            return JSONResponse(status_code=200, content={"message": "Friend request cancelled"})
        else:
            raise HTTPException(status_code=400, detail=result.get("message"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling friend request: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel friend request")

@router.get("/friends/requests/sent")
async def get_sent_requests(user_id: str = Query(...)):
    """Get outgoing pending friend requests sent by the user."""
    try:
        requests = await FriendService.get_sent_pending_requests(user_id)
        return JSONResponse(status_code=200, content=jsonable_encoder(requests))
    except Exception as e:
        logger.error(f"Error getting sent requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sent requests")
