#chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.services.translator import translate_text, detect_language
from backend.services.database import save_chat_message

router = APIRouter()

class TranslateRequest(BaseModel):
    text: str
    lang: str
    user_id: Optional[str] = "default_user"

@router.post("/translate")
def translate(request: TranslateRequest):
    """
    Translate text to a specified language.
    Saves message to MongoDB.
    
    Input: {"text": "Mujhe samajh nahi aaya", "lang": "en", "user_id": "user123"}
    
    Output: {"original": "...", "translated": "...", "detected_lang": "...", "message_id": "..."}
    """
    
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if not request.lang or len(request.lang.strip()) == 0:
        raise HTTPException(status_code=400, detail="Language code required (e.g., 'en', 'hi', 'es')")
    
    # Detect original language
    detected_lang = detect_language(request.text)
    
    # Translate
    translated = translate_text(request.text, request.lang)
    
    # Save to database
    db_result = save_chat_message(
        user_id=request.user_id,
        original_text=request.text,
        translated_text=translated,
        source_lang=detected_lang,
        target_lang=request.lang
    )
    
    return {
        "original": request.text,
        "translated": translated,
        "detected_lang": detected_lang,
        "target_lang": request.lang,
        "message_id": db_result.get("message_id", None),
        "saved": db_result.get("success", False)
    }

@router.get("/history/{user_id}")
def get_chat_history(user_id: str, limit: int = 10):
    """
    Get chat/translation history for a user.
    """
    from backend.services.database import get_user_chats
    messages = get_user_chats(user_id, limit)
    return {
        "user_id": user_id,
        "total": len(messages),
        "messages": messages
    }
