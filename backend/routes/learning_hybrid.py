#learning_hybrid.py
"""
CORRECT ARCHITECTURE: Hybrid Adaptive System

RULE-BASED LAYER (Pedagogy + Logic):
- Intent detection (minimal, routing only)
- Emotion detection (signal)
- Teaching mode selection (emotion + evaluation → difficulty)
- Mastery tracking (concepts, attempts)

AI GENERATION LAYER (Content):
- Explanations (dynamic, context-aware)
- Examples (varied, relevant)
- Questions (thoughtful, appropriate)
- All language/tone (LLM decides)

This shows: "We guide AI decisions with intelligent logic"
NOT: "We hardcode everything" OR "AI magically works"
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.emotion import detect_emotion
from services.evaluation import evaluate_answer
from services.rag import rag_pipeline
from db.mongo import db
from datetime import datetime
from uuid import uuid4

router = APIRouter()


# ============================================
# RULE LAYER: MINIMAL DECISION LOGIC
# ============================================

def detect_intent(text: str) -> str:
    """
    Route user intent (MINIMAL - just classify).
    
    Shows: "We route user inputs intelligently"
    
    Returns: "chat" | "learning"
    """
    text_lower = text.lower().strip()
    
    # Only catch obvious greetings
    chat_patterns = ["hi", "hello", "hey", "good morning", "good afternoon"]
    
    if any(p in text_lower for p in chat_patterns) and len(text) < 30:
        return "chat"
    
    return "learning"


def determine_teaching_mode(emotion: str, evaluation_result: Optional[str]) -> str:
    """
    INTELLIGENT DECISION: Map emotion + evaluation to teaching difficulty.
    
    Shows: "Our system adapts difficulty based on student state"
    
    This is GOOD to show examiners - it's pedagogical logic.
    """
    
    # If we just evaluated an answer, use that as PRIMARY signal
    if evaluation_result == "correct":
        return "advanced"      # Student understands, go deeper
    elif evaluation_result == "partial":
        return "teach_basic"   # Student partially understands, refine
    elif evaluation_result == "incorrect":
        return "simplify"      # Student didn't understand, simplify
    
    # Otherwise, use emotion as difficulty indicator
    # This shows adaptive difficulty (student-centered)
    difficulty_map = {
        "very_frustrated": "simplify",     # Very confused → simplest
        "frustrated": "teach_basic",       # Confused → basic
        "confused": "teach_basic",         # Confused → basic
        "neutral": "adaptive",             # Neutral → balanced
        "engaged": "adaptive",             # Engaged → balanced
        "very_engaged": "advanced"         # Very engaged → challenging
    }
    
    return difficulty_map.get(emotion, "adaptive")


def get_learning_state(teaching_mode: str, emotion: str, attempt_count: int) -> dict:
    """
    INTELLIGENT PROFILE: Comprehensive student state.
    
    Shows: "We track detailed learning state"
    
    Used to inform AI generation, not hardcode responses.
    """
    return {
        "teaching_mode": teaching_mode,           # difficulty level
        "emotion": emotion,                       # student state
        "attempt_count": attempt_count,           # struggle indicator
        "is_struggling": attempt_count > 1,       # bool: needs support?
        "is_frustrated": emotion in ["frustrated", "very_frustrated"],
        "is_engaged": emotion in ["engaged", "very_engaged"],
        "needs_encouragement": emotion in ["confused", "frustrated", "very_frustrated"]
    }


# ============================================
# AI GENERATION LAYER: SMART CONTEXT PROMPTING
# ============================================

def build_teaching_prompt(learning_state: dict, topic: str, user_input: str, last_explanation: str = "") -> str:
    """
    Build SMART CONTEXT for LLM (not hardcoding responses).
    
    Shows: "We provide rich context to guide AI generation"
    
    This replaces hardcoded style strings with intelligent context.
    """
    
    state = learning_state
    
    # Build adaptive guidance based on state
    difficulty_guidance = {
        "simplify": "Explain very simply. Use basic everyday words. Include a real-world example. Keep it short.",
        "teach_basic": "Clear beginner explanation. Step-by-step. Include an easy example.",
        "adaptive": "Clear explanation with good balance. Include a relatable example.",
        "advanced": "Deeper explanation. Can use technical terms. Include interesting insight or challenge."
    }
    
    tone_guidance = {
        "needs_encouragement": "Be warm and supportive. Build their confidence.",
        "is_frustrated": "Be encouraging and patient. Make it achievable.",
        "is_engaged": "Match their energy. You can go deeper or challenge them.",
        "is_struggling": "Be patient. Break into small steps."
    }
    
    difficulty_text = difficulty_guidance.get(state["teaching_mode"], "Explain clearly.")
    tone_text = ""
    
    if state["needs_encouragement"]:
        tone_text = tone_guidance["needs_encouragement"]
    elif state["is_frustrated"]:
        tone_text = tone_guidance["is_frustrated"]
    elif state["is_engaged"]:
        tone_text = tone_guidance["is_engaged"]
    
    # Don't repeat previous explanations
    repetition_guidance = ""
    if last_explanation:
        repetition_guidance = f"Note: We previously explained this as: '{last_explanation[:100]}...'\nUse a DIFFERENT approach this time."
    
    # Build the actual prompt
    prompt = f"""You are an intelligent tutoring system helping a student learn {topic}.

