from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.emotion import detect_emotion, adaptive_response, get_emotion_with_confidence
from services.database import save_learning_session
from services.rag import rag_pipeline, save_content
from services.evaluation import evaluate_answer, is_likely_answering, format_teaching_feedback
from .session import update_conversation_state, get_session_state, is_actual_answer, extract_question as extract_question_helper
from db.mongo import db

router = APIRouter()

class LearningRequest(BaseModel):
    text: str
    user_id: Optional[str] = "test_user"
    session_id: Optional[str] = None
    topic: Optional[str] = None

class ContentUploadRequest(BaseModel):
    user_id: str
    topic: str
    content: str

@router.post("/learn")
def learn(request: LearningRequest):
    """
    Learning API endpoint with RAG pipeline + AI Tutor + Answer Evaluation.
    
    Real tutor loop:
    1. User asks question
    2. AI explains and asks a follow-up question
    3. System tracks the question (conversation_state = "question_asked")
    4. User answers
    5. System detects user isanswering and evaluates answer
    6. System adapts next explanation based on answer quality
    7. Teaching mode changes (advanced/teach_basic/simplify)
    """
    
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    print(f"\n[LEARN] Request received:")
    print(f"  Text: {request.text[:50]}...")
    print(f"  Topic: {request.topic}")
    print(f"  Session: {request.session_id}")
    print(f"  User: {request.user_id}")
    
    # Detect emotion
    emotion = detect_emotion(request.text)
    print(f"  Detected Emotion: {emotion}")
    
    answer_evaluation_result = None
    is_evaluating_answer = False
    teaching_mode = "adaptive"
    current_concept = request.topic or "general"  # Default to request topic
    
    # Check if user is answering a question
    if request.session_id:
        session_state = get_session_state(request.session_id)
        print(f"[LEARN] Session state retrieved: {session_state}")
        
        if session_state:
            # Use the CURRENT CONCEPT from session (don't jump topics)
            current_concept = session_state.get("current_concept", session_state.get("topic", "general"))
            concept_mastery = session_state.get("concept_mastery", "learning")
            
            # Use the strict answer detection from session helpers
            is_answering = is_actual_answer(request.text, session_state.get("conversation_state", "idle"))
            print(f"[LEARN] Answer detection: state={session_state.get('conversation_state')}, is_answering={is_answering}")
            print(f"[LEARN] Concept context: current={current_concept}, mastery={concept_mastery}")
            
            if is_answering:
                print(f"[LEARN] ✅ USER IS ANSWERING A QUESTION")
                is_evaluating_answer = True
                
                # Evaluate the answer
                topic_for_eval = current_concept
                question = session_state.get("last_question", "")
                
                answer_evaluation_result = evaluate_answer(
                    user_answer=request.text,
                    topic=topic_for_eval,
                    ai_question=question
                )
                
                print(f"[LEARN] Answer evaluation: {answer_evaluation_result.get('result')}")
                
                # CRITICAL: Update concept mastery based on ANSWER RESULT
                # Only advance teaching mode for CORRECT answers
                if answer_evaluation_result.get("result") == "correct":
                    teaching_mode = "advanced"
                    # Mark concept as advancing (can move to next concept if needed)
                    db["sessions"].update_one(
                        {"session_id": request.session_id},
                        {"$set": {"concept_mastery": "advancing"}}
                    )
                    print(f"[LEARN] ✅ Concept advancing - user understands")
                elif answer_evaluation_result.get("result") == "partial":
                    teaching_mode = "teach_basic"
                    # Stay on same concept with refinement
                    attempt_count = session_state.get("concept_attempt_count", 0) + 1
                    db["sessions"].update_one(
                        {"session_id": request.session_id},
                        {"$set": {"concept_attempt_count": attempt_count}}
                    )
                    print(f"[LEARN] 📌 Partial answer - refining same concept (attempt {attempt_count})")
                else:
                    teaching_mode = "simplify"
                    # Stay on same concept, simplify more
                    attempt_count = session_state.get("concept_attempt_count", 0) + 1
                    db["sessions"].update_one(
                        {"session_id": request.session_id},
                        {"$set": {"concept_attempt_count": attempt_count}}
                    )
                    print(f"[LEARN] ❌ Incorrect answer - simplifying same concept (attempt {attempt_count})")
                
                # Reset conversation state for next interaction
                update_conversation_state(request.session_id, "idle")
    
    # CRITICAL FIX: Use current_concept from session, NOT arbitrary request.topic
    # This prevents topic jumping - always teach the concept tracked in the session
    if request.session_id:
        topic_to_teach = current_concept
    else:
        topic_to_teach = request.topic or "general"
    
    # Run RAG pipeline with AI tutor (with teaching mode adaptation)
    print(f"[LEARN] Running RAG pipeline")
    print(f"  Topic to teach: {topic_to_teach}")
    print(f"  Teaching mode: {teaching_mode}")
    rag_result = rag_pipeline(
        user_input=request.text,
        user_id=request.user_id,
        topic=topic_to_teach,
        emotion=emotion,
        teaching_mode=teaching_mode
    )
    
    print(f"[LEARN] RAG Result: has_content={rag_result.get('has_content')}, ai_powered={rag_result.get('ai_powered')}")
    
    # Extract question from response for next turn (so we can detect if user is answering)
    # Note: quick_check field already contains just the question text (parsed by ai_tutor)
    extracted_question = rag_result.get('quick_check', '').strip()
    
    # Update conversation state if question was asked (mark that we're waiting for an answer)
    if extracted_question and request.session_id:
        update_conversation_state(request.session_id, "question_asked", extracted_question)
        print(f"[LEARN] ✅ Question tracked: {extracted_question[:60]}...")
    
    # Generate adaptive response (for compatibility)
    response = adaptive_response(emotion)
    
    # Save to database
    db_result = save_learning_session(
        user_id=request.user_id,
        text=request.text,
        emotion=emotion,
        response=response,
        session_id=request.session_id,
        topic=request.topic
    )
    
    # Build final response
    final_response = {
        "emotion": rag_result["emotion"],
        "explanation": rag_result.get("explanation") or "",
        "example": rag_result.get("example") or "",
        "quick_check": rag_result.get("quick_check") or "",
        "chunk": rag_result.get("chunk"),
        "has_content": rag_result.get("has_content", False),
        "ai_powered": rag_result.get("ai_powered", False),
        "message": rag_result.get("message"),
        "response": response,
        "session_id": db_result.get("session_id", None),
        "saved": db_result.get("success", False),
        "is_answer_evaluation": is_evaluating_answer,
        "answer_evaluation": answer_evaluation_result
    }
    
    print(f"[LEARN] Response: is_answer_evaluation={is_evaluating_answer}")
    return final_response

