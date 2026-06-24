"""
Feedback Routes - User feedback collection for AI responses

Endpoints:
- POST /feedback/submit - Record user feedback (helpful/confusing)
- GET /feedback/message/{message_id} - Get feedback stats for a message
- GET /feedback/session/{session_id} - Get all feedback for a session
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from backend.db.mongo import get_db

router = APIRouter()
db = get_db()

class FeedbackRequest(BaseModel):
    """Feedback submission from user"""
    session_id: str
    message_index: int  # Position in conversation
    helpful: bool  # True = 👍 helpful, False = 👎 confusing
    message_content: str  # AI response that was rated
    emotion: str  # Emotion detected for this response
    concept: str  # Concept being taught

class FeedbackResponse(BaseModel):
    """Response from feedback submission"""
    success: bool
    feedback_id: str
    message: str


@router.post("/submit", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback for an AI response.
    
    Creates a feedback record with:
    - User's rating (helpful/confusing)
    - Message metadata (emotion, concept, content)
    - Timestamp
    - Session context
    """
    try:
        # Verify session exists
        session = db["sessions"].find_one({"session_id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Create feedback record
        feedback_record = {
            "session_id": request.session_id,
            "user_id": session.get("user_id"),
            "message_index": request.message_index,
            "helpful": request.helpful,
            "message_content": request.message_content,
            "emotion": request.emotion,
            "concept": request.concept,
            "timestamp": datetime.now(),
            "rating": "helpful" if request.helpful else "confusing"
        }
        
        # Insert into feedback collection
        result = db["feedback"].insert_one(feedback_record)
        feedback_id = str(result.inserted_id)
        
        print(f"[FEEDBACK] ✅ Recorded feedback: {feedback_id} - {request.helpful and '👍 helpful' or '👎 confusing'}")
        
        return FeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            message=f"Feedback recorded: {request.helpful and '👍 Helpful' or '👎 Confusing'}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[FEEDBACK] ❌ Error recording feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/message/{session_id}/{message_index}")
async def get_message_feedback(session_id: str, message_index: int):
    """
    Get feedback statistics for a specific message.
    
    Returns:
    - Total feedback count
    - Helpful count (👍)
    - Confusing count (👎)
    - Percentage helpful
    """
    try:
        # Get all feedback for this message
        feedback_records = list(db["feedback"].find({
            "session_id": session_id,
            "message_index": message_index
        }))
        
        total = len(feedback_records)
        helpful_count = len([f for f in feedback_records if f.get("helpful")])
        confusing_count = total - helpful_count
        
        percentage_helpful = (helpful_count / total * 100) if total > 0 else 0
        
        return {
            "session_id": session_id,
            "message_index": message_index,
            "total_feedback": total,
            "helpful": helpful_count,
            "confusing": confusing_count,
            "percentage_helpful": round(percentage_helpful, 1),
            "status": "success"
        }
        
    except Exception as e:
        print(f"[FEEDBACK] ❌ Error fetching message feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_feedback(session_id: str):
    """
    Get all feedback for a session.
    
    Returns:
    - Feedback by message
    - Overall stats
    - Emotion breakdown
    """
    try:
        # Get all feedback for session
        feedback_records = list(db["feedback"].find({"session_id": session_id}))
        
        if not feedback_records:
            return {
                "session_id": session_id,
                "total_feedback": 0,
                "feedback_by_message": [],
                "overall_helpful_percentage": 0,
                "status": "success"
            }
        
        total = len(feedback_records)
        helpful_count = len([f for f in feedback_records if f.get("helpful")])
        
        # Group by message
        feedback_by_message = {}
        for fb in feedback_records:
            msg_idx = fb.get("message_index")
            if msg_idx not in feedback_by_message:
                feedback_by_message[msg_idx] = {
                    "helpful": 0,
                    "confusing": 0,
                    "emotion": fb.get("emotion"),
                    "concept": fb.get("concept")
                }
            
            if fb.get("helpful"):
                feedback_by_message[msg_idx]["helpful"] += 1
            else:
                feedback_by_message[msg_idx]["confusing"] += 1
        
        # Emotion breakdown
        emotion_breakdown = {}
        for emotion in ["engaged", "neutral", "confused", "frustrated"]:
            emotion_feedback = [f for f in feedback_records if f.get("emotion") == emotion]
            if emotion_feedback:
                emotion_helpful = len([f for f in emotion_feedback if f.get("helpful")])
                emotion_breakdown[emotion] = {
                    "total": len(emotion_feedback),
                    "helpful": emotion_helpful,
                    "confusing": len(emotion_feedback) - emotion_helpful
                }
        
        return {
            "session_id": session_id,
            "total_feedback": total,
            "overall_helpful_count": helpful_count,
            "overall_confusing_count": total - helpful_count,
            "overall_helpful_percentage": round(helpful_count / total * 100, 1),
            "feedback_by_message": feedback_by_message,
            "emotion_breakdown": emotion_breakdown,
            "status": "success"
        }
        
    except Exception as e:
        print(f"[FEEDBACK] ❌ Error fetching session feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/concept/{concept}")
async def get_concept_analytics(concept: str):
    """
    Get feedback analytics across all sessions for a concept.
    
    Returns:
    - Total feedback for concept
    - Helpful percentage
    - Common patterns
    """
    try:
        feedback_records = list(db["feedback"].find({"concept": concept}))
        
        if not feedback_records:
            return {
                "concept": concept,
                "total_feedback": 0,
                "status": "success"
            }
        
        total = len(feedback_records)
        helpful = len([f for f in feedback_records if f.get("helpful")])
        
        # Emotion breakdown for this concept
        emotion_stats = {}
        for record in feedback_records:
            emotion = record.get("emotion", "unknown")
            if emotion not in emotion_stats:
                emotion_stats[emotion] = {"helpful": 0, "confusing": 0}
            
            if record.get("helpful"):
                emotion_stats[emotion]["helpful"] += 1
            else:
                emotion_stats[emotion]["confusing"] += 1
        
        return {
            "concept": concept,
            "total_feedback": total,
            "helpful_count": helpful,
            "confusing_count": total - helpful,
            "helpful_percentage": round(helpful / total * 100, 1),
            "emotion_breakdown": emotion_stats,
            "status": "success"
        }
        
    except Exception as e:
        print(f"[FEEDBACK] ❌ Error fetching concept analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
