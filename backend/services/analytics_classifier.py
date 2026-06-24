import os
import json
import logging
import traceback
from datetime import datetime, timezone, timedelta
from backend.db.mongo import db

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_gemini_enabled = False
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_enabled = True
    except Exception as e:
        logger.error(f"[ANALYTICS] Failed to configure Gemini API: {e}")

async def classify_message_background(
    user_msg: str, 
    tutor_reply: str, 
    session_id: str, 
    user_id: str, 
    current_timestamp: datetime, 
    prev_message_timestamp: datetime
):
    """
    Background task that extracts structured data from a conversational exchange.
    Swallows all exceptions to ensure it never crashes the active application.
    """
    try:
        if not GEMINI_API_KEY:
            logger.warning("[ANALYTICS] GEMINI_API_KEY not found. Skipping classification.")
            return

        # Calculate Active Time (Max 5 minute gap)
        active_minutes = 0.0
        if prev_message_timestamp:
            delta_seconds = (current_timestamp - prev_message_timestamp).total_seconds()
            if 0 <= delta_seconds <= 300: # 5 minutes
                active_minutes = delta_seconds / 60.0

        # Run Classification
        model = genai.GenerativeModel("gemini-1.5-flash", generation_config={"response_mime_type": "application/json"})
        prompt = f"""
You are an educational analytics classifier. Analyze the following exchange between a learner and an AI tutor.
Extract the relevant metrics and return ONLY a valid JSON object matching this exact schema:

{{
    "topic": "string (the broad subject, e.g., 'Python', 'HTML')",
    "concept_id": "string (the specific concept, e.g., 'loops', 'tags')",
    "sentiment": "string (one of: 'confident', 'confused', 'stuck', 'neutral', 'frustrated')",
    "is_question": boolean (true if user asked a question),
    "is_confusion": boolean (true if user expressed confusion),
    "gave_praise": boolean (true if tutor praised the user),
    "corrected_mistake": boolean (true if tutor corrected a user's mistake),
    "introduced_new_concept": boolean (true if tutor introduced something new),
    "gave_answer_directly": boolean (true if tutor provided the direct answer without waiting for the user to figure it out)
}}

User Message: "{user_msg}"
Tutor Reply: "{tutor_reply}"
"""
        response = model.generate_content(prompt)
        
        try:
            classification = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"[ANALYTICS] Failed to parse JSON from classifier: {response.text}")
            classification = {}
            
        # Write Event Row
        event_row = {
            "session_id": session_id,
            "user_id": user_id,
            "timestamp": current_timestamp,
            "active_minutes": active_minutes,
            "classification_version": 1,
            "raw_user_msg": user_msg, # Optional, useful for debugging
            **classification
        }
        
        db["analytics_events"].insert_one(event_row)
        
        # Check Mastery (Aggregation Pipeline)
        # We need 3 consecutive correct answers without hints (gave_answer_directly = False)
        # A "correct answer" implies they weren't confused, and they weren't stuck.
        concept_id = classification.get("concept_id")
        if concept_id and not classification.get("is_confusion") and not classification.get("gave_answer_directly"):
            # Check the last 3 events for this session and concept
            pipeline = [
                {"$match": {"session_id": session_id, "concept_id": concept_id}},
                {"$sort": {"timestamp": -1}},
                {"$limit": 3}
            ]
            recent_events = list(db["analytics_events"].aggregate(pipeline))
            
            if len(recent_events) == 3:
                # If all 3 have gave_answer_directly == False and is_confusion == False
                is_mastered = all(
                    not e.get("gave_answer_directly", False) and 
                    not e.get("is_confusion", False) and 
                    e.get("sentiment") in ["confident", "neutral"]
                    for e in recent_events
                )
                
                if is_mastered:
                    # Fire EVENT_CONCEPT_MASTERED
                    db["sessions"].update_one(
                        {"session_id": session_id},
                        {"$push": {"events": {
                            "event_type": "EVENT_CONCEPT_MASTERED",
                            "session_id": session_id,
                            "user_id": user_id,
                            "timestamp": current_timestamp,
                            "concept": concept_id,
                            "metadata": {"source": "background_classifier"}
                        }}}
                    )
                    logger.info(f"[ANALYTICS] Concept mastered: {concept_id}")

    except Exception as e:
        logger.error(f"[ANALYTICS] Background classification failed: {e}")
        logger.debug(traceback.format_exc())
