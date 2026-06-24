"""
Friend Chat Routes
Completely independent social chat module with real-time translation.
Isolated from AI tutoring system (learning_production.py, ai_tutor_production.py).
"""

import os
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query, Path
from fastapi.responses import JSONResponse

from backend.models.message_model import (
    FriendMessageCreate,
    FriendMessageResponse,
    ChatHistoryRequest,
    UserPreferences,
)
from backend.services.websocket_manager import connection_manager
from backend.services.chat_service import ChatService
from backend.services.translation_service import TranslationService
from backend.services.friend_service import FriendService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/friend-chat", tags=["friend-chat"])

# Store offline messages temporarily (in production, use Redis)
_offline_queue: dict = {}


# ===== UTILITY FUNCTIONS =====


async def verify_user_participation(user_id: str, friend_id: str) -> bool:
    """Verify that user is requesting their own data."""
    return user_id is not None  # In production, validate against JWT


# ===== REST ENDPOINTS =====


@router.get("/history/{friend_id}")
async def get_message_history(
    friend_id: str = Path(..., description="Friend to fetch history with"),
    user_id: str = Query(..., description="Current user ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    Fetch paginated message history between user and friend.
    User can only access their own conversations.
    """
    try:
        if not await verify_user_participation(user_id, friend_id):
            raise HTTPException(status_code=403, detail="Unauthorized")

        result = await ChatService.get_message_history(
            user_id=user_id,
            friend_id=friend_id,
            page=page,
            page_size=page_size,
        )

        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        logger.error(f"Error fetching message history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


@router.get("/preferences")
async def get_user_preferences(user_id: str = Query(...)):
    """Fetch user's translation preferences."""
    try:
        prefs = await ChatService.get_user_preferences(user_id)
        return JSONResponse(status_code=200, content=prefs)
    except Exception as e:
        logger.error(f"Error fetching preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch preferences")


@router.post("/preferences")
async def update_user_preferences(
    user_id: str = Query(...),
    preferences: UserPreferences = None,
):
    """Update user's translation preferences."""
    try:
        if not preferences:
            raise HTTPException(status_code=400, detail="Preferences required")

        success = await ChatService.update_user_preferences(
            user_id=user_id,
            preferences={
                "preferred_language": preferences.preferred_language,
                "auto_translate": preferences.auto_translate,
                "auto_read_aloud": preferences.auto_read_aloud,
            },
        )

        if success:
            return JSONResponse(
                status_code=200,
                content={"message": "Preferences updated successfully"},
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to update preferences")
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")


@router.get("/online-status")
async def get_online_status():
    """Get list of currently online users."""
    try:
        online_users = await connection_manager.get_online_users()
        return JSONResponse(
            status_code=200,
            content={"online_users": list(online_users)},
        )
    except Exception as e:
        logger.error(f"Error fetching online status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch status")


@router.get("/supported-languages")
async def get_supported_languages():
    """Get list of supported languages for translation."""
    languages = TranslationService.get_supported_languages()
    return JSONResponse(status_code=200, content=languages)


# ===== WEBSOCKET ENDPOINT =====


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    Main WebSocket connection for real-time friend chat.
    Handles messaging, typing indicators, and presence.
    """
    await connection_manager.connect(user_id, websocket)
    # Send current online users list to the connecting user
    online_users = list(await connection_manager.get_online_users())
    await connection_manager.send_personal_message(user_id, {
        "type": "presence_list",
        "users": online_users
    })
    await connection_manager.broadcast_presence(user_id, "online")
    await deliver_offline_messages(user_id)

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_websocket_message(user_id, data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user: {user_id}")
        await connection_manager.disconnect(user_id)
        await connection_manager.broadcast_presence(user_id, "offline")

    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        await connection_manager.disconnect(user_id)


async def _handle_websocket_message(user_id: str, data: dict) -> None:
    """
    Route WebSocket messages based on type.
    """
    message_type = data.get("type", "message")

    if message_type == "message":
        await _handle_chat_message(user_id, data)
    elif message_type == "typing":
        await _handle_typing_indicator(user_id, data)
    elif message_type == "read":
        await _handle_read_receipt(user_id, data)
    elif message_type == "ping":
        # Heartbeat ping: reply immediately with pong to keep connection alive
        await connection_manager.send_personal_message(user_id, {"type": "pong"})
    else:
        logger.warning(f"Unknown message type: {message_type}")


async def _handle_chat_message(user_id: str, data: dict) -> None:
    """
    Process incoming chat message.
    Translate and deliver to recipient or queue for offline.
    """
    try:
        receiver_id = data.get("receiver_id")
        text = data.get("text", "").strip()

        if not receiver_id or not text:
            logger.warning(f"Invalid message from {user_id}: missing receiver or text")
            return

        # Restrict message delivery only to accepted friends
        is_friend = await FriendService.are_friends(user_id, receiver_id)
        if not is_friend:
            logger.warning(f"Message blocked: {user_id} and {receiver_id} are not friends")
            return

        # Fetch receiver's preferences
        receiver_prefs = await ChatService.get_user_preferences(receiver_id)
        target_language = receiver_prefs.get("preferred_language", "en")
        auto_translate = receiver_prefs.get("auto_translate", True)

        print(f"\n>>> MESSAGE TRANSLATION")
        print(f">>> Sender: {user_id}")
        print(f">>> Receiver: {receiver_id}")
        print(f">>> Receiver preferences: {receiver_prefs}")
        print(f">>> Target language: {target_language}")
        print(f">>> Original text: {text}")

        # Translate message
        original_text, translated_text, source_language = (
            await TranslationService.detect_and_translate(
                text=text,
                target_language=target_language,
                user_auto_translate=auto_translate,
            )
        )

        print(f">>> After translation:")
        print(f">>> Source language: {source_language}")
        print(f">>> Translated text: {translated_text}")
        print(f">>> {source_language} → {target_language}\n")

        # Save to database
        message_id = await ChatService.save_message(
            sender_id=user_id,
            receiver_id=receiver_id,
            original_text=original_text,
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
        )

        timestamp = datetime.utcnow().isoformat()

        # Build delivery payload for receiver (with translation into receiver's language)
        receiver_payload = {
            "type": "message",
            "_id": message_id,
            "message_id": message_id,
            "sender_id": user_id,
            "receiver_id": receiver_id,
            "original_text": original_text,
            "translated_text": translated_text,
            "source_language": source_language,
            "target_language": target_language,
            "timestamp": timestamp,
            "read_status": False,
        }

        # Attempt delivery to receiver
        delivered = await connection_manager.send_personal_message(receiver_id, receiver_payload)

        if not delivered:
            logger.info(f"Receiver {receiver_id} offline - message {message_id} queued")
            _offline_queue.setdefault(receiver_id, []).append(receiver_payload)

        # Echo the message back to the sender so their UI updates in real-time.
        # The frontend uses 'isMine' to show the original_text by default, but we still 
        # need to pass the actual translated_text so the 'Show Translation' button works.
        sender_payload = {
            "type": "message",
            "_id": message_id,
            "message_id": message_id,
            "sender_id": user_id,
            "receiver_id": receiver_id,
            "original_text": original_text,
            "translated_text": translated_text,
            "source_language": source_language,
            "target_language": target_language,
            "timestamp": timestamp,
            "read_status": False,
        }
        await connection_manager.send_personal_message(user_id, sender_payload)

        # Simulated Auto-Reply for Demo Friends
        if receiver_id in ["maria_spanish", "yuki_japanese", "jean_french", "amit_hindi"]:
            asyncio.create_task(simulate_friend_reply(user_id, receiver_id, text))

    except Exception as e:
        logger.error(f"Error handling chat message from {user_id}: {e}")


async def _handle_typing_indicator(user_id: str, data: dict) -> None:
    """
    Broadcast typing indicator to recipient.
    """
    try:
        receiver_id = data.get("receiver_id")
        is_typing = data.get("is_typing", True)
        if receiver_id:
            await connection_manager.send_typing_indicator(user_id, receiver_id, is_typing)
    except Exception as e:
        logger.error(f"Error handling typing indicator: {e}")


async def _handle_read_receipt(user_id: str, data: dict) -> None:
    """
    Mark message as read.
    """
    try:
        message_id = data.get("message_id")
        sender_id = data.get("sender_id")
        if message_id:
            await ChatService.mark_as_read(message_id)
            if sender_id:
                # Route the read receipt back to the original sender
                await connection_manager.send_personal_message(sender_id, {
                    "type": "read",
                    "message_id": message_id,
                    "reader_id": user_id
                })
    except Exception as e:
        logger.error(f"Error handling read receipt: {e}")


# ===== RECONNECTION HANDLER =====


async def deliver_offline_messages(user_id: str) -> None:
    """
    Deliver queued messages to user upon reconnection.
    Called from frontend on connection re-establishment.
    """
    try:
        if user_id in _offline_queue:
            queued_messages = _offline_queue.pop(user_id)
            for message in queued_messages:
                await connection_manager.send_personal_message(user_id, message)
            logger.info(f"Delivered {len(queued_messages)} offline messages to {user_id}")
    except Exception as e:
        logger.error(f"Error delivering offline messages: {e}")


async def simulate_friend_reply(user_id: str, friend_id: str, user_text: str):
    """Simulate a reply from a demo friend using Gemini or templates."""
    try:
        await asyncio.sleep(2.0)  # Realistic typing delay
        
        # Broadcast typing indicator
        await connection_manager.send_typing_indicator(friend_id, user_id, True)
        await asyncio.sleep(2.0)
        await connection_manager.send_typing_indicator(friend_id, user_id, False)
        
        response_text = f"I received your message! You said: '{user_text}'"
        friend_lang = "en"
        
        if friend_id == "maria_spanish":
            friend_lang = "es"
            response_text = "¡Hola! Recibí tu mensaje. Es genial chatear contigo."
        elif friend_id == "yuki_japanese":
            friend_lang = "ja"
            response_text = "こんにちは！メッセージをいただきました。あなたとチャットできて嬉しいです。"
        elif friend_id == "jean_french":
            friend_lang = "fr"
            response_text = "Bonjour ! J'ai bien reçu ton message. C'est un plaisir de discuter."
        elif friend_id == "amit_hindi":
            friend_lang = "hi"
            response_text = "नमस्ते! मुझे आपका संदेश मिल गया है। आपसे चैट करके बहुत अच्छा लगा।"
            
        if os.getenv("GEMINI_API_KEY"):
            try:
                import google.generativeai as genai
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = (
                    f"You are simulating a friend named {friend_id} who speaks language code '{friend_lang}'. "
                    f"Your friend just sent you this message in their language: '{user_text}'. "
                    f"Respond to them naturally and casually in your native language ({friend_lang}). "
                    f"Respond ONLY with the message text, no quotes or explanations."
                )
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, model.generate_content, prompt)
                if res and res.text:
                    response_text = res.text.strip()
            except Exception as ex:
                logger.error(f"Error generating simulated reply: {ex}")

        # Translate reply to user's preferred language
        user_prefs = await ChatService.get_user_preferences(user_id)
        user_lang = user_prefs.get("preferred_language", "en")
        auto_translate = user_prefs.get("auto_translate", True)
        
        orig_text, trans_text, src_lang = await TranslationService.detect_and_translate(
            text=response_text,
            target_language=user_lang,
            user_auto_translate=auto_translate
        )
        
        message_id = await ChatService.save_message(
            sender_id=friend_id,
            receiver_id=user_id,
            original_text=orig_text,
            translated_text=trans_text,
            source_language=src_lang,
            target_language=user_lang,
        )
        
        payload = {
            "type": "message",
            "message_id": message_id,
            "sender_id": friend_id,
            "receiver_id": user_id,
            "original_text": orig_text,
            "translated_text": trans_text,
            "source_language": src_lang,
            "target_language": user_lang,
            "timestamp": datetime.utcnow().isoformat(),
            "read_status": False,
        }
        await connection_manager.send_personal_message(user_id, payload)
    except Exception as e:
        logger.error(f"Error in simulate_friend_reply: {e}")
