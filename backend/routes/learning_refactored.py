#learning_refactored.py

"""
REFACTORED: LLM-Guided Tutoring System

KEY PRINCIPLE:
- Backend: Provides SIGNALS (emotion, evaluation, session state)
- LLM: Makes DECISIONS (intent, tone, approach, content)

NOT hardcoding behavior - letting LLM decide dynamically based on context.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.emotion import detect_emotion, adaptive_response
from services.database import save_learning_session
from services.rag import rag_pipeline
from services.evaluation import evaluate_answer
from .session import get_session_state, update_conversation_state
from db.mongo import db
from datetime import datetime
from uuid import uuid4

router = APIRouter()

class LearningRequest(BaseModel):
    text: str
    user_id: Optional[str] = "test_user"
    session_id: Optional[str] = None
    topic: Optional[str] = None


@router.post("/learn")
def learn(request: LearningRequest):
    """
    REFACTORED: LLM-Guided Tutoring (NOT Hardcoded)
    
    Key Principle: Backend provides SIGNALS, LLM makes DECISIONS
    
    Backend signals:
    - emotion (detected)
    - teaching_mode (based on answer eval, not hardcoded)
    - session state (history, last question)
    - user input
    
    LLM decides:
    - intent (is user greeting? learning? answering?)
    - teaching approach
    - question type
    - tone
    """
    
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    print(f"\n[LEARN-REFACTORED] Request: session={request.session_id}, user={request.user_id}")
    print(f"[LEARN-REFACTORED] Text: {request.text[:60]}...")
    
    # ===== STEP 1: Detect emotion (backend responsibility) =====
    emotion = detect_emotion(request.text)
    print(f"[LEARN-REFACTORED] Emotion: {emotion}")
    
    # ===== STEP 2: Get or create session =====
    if not request.session_id:
        request.session_id = str(uuid4())
        topic = request.topic or "general"
        new_session = {
            "session_id": request.session_id,
            "user_id": request.user_id,
            "topic": topic,
            "current_concept": topic,
            "concepts": [topic],
            "concept_index": 0,
            "status": "active",
            "emotion": emotion,
            "attempt_count": 0,
            "start_time": datetime.now(),
            "last_interaction": datetime.now(),
            "conversation_state": "idle",
            "last_question": ""
        }
        db["sessions"].insert_one(new_session)
        print(f"[LEARN-REFACTORED] 🆕 Created new session: {request.session_id}")
        session = new_session
    else:
        session = db["sessions"].find_one({"session_id": request.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # ===== STEP 3: Determine teaching mode based on evaluation (NOT hardcoded) =====
    # Only evaluate if user was answering a question
    evaluation_result = None
    teaching_mode = "normal"
    
    if session.get("conversation_state") == "question_asked":
        # User might be answering the previous question
        last_question = session.get("last_question", "")
        if last_question:
            evaluation_result = evaluate_answer(
                user_answer=request.text,
                topic=session.get("current_concept", ""),
                ai_question=last_question
            )
            print(f"[LEARN-REFACTORED] Answer evaluation: {evaluation_result}")
            
            # Only change teaching_mode based on ACTUAL evaluation
            # (not arbitrary logic)
            if evaluation_result == "correct":
                teaching_mode = "advanced"  # User understood, can go deeper
            elif evaluation_result == "partial":
                teaching_mode = "refine"    # User partially got it, refine
            elif evaluation_result == "incorrect":
                teaching_mode = "simplify"  # User didn't understand, simplify
    
    current_topic = session.get("current_concept", session.get("topic", "general"))
    
    # ===== STEP 4: BUILD RICH CONTEXT FOR LLM (KEY CHANGE) =====
    # Instead of hardcoding behavior, provide complete context
    # Let LLM decide based on all signals
    
    # Get last explanation for repetition context
    last_explanation = session.get("last_explanation", "")
    attempt_count = session.get("attempt_count", 0)
    
    context_for_llm = f"""
You are an intelligent AI tutor having a natural conversation.

---
STUDENT CONTEXT:
- Emotion: {emotion}
- Topic: {current_topic}
- Conversation state: {session.get('conversation_state', 'idle')}
- Attempts on this concept: {attempt_count}
- Session active: {session.get('status') == 'active'}
- Teaching mode: {teaching_mode}

---
TEACHING SIGNALS (use to guide your approach):
- If teaching_mode is 'simplify': Student is struggling, explain more simply
- If teaching_mode is 'refine': Student has partial understanding, refine it
- If teaching_mode is 'advanced': Student understands well, go deeper
- If teaching_mode is 'normal': Use balanced explanation