@router.post("/upload-content")
def upload_content(request: ContentUploadRequest):
    """
    Upload study material for a topic.
    Content is chunked and stored for RAG retrieval.
    """
    if not request.content or len(request.content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    
    result = save_content(
        user_id=request.user_id,
        topic=request.topic,
        content=request.content
    )
    
    return result

@router.get("/history/{user_id}")
def get_learning_history(user_id: str):
    """Get user's learning history"""
    from db.mongo import db
    
    history = list(db["learning_sessions"].find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(50))
    
    return {
        "user_id": user_id,
        "sessions": history,
        "count": len(history)
    }

@router.post("/analyze")
def analyze_learning(request: LearningRequest):
    """Detailed analysis of a learning response"""
    emotion_data = get_emotion_with_confidence(request.text)
    
    return {
        "text": request.text,
        "emotion": emotion_data.get("emotion"),
        "confidence": emotion_data.get("confidence"),
        "scores": emotion_data.get("scores")
    }

@router.get("/analytics")
def get_analytics(user_id: str):
    """
    Get learning analytics for a user.
    Returns emotion distribution and session metrics.
    
    Args:
        user_id: User ID to get analytics for
    
    Returns:
        {
            "user_id": "...",
            "total_sessions": N,
            "very_frustrated": X%,
            "frustrated": X%,
            "neutral": X%,
            "confused": X%,
            "engaged": X%,
            "very_engaged": X%
        }
    """
    try:
        # Get all sessions for this user
        sessions = list(db["sessions"].find({"user_id": user_id}))
        
        if not sessions:
            return {
                "user_id": user_id,
                "total_sessions": 0,
                "very_frustrated": 0,
                "frustrated": 0,
                "neutral": 0,
                "confused": 0,
                "engaged": 0,
                "very_engaged": 0,
                "message": "No sessions found"
            }
        
        # Count emotions from all messages in sessions
        emotion_counts = {
            "very_frustrated": 0,
            "frustrated": 0,
            "neutral": 0,
            "confused": 0,
            "engaged": 0,
            "very_engaged": 0
        }
        
        total_emotions = 0
        
        for session in sessions:
            # Check both old and new message formats
            messages = session.get("messages", [])
            
            # Also check if emotions are stored directly
            if "emotions" in session:
                for emotion_entry in session.get("emotions", []):
                    emotion = emotion_entry.get("emotion") if isinstance(emotion_entry, dict) else emotion_entry
                    if emotion in emotion_counts:
                        emotion_counts[emotion] += 1
                        total_emotions += 1
            
            # Check conversation state for embedded emotions
            if "emotion" in session:
                emotion = session.get("emotion")
                if emotion in emotion_counts:
                    emotion_counts[emotion] += 1
                    total_emotions += 1
        
        # If no emotions found, default to showing some engaged state
        # (since users are actively learning)
        if total_emotions == 0:
            total_emotions = 1
            emotion_counts["engaged"] = 1
        
        # Calculate percentages
        percentages = {
            k: round((v / total_emotions * 100) if total_emotions > 0 else 0, 2)
            for k, v in emotion_counts.items()
        }
        
        return {
            "user_id": user_id,
            "total_sessions": len(sessions),
            **percentages,
            "last_session": sessions[-1].get("start_time", "").isoformat() if sessions else None
        }
        
    except Exception as e:
        print(f"[ANALYTICS] Error: {e}")
        return {
            "user_id": user_id,
            "total_sessions": 0,
            "very_frustrated": 0,
            "frustrated": 0,
            "neutral": 0,
            "confused": 0,
            "engaged": 0,
            "very_engaged": 0,
            "error": str(e)
        }