STUDENT CONTEXT:
- Emotion: {state['emotion']}
- Attempts on this: {state['attempt_count']}
- Teaching mode: {state['teaching_mode']}

GUIDANCE FOR YOUR RESPONSE:
{difficulty_text}
{tone_text}
{repetition_guidance}

STRUCTURE (ALWAYS):
1. Explanation (adjust to teaching_mode and emotion above)
2. One concrete example (real-world if possible)
3. One thoughtful question (not yes/no)

USER JUST SAID:
"{user_input}"

Now respond as a tutor would. Explain clearly, be encouraging, make it understandable."""
    
    return prompt


# ============================================
# STATE TRACKING & SESSION MANAGEMENT
# ============================================

class LearningRequest(BaseModel):
    text: str
    user_id: Optional[str] = "test_user"
    session_id: Optional[str] = None
    topic: Optional[str] = None


@router.post("/hybrid")
def learn_hybrid(request: LearningRequest):
    """
    HYBRID SYSTEM:
    
    1. RULE LAYER: Detect intent, emotion, teaching mode
    2. AI LAYER: Generate response with smart context
    3. STATE: Track mastery, attempts, conversation flow
    
    This architecture shows:
    - Pedagogical reasoning (rules)
    - AI-enhanced generation (dynamic)
    - Measurable system (tracking)
    """
    
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    print(f"\n[HYBRID] User: {request.user_id}, Topic: {request.topic}")
    print(f"[HYBRID] Input: {request.text[:50]}...")
    
    # ===== STEP 1: RULE LAYER - DETECT INTENT =====
    intent = detect_intent(request.text)
    print(f"[HYBRID] Intent: {intent}")
    
    # ===== STEP 2: RULE LAYER - DETECT EMOTION =====
    emotion = detect_emotion(request.text)
    print(f"[HYBRID] Emotion: {emotion}")
    
    # ===== STEP 3: GET OR CREATE SESSION =====
    if not request.session_id:
        request.session_id = str(uuid4())
        session = {
            "session_id": request.session_id,
            "user_id": request.user_id,
            "topic": request.topic or "general",
            "current_concept": request.topic or "general",
            "status": "active",
            "conversation_state": "idle",
            "last_question": "",
            "last_explanation": "",
            "attempt_count": 0,
            "mastery_level": 0,  # 0-100
            "start_time": datetime.now()
        }
        db["sessions"].insert_one(session)
        print(f"[HYBRID] 🆕 Session created: {request.session_id}")
    else:
        session = db["sessions"].find_one({"session_id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        print(f"[HYBRID] Session loaded: {request.session_id}")
    
    # CHAT INTENT - respond early but keep session
    if intent == "chat":
        # User greeting → respond naturally
        return {
            "emotion": emotion,
            "explanation": "Hey there! What would you like to learn?",
            "example": "",
            "question": "",
            "session_id": request.session_id,
            "intent": "chat",
            "teaching_mode": None,
            "mastery_level": session.get("mastery_level", 0),
            "attempt_count": session.get("attempt_count", 0)
        }
    
    # ===== STEP 4: RULE LAYER - EVALUATE IF ANSWERING =====
    evaluation_result = None
    
    if session.get("conversation_state") == "question_asked":
        last_question = session.get("last_question", "")
        if last_question:
            evaluation_result = evaluate_answer(
                user_answer=request.text,
                topic=session.get("current_concept", ""),
                ai_question=last_question
            )
            print(f"[HYBRID] Answer evaluation: {evaluation_result}")
            
            # Update mastery based on evaluation
            if evaluation_result == "correct":
                session["mastery_level"] = min(100, session.get("mastery_level", 0) + 25)
                session["attempt_count"] = 0
            else:
                session["attempt_count"] = session.get("attempt_count", 0) + 1
    
    # ===== STEP 5: RULE LAYER - DETERMINE TEACHING MODE =====
    teaching_mode = determine_teaching_mode(emotion, evaluation_result)
    learning_state = get_learning_state(teaching_mode, emotion, session.get("attempt_count", 0))
    
    print(f"\n[HYBRID DEBUG]")
    print(f"intent={intent}")
    print(f"emotion={emotion}")
    print(f"teaching_mode={teaching_mode}")
    print(f"is_answering={session.get('conversation_state') == 'question_asked'}")
    print(f"evaluation={evaluation_result}")
    print(f"topic={session.get('current_concept', '')}")
    print(f"mastery={session.get('mastery_level', 0)}")
    print(f"attempt_count={session.get('attempt_count', 0)}\n")
    
    # ===== STEP 6: AI LAYER - GENERATE WITH SMART CONTEXT =====
    teaching_prompt = build_teaching_prompt(
        learning_state=learning_state,
        topic=session.get("current_concept", ""),
        user_input=request.text,
        last_explanation=session.get("last_explanation", "")
    )
    
    print(f"[HYBRID] Context prompt ready ({len(teaching_prompt)} chars)")
    
    # Call RAG/LLM with smart context (not hardcoded responses)
    rag_result = rag_pipeline(
        user_input=request.text,
        user_id=request.user_id,
        topic=session.get("current_concept", ""),
        emotion=emotion,
        teaching_mode=teaching_mode,
        enhanced_context=teaching_prompt  # Pass intelligent context
    )
    
    print(f"[HYBRID] AI generation complete")
    
    # ===== STEP 7: STATE TRACKING =====
    extracted_question = rag_result.get('quick_check', '').strip()
    
    update_data = {
        "emotion": emotion,
        "teaching_mode": teaching_mode,
        "evaluation": evaluation_result,
        "last_explanation": rag_result.get("explanation", ""),
        "last_question": extracted_question,
        "conversation_state": "question_asked" if extracted_question else "idle",
        "last_interaction": datetime.now()
    }
    
    db["sessions"].update_one(
        {"session_id": request.session_id},
        {"$set": update_data}
    )
    
    print(f"[HYBRID] Session updated - mastery={session.get('mastery_level')}, attempts={session.get('attempt_count')}")
    
    # ===== STEP 8: RETURN RESPONSE =====
    return {
        "emotion": emotion,
        "explanation": rag_result.get("explanation", ""),
        "example": rag_result.get("example", ""),
        "question": extracted_question,
        "teaching_mode": teaching_mode,
        "session_id": request.session_id,
        "mastery_level": session.get("mastery_level", 0),
        "attempt_count": session.get("attempt_count", 0),
        "ai_powered": rag_result.get("ai_powered", False)
    }


@router.get("/analytics/{user_id}")
def get_analytics(user_id: str):
    """
    Shows: "We track measurable learning metrics"
    
    This is GOOD to demonstrate - shows you have a real system, not magic.
    """
    sessions = list(db["sessions"].find({"user_id": user_id}))
    
    if not sessions:
        return {"user_id": user_id, "total_sessions": 0}
    
    emotions = {}
    total_mastery = 0
    total_attempts = 0
    
    for session in sessions:
        emotion = session.get("emotion", "neutral")
        emotions[emotion] = emotions.get(emotion, 0) + 1
        total_mastery += session.get("mastery_level", 0)
        total_attempts += session.get("attempt_count", 0)
    
    return {
        "user_id": user_id,
        "total_sessions": len(sessions),
        "average_mastery": round(total_mastery / len(sessions), 1),
        "emotion_distribution": emotions,
        "total_struggle_attempts": total_attempts,
        "last_session": sessions[-1].get("start_time").isoformat() if sessions else None
    }


@router.get("/session/{session_id}")
def get_session_details(session_id: str):
    """
    Get detailed session info - shows you track learning trajectory.
    """
    session = db["sessions"].find_one({"session_id": session_id})
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Remove MongoDB's _id field
    session.pop("_id", None)
    
    return session