STUDENT EMOTION SIGNALS (adapt tone accordingly):
- If very_frustrated: Be encouraging, break into tiny steps, build confidence
- If frustrated: Be supportive, keep it simpler than normal
- If confused: Be patient, use real-world examples first
- If neutral: Use clear structured explanation
- If engaged: Can go deeper or add interesting extensions
- If very_engaged: Challenge them, include advanced perspectives

---
CONVERSATION RULES (CRITICAL - follow these):
1. First, understand what the student is doing:
   - Are they greeting you casually? (respond naturally)
   - Are they asking a learning question? (teach it)
   - Are they answering your previous question? (evaluate implicitly, guide based on teaching_mode)
   - Are they confused or stuck? (simplify and support)

2. Response structure (ALWAYS):
   - A clear explanation (appropriate for current teaching_mode)
   - A concrete example (real-world or relatable)
   - One thoughtful open-ended question (not yes/no)

3. Tone & Language:
   - Match student emotion (supportive for frustrated, enthusiastic for engaged)
   - Avoid repeating same explanations (previous attempt was: {last_explanation[:100] if last_explanation else 'new topic'})
   - Sound natural, not robotic
   - Use varied explanation strategies

4. NO hardcoding:
   - Don't force template responses
   - Don't use forced enthusiasm
   - Don't repeat the same structure
   - Be genuinely responsive

---
PREVIOUS INTERACTION (for context):
Last question asked: {session.get('last_question', 'none')}
Student's teaching mode: {teaching_mode}
Evaluation of their answer: {evaluation_result if evaluation_result else 'not evaluated yet'}

---
NOW:
Student says: "{request.text}"

Respond naturally as a tutor would. Understand their intent dynamically and teach appropriately.
"""
    
    print(f"[LEARN-REFACTORED] 📊 Context prepared - emotion={emotion}, mode={teaching_mode}, eval={evaluation_result}")
    
    # ===== STEP 5: CALL RAG/LLM WITH RICH CONTEXT (NO HARDCODING) =====
    print(f"[LEARN-REFACTORED] Calling RAG with full context...")
    
    rag_result = rag_pipeline(
        user_input=request.text,
        user_id=request.user_id,
        topic=current_topic,
        emotion=emotion,
        teaching_mode=teaching_mode,
        enhanced_context=context_for_llm  # Pass full rich context
    )
    
    print(f"[LEARN-REFACTORED] RAG Result: ai_powered={rag_result.get('ai_powered')}, has_content={rag_result.get('has_content')}")
    
    # ===== STEP 6: Update session state =====
    extracted_question = rag_result.get('quick_check', '').strip()
    
    update_data = {
        "last_question": extracted_question,
        "emotion": emotion,
        "evaluation": evaluation_result,
        "teaching_mode": teaching_mode,
        "last_explanation": rag_result.get("explanation", ""),
        "last_interaction": datetime.now(),
        "conversation_state": "question_asked" if extracted_question else "idle"
    }
    
    # If user answered correctly, progress to next concept
    if evaluation_result == "correct":
        new_index = session.get("concept_index", 0) + 1
        concepts = session.get("concepts", [])
        
        if new_index < len(concepts):
            update_data["current_concept"] = concepts[new_index]
            update_data["concept_index"] = new_index
            update_data["attempt_count"] = 0
            print(f"[LEARN-REFACTORED] ✅ Moving to next concept: {concepts[new_index]}")
        else:
            update_data["status"] = "completed"
            print(f"[LEARN-REFACTORED] ✅ All concepts completed!")
    else:
        # Increment attempts if struggling
        if evaluation_result in ["incorrect", "partial"]:
            update_data["attempt_count"] = session.get("attempt_count", 0) + 1
    
    db["sessions"].update_one(
        {"session_id": request.session_id},
        {"$set": update_data}
    )
    
    # ===== STEP 7: Return response =====
    response_data = {
        "emotion": emotion,
        "evaluation": evaluation_result,
        "teaching_mode": teaching_mode,
        "explanation": rag_result.get("explanation", ""),
        "example": rag_result.get("example", ""),
        "question": extracted_question,
        "concept": current_topic,
        "concept_index": session.get("concept_index", 0),
        "concepts_total": len(session.get("concepts", [])),
        "session_id": request.session_id,
        "status": update_data.get("status", "active"),
        "ai_powered": rag_result.get("ai_powered", False)
    }
    
    print(f"[LEARN-REFACTORED] 🔥 Response ready - emotion={emotion}, eval={evaluation_result}, has_question={bool(extracted_question)}")
    return response_data


@router.post("/upload-content")
def upload_content(request):
    """Upload study material for a topic"""
    pass


@router.get("/history/{user_id}")
def get_learning_history(user_id: str):
    """Get user's learning history"""
    history = list(db["sessions"].find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("start_time", -1).limit(50))
    
    return {
        "user_id": user_id,
        "sessions": history,
        "count": len(history)
    }
