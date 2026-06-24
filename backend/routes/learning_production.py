"""
Production Learning Endpoint

Clean Tutoring Loop:
1. Student sends message
2. Detect emotion
3. Evaluate if answering a question
4. Generate lesson for current concept
5. Save updated session state
6. Return structured response

This endpoint uses generate_lesson() which handles:
- SYSTEM_PROMPT (fixed)
- Structured learning state (no chat history)
- Anti-repetition
- Emotional adaptation
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from backend.services.emotion import detect_emotion
from backend.services.ai_tutor_production import (
    generate_lesson, 
    evaluate_answer, 
    detect_intent, 
    is_overwhelmed, 
    update_teaching_mode,
    classify_student_response
)
from backend.db.mongo import db, get_status
from collections import defaultdict
from datetime import datetime, timezone
import time
import uuid
from bson import Binary

# Tutor Control & State Machine Imports
from backend.services.session_defaults import ensure_session_structure
from backend.services.session_service import get_session_history, save_message
from backend.services.tutor_control import (
    update_tutor_state,
    validate_response,
    update_analogy_tracking,
    deterministic_fallback_trim,
    SessionPhase,
    infer_level_from_onboarding
)
from backend.services.event_tracker import EventTracker
from backend.services.analytics_classifier import classify_message_background

router = APIRouter()

class LearningRequest(BaseModel):
    text: str
    user_id: str
    session_id: str


def determine_stable_level(current_level: str, text: str, evaluation: str, attempt_count: int, emotion: str, emotional_history: list = None) -> str:
    """
    Dynamically evaluate the student's learning level based on response quality,
    vocabulary complexity, and reasoning indicators.
    
    Returns: "beginner" | "intermediate" | "advanced"
    """
    if not text:
        return current_level or "intermediate"
        
    text_lower = text.lower()
    words = text_lower.split()
    word_count = len(words)
    
    # Calculate average word length as a proxy for vocabulary complexity
    avg_word_len = sum(len(w) for w in words) / max(word_count, 1)
    
    # Look for advanced reasoning/conceptual vocabulary
    reasoning_terms = ["because", "trained", "data", "pattern", "since", "algorithm", "learn", "predict", "model", "input"]
    reasoning_count = sum(1 for term in reasoning_terms if term in text_lower)
    
    # 1. Advanced level triggers:
    # - Good length (e.g., > 10 words) AND uses 2+ reasoning/conceptual terms AND correct evaluation.
    # - Or average word length is high (> 5.5 chars) and reasoning words present.
    is_advanced_vocab = avg_word_len > 5.5 and word_count >= 8
    is_advanced_reasoning = reasoning_count >= 2 and evaluation == "correct"
    
    # Check emotional history for consecutive confusion/frustration signals
    has_consecutive_emotion = False
    if emotional_history:
        if len(emotional_history) > 0:
            prev_emotion = emotional_history[-1]
            if prev_emotion == emotion and emotion in ["confused", "frustrated"]:
                has_consecutive_emotion = True
                
    # 2. Beginner level triggers:
    # - Short sentences (< 4 words), simple/empty responses, or multiple failed attempts (attempt_count >= 2)
    # - Or explicit confusion/frustration in TWO consecutive messages (requires at least 2 attempts so it doesn't drop on the first message)
    is_beginner_signals = word_count < 4 or attempt_count >= 2 or (has_consecutive_emotion and attempt_count >= 2)
    
    # Compute base decision
    if is_advanced_reasoning or (is_advanced_vocab and evaluation in ["correct", "partial"]):
        target_level = "advanced"
    elif is_beginner_signals:
        target_level = "beginner"
    else:
        target_level = "intermediate"
        
    # Smoothen transitions (don't jump directly from beginner to advanced or vice-versa without intermediate)
    if current_level == "beginner" and target_level == "advanced":
        return "intermediate"
    if current_level == "advanced" and target_level == "beginner":
        return "intermediate"
        
    return target_level


def get_state_update_fields(session: dict) -> dict:
    """Returns a dict of all persistent state machine fields to save to DB."""
    return {
        "tutor_state": session.get("tutor_state", "normal"),
        "level_change_cooldown": session.get("level_change_cooldown", 0),
        "sustained_emotional_history": session.get("sustained_emotional_history", []),
        "analogy_cooldown": session.get("analogy_cooldown", 0),
        "used_analogies": session.get("used_analogies", []),
    }


def generate_and_validate_lesson(
    session: dict,
    concept: str,
    emotion: str,
    evaluation_result: str,
    intent: str,
    classification: str,
    kwargs_for_lesson: dict
) -> tuple[str, dict]:
    """
    Orchestration layer combining the state machine, prompt construction, pre-flight validation,
    swift regeneration on failure, safe deterministic fallback trim, and analogy tracking.
    
    Returns:
        (final_text, updated_session)
    """
    # 1. Update State Machine
    session = update_tutor_state(
        session=session,
        user_input=kwargs_for_lesson.get("user_query", ""),
        emotion=emotion,
        evaluation=evaluation_result,
        classification=classification,
        intent=intent
    )
    tutor_state = session.get("tutor_state", "normal")
    
    # Inject tutor_state into generate_lesson arguments
    kwargs_for_lesson["tutor_state"] = tutor_state
    
    # Get session history for context
    session_history = get_session_history(session.get("session_id"), limit=6)
    
    # 2. Call generate_lesson
    lesson = generate_lesson(
        concept=concept,
        emotion=emotion,
        evaluation_result=evaluation_result,
        intent=intent,
        cognitive_load_score=session.get("cognitive_load_score", 1),
        classification=classification,
        session_history=session_history,
        **kwargs_for_lesson
    )
    response_text = lesson.get("response", "").strip()
    
    # 3. Pre-flight response validation
    is_valid, error_reason = validate_response(response_text, tutor_state, session)
    
    if not is_valid:
        print(f"[VALIDATION] Failed: {error_reason}. Triggering swift regeneration...")
        # Get sentence count rule limit
        from backend.services.tutor_control import RESPONSE_POLICIES
        max_sentences = RESPONSE_POLICIES[tutor_state]["max_sentences"]
        
        # Enforce strict correction instructions
        reg_prompt = (
            f"Your previous response failed validation with reason: {error_reason}. "
            f"Rewrite it perfectly now. You MUST answer the student's question directly in the very first sentence. "
            f"Do not start with greetings or filler like 'Great question!'. "
            f"You MUST write exactly or at most {max_sentences} sentences. "
            f"Do NOT use any analogies or metaphors."
        )
        
        # Make a copy and override user_query/guidance for regeneration
        reg_kwargs = kwargs_for_lesson.copy()
        reg_kwargs["user_query"] = reg_prompt
        
        lesson = generate_lesson(
            concept=concept,
            emotion=emotion,
            evaluation_result=evaluation_result,
            intent=intent,
            cognitive_load_score=session.get("cognitive_load_score", 1),
            classification=classification,
            session_history=session_history,
            **reg_kwargs
        )
        response_text = lesson.get("response", "").strip()
        
        # Second verification
        is_valid_again, error_reason_again = validate_response(response_text, tutor_state, session)
        if not is_valid_again:
            print(f"[VALIDATION] Regeneration failed: {error_reason_again}. Applying deterministic fallback trim.")
            response_text = deterministic_fallback_trim(response_text, tutor_state)
            
    # 4. Analogy Tracking update
    session = update_analogy_tracking(response_text, session)
    
    # ===== NEW: RESUMED SESSION BRIDGE DETECTOR =====
    if session.get("resumed_session_pending") is True:
        concepts = session.get("concepts", [])
        topic = concepts[0] if concepts else "this topic"
        current_concept = session.get("current_concept", "our lesson")
        resumed_bridge = f"Welcome back! Let's resume our lesson on {topic}. We were just looking at {current_concept}.\n\n"
        response_text = resumed_bridge + response_text
        session["resumed_session_pending"] = False
        print(f"[LEARN-PROD] Resumed session bridge prepended. Welcome back to {topic}!")
        
    save_message(session.get("session_id"), "ai", response_text, emotion)
    
    return response_text, session


def _learn_internal(request: LearningRequest):
    """
    Production tutoring loop - returns FLAT text response (not structured).
    
    Flow:
    0️⃣ Check for overwhelm/small input FIRST (earliest exit)
    1. Get session (concept tracking)
    2. Detect emotion
    3. Evaluate if answering
    4. Generate lesson for current concept
    5. Update session
    6. Return FLAT text response
    """
    
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    req_start = time.time()
    print(f"\n[LEARN-PROD] Request START: session={request.session_id}, user={request.user_id}")
    print(f"[LEARN-PROD] Text: {request.text[:60]}...")
    
    # Save student message to history
    save_message(request.session_id, "student", request.text)
    
    # ===== STEP 0: Get Session & Increment Turn Count =====
    db_start = time.time()
    session = db["sessions"].find_one({"session_id": request.session_id})
    db_time = time.time() - db_start
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # FIX: Increment turn_count immediately to guarantee single authoritative increment
    db["sessions"].update_one(
        {"session_id": request.session_id},
        {"$inc": {"turn_count": 1}}
    )
    session["turn_count"] = session.get("turn_count", 0) + 1
    
    # ===== STEP 0.5: Check for OVERWHELM FIRST =====
    # This must be BEFORE emotion detection, before anything else
    if is_overwhelmed(request.text):
        print(f"[LEARN-PROD] [ALARM] OVERWHELM DETECTED - Triggering confusion breaker")
        
        # Reset state with persistent TutorState elements
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": {
                "teaching_mode": "simplify",
                "attempt_count": 0,
                "conversation_state": "confusion_break",
                "last_interaction": datetime.now(),
                "stable_teaching_level": "beginner",
                "tutor_state": "recovery",
                "level_change_cooldown": 3,
                "cognitive_load_score": 5
            }}
        )
        
        # Return FLAT text response (not structured)
        concept_name = session.get('current_concept', 'this topic').split(':')[0]
        final_text = f"[STOP] Alright, too much. Let me simplify.\n\n{concept_name} — that's the main thing to focus on.\n\nLet's take a step back and go slower [OK]"
        
        save_message(request.session_id, "ai", final_text, "overwhelmed")
        
        return {
            "response": final_text,
            "text": final_text,
            "intent": "repair",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": "overwhelmed",
            "cognitive_load": 5,
            "cognitive_load_score": 5,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": "beginner",
            "evaluation": "overwhelmed"
        }
    
    # Issue 5: Reject messages if session status is completed
    if session.get("status") == "completed":
        return {
            "response": "🎉 You've completed all the concepts! Great work!",
            "text": "🎉 You've completed all the concepts! Great work!",
            "intent": "advance",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": "neutral",
            "cognitive_load": session.get("cognitive_load_score", 1),
            "cognitive_load_score": session.get("cognitive_load_score", 1),
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": "completed",
            "stable_teaching_level": session.get("stable_teaching_level", "intermediate"),
            "evaluation": None
        }
    
    if session.get("status") == "expired":
        msg = "Welcome back! Your previous session expired. Want to continue from where you left off, or start fresh?"
        return {
            "response": msg,
            "text": msg,
            "intent": "repair",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": "neutral",
            "cognitive_load": session.get("cognitive_load_score", 1),
            "cognitive_load_score": session.get("cognitive_load_score", 1),
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": "expired",
            "stable_teaching_level": session.get("stable_teaching_level", "intermediate"),
            "evaluation": None
        }
    
    session = ensure_session_structure(session)
    
    # ===== FIX: Update start_time and resumed_at if session is resumed on a different day =====
    from datetime import date as date_class
    today = date_class.today().isoformat()
    session_date = None
    
    if session.get("start_time"):
        try:
            start = session["start_time"]
            if isinstance(start, str):
                session_date = start.split('T')[0]
            else:
                session_date = start.date().isoformat()
        except:
            pass
    
    # If session is from a different day, update start_time and set resumed_at for correct duration calculation
    if session_date != today:
        print(f"[LEARN-PROD] [RESUME] Session from {session_date} resumed today ({today}). Updating start_time and setting resumed_at.")
        now = datetime.now()
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": {
                "start_time": now,  # For analytics streak tracking
                "resumed_at": now    # For accurate duration calculation (session.py will use this)
            }}
        )
        session["start_time"] = now
        session["resumed_at"] = now
    
    print(f"[LEARN-PROD] [DB] Session retrieval: {db_time:.3f}s")
    print(f"[LEARN-PROD] Concept: {session.get('current_concept')}")
    
    # ===== STEP 2: Detect Emotion =====
    emotion_start = time.time()
    emotion = detect_emotion(request.text)
    emotion_time = time.time() - emotion_start
    print(f"[LEARN-PROD] [EMOTION] Detection: {emotion_time:.3f}s → {emotion}")
    
    # Explicit Confusion Override (Pedagogical Rule 4)
    text_lower = request.text.lower()
    confusion_keywords = ["confused", "confusing", "lost", "don't get", "makes no sense", "stuck", "bro its confusingnow", "wth", "idk"]
    if any(keyword in text_lower for keyword in confusion_keywords):
        print(f"[LEARN-PROD] [OVERRIDE] Overriding emotion to 'confused' due to keyword match")
        emotion = "confused"

    # ===== NEW: ONBOARDING PHASE ROUTING INTERCEPTOR =====
    if session.get("session_phase") == SessionPhase.ONBOARDING.value:
        concepts = session.get("concepts", [])
        concept = session.get("current_concept", "Python Basics")
        
        if not session.get("onboarding_welcome_sent"):
            print("[LEARN-PROD] [ONBOARDING] Welcome not sent yet. Generating onboarding welcome.")
            # Call generate_lesson for onboarding
            lesson = generate_lesson(
                concept=concept,
                emotion=emotion,
                session_phase="ONBOARDING",
                concepts=concepts,
                user_query=request.text
            )
            final_text = lesson.get("response", "").strip()
            
            save_message(request.session_id, "ai", final_text, emotion)
            
            db["sessions"].update_one(
                {"session_id": request.session_id},
                {"$set": {
                    "onboarding_welcome_sent": True,
                    "last_question": "Prior experience query",
                    "last_substantive_message": {"text": final_text, "timestamp": datetime.now()},
                    "last_interaction": datetime.now()
                }}
            )
            
            return {
                "response": final_text,
                "text": final_text,
                "intent": "chitchat",
                "concept_index": 0,
                "concepts_total": len(concepts),
                "advance_curriculum": False,
                "emotion": emotion,
                "cognitive_load": 1,
                "cognitive_load_score": 1,
                "session_id": request.session_id,
                "concept": concept,
                "status": "active",
                "stable_teaching_level": session.get("stable_teaching_level", "intermediate"),
                "evaluation": None
            }
        else:
            print("[LEARN-PROD] [ONBOARDING] Welcome already sent. Processing diagnostic reply.")
            inferred_level = infer_level_from_onboarding(request.text)
            print(f"[LEARN-PROD] [ONBOARDING] Inferred student level: {inferred_level}")
            
            # Generate personalized concept path based on inferred level
            from backend.services.ai_tutor_production import generate_concepts
            concepts = generate_concepts(concept, student_level=inferred_level)
            
            # Transition to LEARNING phase
            session["stable_teaching_level"] = inferred_level
            session["session_phase"] = SessionPhase.LEARNING.value
            session["concepts"] = concepts
            session["concepts_generated"] = True
            session["concept_index"] = 0
            
            if concepts:
                first_concept = concepts[0]
            else:
                first_concept = concept
            session["current_concept"] = first_concept
            
            initial_depth = "foundational" if inferred_level in ["complete_beginner", "beginner"] else "intro"
            session["depth_level"] = initial_depth
            
            kwargs_for_lesson = {
                "teaching_mode": "teach_basic",
                "attempt_count": 0,
                "user_query": f"I told you about my prior experience: '{request.text}'. You inferred my level as {inferred_level}. Transition warmly by saying something like 'Got it! Since you are at a {inferred_level} level, let's start with our first concept: {first_concept}' and then teach that concept.",
                "explained_concepts": [],
                "avoid_list": [],
                "depth_level": initial_depth,
                "lesson_stage": "introduction",
                "last_success_moment": False,
                "question_type_override": None
            }
            
            final_text, session = generate_and_validate_lesson(
                session=session,
                concept=first_concept,
                emotion=emotion,
                evaluation_result=None,
                intent="advance",
                classification="demonstrated_reasoning",
                kwargs_for_lesson=kwargs_for_lesson
            )
            
            try:
                from backend.services.event_tracker import EventTracker
                EventTracker.track_concept_presented(request.session_id, request.user_id, first_concept)
            except Exception as e:
                print(f"[LEARN-PROD] Failed to track concept presented: {e}")
            
            # Try to extract a question sentence from final_text to keep last_question updated
            last_q = ""
            if "?" in final_text:
                from backend.services.tutor_control import split_into_sentences
                sentences = split_into_sentences(final_text)
                for s in reversed(sentences):
                    if "?" in s:
                        last_q = s
                        break
                        
            db["sessions"].update_one(
                {"session_id": request.session_id},
                {"$set": {
                    "session_phase": SessionPhase.LEARNING.value,
                    "stable_teaching_level": inferred_level,
                    "concept_index": 0,
                    "current_concept": first_concept,
                    "last_question": last_q,
                    "last_substantive_message": {"text": final_text, "timestamp": datetime.now()},
                    "last_interaction": datetime.now(),
                    **get_state_update_fields(session)
                }}
            )
            
            return {
                "response": final_text,
                "text": final_text,
                "intent": "advance",
                "concept_index": 0,
                "concepts_total": len(concepts),
                "advance_curriculum": True,
                "emotion": emotion,
                "cognitive_load": 1,
                "cognitive_load_score": 1,
                "session_id": request.session_id,
                "concept": first_concept,
                "status": "active",
                "stable_teaching_level": inferred_level,
                "evaluation": None
            }

    # ===== STEP 2.5: Classify Student Response & Initialize Cognitive Load =====
    current_concept = session.get("current_concept", "")
    last_question = session.get("last_question", "")
    classification = classify_student_response(request.text, current_concept, last_question)
    print(f"[LEARN-PROD] Student response classification: {classification}")
    
    cognitive_load_score = session.get("cognitive_load_score", 1)
    
    # Adapt cognitive load based on classification and emotion
    if classification == "confusion" or emotion == "confused":
        cognitive_load_score = min(5, cognitive_load_score + 2)
    elif emotion in ["frustrated", "very_frustrated"]:
        cognitive_load_score = min(5, cognitive_load_score + 2)
    print(f"[LEARN-PROD] Initial cognitive load score: {cognitive_load_score}")

    # ===== STEP 3: DETECT INTENT =====
    # CRITICAL: Do NOT inject previous responses - prevents context pollution
    intent_start = time.time()
    # Retrieve previous tutor message for context
    prev_ai_response = session.get('last_substantive_message', {}).get('text', '')
    intent = detect_intent(request.text, previous_ai_response=prev_ai_response, context=session)  # Context-aware intent detection
    intent_time = time.time() - intent_start
    print(f"[LEARN-PROD] [INTENT] Detection: {intent_time:.3f}s → {intent}")
    
    # Get current stable level and lists to update
    stable_teaching_level = session.get("stable_teaching_level", "intermediate")
    explained_concepts = session.get("explained_concepts", [])
    avoid_list = session.get("avoid_list", [])
    
    # ===== STEP 3b: HANDLE LOW-VALUE MESSAGES =====
    # SHORT_ACK messages DO NOT flow through learning pipeline
    # This prevents garbage analytics and state pollution
    if intent in ["SHORT_ACK", "acknowledgement"]:
        print(f"[LEARN-PROD] [SHORT_ACK] Low-value message - responding without session update")
        
        # Track low-value message (do NOT count toward analytics)
        EventTracker.track_low_value_message(
            session_id=request.session_id,
            user_id=request.user_id,
            message=request.text,
            emotion=emotion
        )
        
        # Simple acknowledgement without learning processing
        simple_ack_responses = [
            "Got it! Continue whenever you're ready.",
            "No problem! Let me know when you want to keep going.",
            "Ready when you are!",
            "Understood. What else would you like to learn?"
        ]
        
        import random
        simple_response = random.choice(simple_ack_responses)
        
        # IMPORTANT: Update LAST INTERACTION but NOT meaningful learning metrics
        update_fields = {
            "last_interaction": datetime.now(),
            "emotion": emotion
        }
        
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": update_fields}
        )
        
        return {
            "response": simple_response,
            "text": simple_response,
            "intent": "short_ack",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": cognitive_load_score,
            "cognitive_load_score": cognitive_load_score,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None,
            "note": "Low-value message - not counted in analytics"
        }
    
    # ===== STEP 4: Handle Based on Intent =====
    elif intent == "activity_switch":
        print(f"[LEARN-PROD] [ACTIVITY_SWITCH] Handling re-engagement")
        # Prepare kwargs for lesson generation with simplify mode and re-engage strategy
        kwargs_for_lesson = {
            "user_query": request.text,
            "explained_concepts": explained_concepts,
            "avoid_list": avoid_list,
            "depth_level": session.get("depth_level", "intro"),
            "lesson_stage": session.get("lesson_stage", "introduction"),
            "teaching_mode": "simplify",
            "lesson_strategy": "re_engage",
        }
        final_text, session = generate_and_validate_lesson(
            session=session,
            concept=session.get('current_concept', ''),
            emotion=emotion,
            evaluation_result=None,
            intent="activity_switch",
            classification="re_engage",
            kwargs_for_lesson=kwargs_for_lesson,
        )
        # Minimal session update, no mastery or attempt count changes
        last_substantive_message = {"text": final_text, "timestamp": datetime.now()}
        update_fields = {
            "emotion": emotion,
            "last_interaction": datetime.now(),
            "last_substantive_message": last_substantive_message,
            "cognitive_load_score": cognitive_load_score,
            **get_state_update_fields(session),
        }
        db["sessions"].update_one({"session_id": request.session_id}, {"$set": update_fields})
        return {
            "response": final_text,
            "text": final_text,
            "intent": "activity_switch",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": cognitive_load_score,
            "cognitive_load_score": cognitive_load_score,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None,
        }
    evaluation_result = None
    feedback_text = ""
    
    if intent == "refusal":
        print(f"[LEARN-PROD] [REFUSAL] Refusal intent detected - halting curriculum")
        
        # Track refusal event
        EventTracker.track_student_refusal(
            session_id=request.session_id,
            user_id=request.user_id,
            concept=session.get('current_concept', ''),
            emotion=emotion
        )
        
        kwargs_for_lesson = {
            "user_query": request.text,
            "explained_concepts": explained_concepts,
            "avoid_list": avoid_list,
            "depth_level": session.get("depth_level", "intro"),
            "lesson_stage": session.get("lesson_stage", "introduction"),
            "question_type_override": "none"
        }
        
        final_text, session = generate_and_validate_lesson(
            session=session,
            concept=session.get('current_concept', ''),
            emotion=emotion,
            evaluation_result=None,
            intent="refusal",
            classification="confusion",
            kwargs_for_lesson=kwargs_for_lesson
        )
        
        last_substantive_message = {
            "text": final_text,
            "timestamp": datetime.now()
        }
        
        update_fields = {
            "conversation_state": "idle",
            "emotion": emotion,
            "last_interaction": datetime.now(),
            "last_substantive_message": last_substantive_message,
            "cognitive_load_score": 5,
            **get_state_update_fields(session)
        }
        
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": update_fields}
        )
        
        return {
            "response": final_text,
            "text": final_text,
            "intent": "refusal",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": 5,
            "cognitive_load_score": 5,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None
        }
        
    elif intent == "repair":
        print(f"[LEARN-PROD] [REPAIR] Repair/Correction intent detected")
        
        kwargs_for_lesson = {
            "user_query": request.text,
            "explained_concepts": explained_concepts,
            "avoid_list": avoid_list,
            "depth_level": session.get("depth_level", "intro"),
            "lesson_stage": session.get("lesson_stage", "introduction")
        }
        
        final_text, session = generate_and_validate_lesson(
            session=session,
            concept=session.get('current_concept', ''),
            emotion=emotion,
            evaluation_result="partial",
            intent="repair",
            classification="partial_understanding",
            kwargs_for_lesson=kwargs_for_lesson
        )
        
        last_substantive_message = {
            "text": final_text,
            "timestamp": datetime.now()
        }
        
        update_fields = {
            "emotion": emotion,
            "last_interaction": datetime.now(),
            "last_substantive_message": last_substantive_message,
            "cognitive_load_score": cognitive_load_score,
            **get_state_update_fields(session)
        }
        
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": update_fields}
        )
        
        return {
            "response": final_text,
            "text": final_text,
            "intent": "repair",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": cognitive_load_score,
            "cognitive_load_score": cognitive_load_score,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None
        }
        
    elif intent == "chitchat":
        print(f"[LEARN-PROD] [CHITCHAT] Chitchat/Off-topic intent detected")
        
        kwargs_for_lesson = {
            "user_query": request.text,
            "explained_concepts": explained_concepts,
            "avoid_list": avoid_list,
            "depth_level": session.get("depth_level", "intro"),
            "lesson_stage": session.get("lesson_stage", "introduction"),
            "question_type_override": "none"
        }
        
        final_text, session = generate_and_validate_lesson(
            session=session,
            concept=session.get('current_concept', ''),
            emotion=emotion,
            evaluation_result=None,
            intent="chitchat",
            classification="general_remark",
            kwargs_for_lesson=kwargs_for_lesson
        )
        
        last_substantive_message = {
            "text": final_text,
            "timestamp": datetime.now()
        }
        
        update_fields = {
            "emotion": emotion,
            "last_interaction": datetime.now(),
            "last_substantive_message": last_substantive_message,
            "cognitive_load_score": cognitive_load_score,
            **get_state_update_fields(session)
        }
        
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": update_fields}
        )
        
        return {
            "response": final_text,
            "text": final_text,
            "intent": "chitchat",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": cognitive_load_score,
            "cognitive_load_score": cognitive_load_score,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None
        }
        
    elif intent == "expand":
        print(f"[LEARN-PROD] [EXPAND] Expand intent - deepening current concept")
        
        current_depth = session.get("depth_level", "intro")
        new_depth = "advanced" if current_depth == "intermediate" else "intermediate"
        
        stable_teaching_level = determine_stable_level(
            current_level=stable_teaching_level,
            text=request.text,
            evaluation="correct",
            attempt_count=session.get("attempt_count", 0),
            emotion=emotion
        )
        
        kwargs_for_lesson = {
            "depth_level": "advanced",
            "user_query": request.text,
            "explained_concepts": explained_concepts,
            "avoid_list": avoid_list,
            "lesson_stage": "expansion"
        }
        
        final_text, session = generate_and_validate_lesson(
            session=session,
            concept=session.get('current_concept', ''),
            emotion=emotion,
            evaluation_result="correct",
            intent="expand",
            classification=classification,
            kwargs_for_lesson=kwargs_for_lesson
        )
        
        last_substantive_message = {
            "text": final_text,
            "timestamp": datetime.now()
        }
        
        update_fields = {
            "depth_level": new_depth,
            "lesson_stage": "expansion",
            "last_response_mode": "expansion",
            "emotion": emotion,
            "last_interaction": datetime.now(),
            "stable_teaching_level": stable_teaching_level,
            "last_substantive_message": last_substantive_message,
            "avoid_list": avoid_list,
            "explained_concepts": explained_concepts,
            "cognitive_load_score": cognitive_load_score,
            **get_state_update_fields(session)
        }
        
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": update_fields}
        )
        
        return {
            "response": final_text,
            "text": final_text,
            "intent": "expand",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": cognitive_load_score,
            "cognitive_load_score": cognitive_load_score,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None
        }
    
    elif intent == "advance":
        print(f"[LEARN-PROD] [NEXT] Advance intent - moving to next concept")
        
        concepts = session.get("concepts", [])
        current_index = session.get("concept_index", 0)
        next_index = current_index + 1
        
        stable_teaching_level = determine_stable_level(
            current_level=stable_teaching_level,
            text=request.text,
            evaluation="correct",
            attempt_count=session.get("attempt_count", 0),
            emotion=emotion
        )
        
        if next_index < len(concepts):
            next_concept = concepts[next_index]
            print(f"[LEARN-PROD] Advancing to: {next_concept}")
            
            old_concept = session.get("current_concept")
            if old_concept not in explained_concepts:
                explained_concepts.append(old_concept)
            
            if any(k in old_concept.lower() for k in ["ai", "artificial intelligence", "introduction", "what is"]):
                for avoid_item in ["redefine_ai", "librarian_analogy", "chess_analogy"]:
                    if avoid_item not in avoid_list:
                        avoid_list.append(avoid_item)
            
            kwargs_for_lesson = {
                "user_query": request.text,
                "explained_concepts": explained_concepts,
                "avoid_list": avoid_list,
                "depth_level": "intro",
                "lesson_stage": "introduction",
                "last_success_moment": True,
                "question_type_override": "none"
            }
            
            session["concept_index"] = next_index
            session["current_concept"] = next_concept
            
            final_text, session = generate_and_validate_lesson(
                session=session,
                concept=next_concept,
                emotion=emotion,
                evaluation_result=None,
                intent="advance",
                classification=classification,
                kwargs_for_lesson=kwargs_for_lesson
            )
            
            try:
                from backend.services.event_tracker import EventTracker
                EventTracker.track_concept_presented(request.session_id, request.user_id, next_concept)
            except Exception as e:
                print(f"[LEARN-PROD] Failed to track concept presented: {e}")
            
            last_substantive_message = {
                "text": final_text,
                "timestamp": datetime.now()
            }
            
            update_fields = {
                "concept_index": next_index,
                "current_concept": next_concept,
                "explained_concepts": explained_concepts,
                "avoid_list": avoid_list,
                "depth_level": "intro",
                "lesson_stage": "introduction",
                "last_response_mode": "lesson",
                "attempt_count": 0,
                "emotion": emotion,
                "last_interaction": datetime.now(),
                "stable_teaching_level": stable_teaching_level,
                "last_substantive_message": last_substantive_message,
                "cognitive_load_score": cognitive_load_score,
                **get_state_update_fields(session)
            }
            
            db["sessions"].update_one(
                {"session_id": request.session_id},
                {"$set": update_fields}
            )
            
            return {
                "response": final_text,
                "text": final_text,
                "intent": "advance",
                "concept_index": next_index,
                "concepts_total": len(concepts),
                "advance_curriculum": True,
                "emotion": emotion,
                "cognitive_load": cognitive_load_score,
                "cognitive_load_score": cognitive_load_score,
                "session_id": request.session_id,
                "concept": next_concept,
                "status": session.get("status", "active"),
                "stable_teaching_level": stable_teaching_level,
                "evaluation": None
            }
        else:
            db["sessions"].update_one(
                {"session_id": request.session_id},
                {"$set": {
                    "status": "completed",
                    "stable_teaching_level": stable_teaching_level,
                    "last_interaction": datetime.now(),
                    **get_state_update_fields(session)
                }}
            )
            try:
                from backend.services.event_tracker import EventTracker
                EventTracker.track_session_completed(request.session_id, request.user_id, len(concepts))
            except Exception as e:
                print(f"[LEARN-PROD] Failed to track session completed: {e}")
            return {
                "response": "🎉 You've completed all the concepts! Great work!",
                "text": "🎉 You've completed all the concepts! Great work!",
                "intent": "advance",
                "concept_index": current_index,
                "concepts_total": len(concepts),
                "advance_curriculum": True,
                "emotion": emotion,
                "cognitive_load": cognitive_load_score,
                "cognitive_load_score": cognitive_load_score,
                "session_id": request.session_id,
                "concept": session.get("current_concept"),
                "status": "completed",
                "stable_teaching_level": stable_teaching_level,
                "evaluation": None
            }
    
    elif intent == "clarify":
        print(f"[LEARN-PROD] [CLARIFY] Clarify intent - providing clarification")
        
        stable_teaching_level = determine_stable_level(
            current_level=stable_teaching_level,
            text=request.text,
            evaluation="partial",
            attempt_count=session.get("attempt_count", 0),
            emotion=emotion
        )
        
        kwargs_for_lesson = {
            "attempt_count": 1,
            "user_query": request.text,
            "explained_concepts": explained_concepts,
            "avoid_list": avoid_list,
            "depth_level": session.get("depth_level", "intro"),
            "lesson_stage": "expansion"
        }
        
        final_text, session = generate_and_validate_lesson(
            session=session,
            concept=session.get('current_concept', ''),
            emotion=emotion,
            evaluation_result="partial",
            intent="clarify",
            classification=classification,
            kwargs_for_lesson=kwargs_for_lesson
        )
        
        last_substantive_message = {
            "text": final_text,
            "timestamp": datetime.now()
        }
        
        update_fields = {
            "last_response_mode": "clarification",
            "emotion": emotion,
            "last_interaction": datetime.now(),
            "stable_teaching_level": stable_teaching_level,
            "last_substantive_message": last_substantive_message,
            "avoid_list": avoid_list,
            "explained_concepts": explained_concepts,
            "cognitive_load_score": cognitive_load_score,
            **get_state_update_fields(session)
        }
        
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": update_fields}
        )
        
        return {
            "response": final_text,
            "text": final_text,
            "intent": "clarify",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": cognitive_load_score,
            "cognitive_load_score": cognitive_load_score,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None
        }
    
    elif intent == "ask_example":
        print(f"[LEARN-PROD] [ASK_EXAMPLE] Student requesting concrete example")
        
        # Track example request event
        EventTracker.track_example_requested(
            session_id=request.session_id,
            user_id=request.user_id,
            concept=session.get('current_concept', ''),
            emotion=emotion
        )
        
        feedback_text = "Perfect! Let me show you a concrete example."
        
        stable_teaching_level = determine_stable_level(
            current_level=stable_teaching_level,
            text=request.text,
            evaluation="correct",
            attempt_count=session.get("attempt_count", 0),
            emotion=emotion
        )
        
        kwargs_for_lesson = {
            "user_query": request.text,
            "explained_concepts": explained_concepts,
            "avoid_list": avoid_list,
            "depth_level": session.get("depth_level", "intro"),
            "lesson_stage": "example_requested",
            "question_type_override": "example"
        }
        
        final_text, session = generate_and_validate_lesson(
            session=session,
            concept=session.get('current_concept', ''),
            emotion=emotion,
            evaluation_result="example_requested",
            intent="ask_example",
            classification="request_for_example",
            kwargs_for_lesson=kwargs_for_lesson
        )
        
        last_substantive_message = {
            "text": final_text,
            "timestamp": datetime.now()
        }
        
        update_fields = {
            "emotion": emotion,
            "last_interaction": datetime.now(),
            "stable_teaching_level": stable_teaching_level,
            "last_substantive_message": last_substantive_message,
            "avoid_list": avoid_list,
            "explained_concepts": explained_concepts,
            "cognitive_load_score": cognitive_load_score,
            **get_state_update_fields(session)
        }
        
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": update_fields}
        )
        
        return {
            "response": final_text,
            "text": final_text,
            "intent": "ask_example",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": cognitive_load_score,
            "cognitive_load_score": cognitive_load_score,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None
        }
    
    elif intent == "ask_simplify":
        print(f"[LEARN-PROD] [ASK_SIMPLIFY] Student wants simpler explanation")
        
        # Track simplification request event
        EventTracker.track_simplification_requested(
            session_id=request.session_id,
            user_id=request.user_id,
            concept=session.get('current_concept', ''),
            emotion=emotion
        )
        
        feedback_text = "You're right, let me break this down more simply."
        evaluation_result = "needs_simplification"
        
    elif intent == "ask_concept":
        print(f"[LEARN-PROD] [QUESTION] Question detected - answering instead")
        
        stable_teaching_level = determine_stable_level(
            current_level=stable_teaching_level,
            text=request.text,
            evaluation="question",
            attempt_count=session.get("attempt_count", 0),
            emotion=emotion
        )
        
        kwargs_for_lesson = {
            "user_query": request.text,
            "explained_concepts": explained_concepts,
            "avoid_list": avoid_list,
            "depth_level": session.get("depth_level", "intro"),
            "lesson_stage": "expansion"
        }
        
        final_text, session = generate_and_validate_lesson(
            session=session,
            concept=session.get('current_concept', ''),
            emotion=emotion,
            evaluation_result="question",
            intent="ask_concept",
            classification=classification,
            kwargs_for_lesson=kwargs_for_lesson
        )
        
        last_substantive_message = {
            "text": final_text,
            "timestamp": datetime.now()
        }
        
        update_fields = {
            "emotion": emotion,
            "last_interaction": datetime.now(),
            "stable_teaching_level": stable_teaching_level,
            "last_substantive_message": last_substantive_message,
            "avoid_list": avoid_list,
            "explained_concepts": explained_concepts,
            "cognitive_load_score": cognitive_load_score,
            **get_state_update_fields(session)
        }
        
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": update_fields}
        )
        
        return {
            "response": final_text,
            "text": final_text,
            "intent": "ask_concept",
            "concept_index": session.get("concept_index", 0),
            "concepts_total": len(session.get("concepts", [])),
            "advance_curriculum": False,
            "emotion": emotion,
            "cognitive_load": cognitive_load_score,
            "cognitive_load_score": cognitive_load_score,
            "session_id": request.session_id,
            "concept": session.get("current_concept"),
            "status": session.get("status", "active"),
            "stable_teaching_level": stable_teaching_level,
            "evaluation": None
        }
    
    elif intent == "unknown":
        # Ambiguous message - treat as potential answer attempt
        print(f"[LEARN-PROD] [UNKNOWN] Ambiguous intent - treating as answer attempt")
        evaluation_result = "partial"
        
    elif intent == "confused":
        # User is confused → Simplify current concept
        print(f"[LEARN-PROD] [CONFUSED] Confusion detected - simplifying")
        
        # Track confusion spike event
        EventTracker.track_confusion_spike(
            session_id=request.session_id,
            user_id=request.user_id,
            concept=session.get('current_concept', ''),
            emotion=emotion
        )
        
        feedback_text = "I see! Let me explain this more simply."
        evaluation_result = "confused"  # Special: not wrong, just needs simpler explanation
        
    else:  # intent == "answer"
        # User is answering the previous question
        last_question = session.get("last_question", "")
        current_concept = session.get("current_concept", "")
        
        # Track student's answer attempt
        EventTracker.track_student_answered(
            session_id=request.session_id,
            user_id=request.user_id,
            concept=current_concept,
            answer_length=len(request.text),
            emotion=emotion
        )
        
        evaluation_result = evaluate_answer(request.text, last_question, current_concept)
        
        # Track answer evaluation event
        EventTracker.track_answer_evaluated(
            session_id=request.session_id,
            user_id=request.user_id,
            concept=current_concept,
            evaluation=evaluation_result,
            emotion=emotion,
            cognitive_load=cognitive_load_score,
            attempt_count=session.get("attempt_count", 0)
        )
        
        # DOWNGRADE SAFETY GATE: Prevent rewarding minimal acknowledgment as mastery
        if evaluation_result == "correct" and classification == "weak_ack":
            print(f"[LEARN-PROD] GATING: Student gave weak_ack ('{request.text}') to a question. Downgrading evaluation to 'partial' to verify reasoning.")
            evaluation_result = "partial"
            
        print(f"[LEARN-PROD] Answer evaluation: {evaluation_result}")
        
        # Adjust cognitive load based on evaluation
        if evaluation_result == "incorrect":
            cognitive_load_score = min(5, cognitive_load_score + 1)
        elif evaluation_result == "correct":
            if cognitive_load_score > 1 and classification in ["demonstrated_reasoning", "partial_understanding"]:
                cognitive_load_score = max(1, cognitive_load_score - 1)
        print(f"[LEARN-PROD] Adjusted cognitive load score: {cognitive_load_score}")
        
        # Determine updated stable teaching level based on answer
        stable_teaching_level = determine_stable_level(
            current_level=stable_teaching_level,
            text=request.text,
            evaluation=evaluation_result,
            attempt_count=session.get("attempt_count", 0),
            emotion=emotion
        )
        
        # Provide feedback based on evaluation
        if evaluation_result == "correct":
            feedback_text = "✅ Excellent! You understood that well."
        elif evaluation_result == "partial":
            feedback_text = "📌 You're on the right track! Let me refine this..."
        else:
            feedback_text = "❌ Not quite. Let me explain this differently..."
        
        # Handle concept progression
        if evaluation_result == "correct":
            try:
                from backend.services.event_tracker import EventTracker
                EventTracker.track_concept_mastered(request.session_id, request.user_id, current_concept, emotion)
            except Exception as e:
                print(f"[LEARN-PROD] Failed to track concept mastered: {e}")
                
            # Move to next concept
            new_index = session.get("concept_index", 0) + 1
            concepts = session.get("concepts", [])
            
            # Semantic avoid list update
            old_concept = session.get("current_concept", "")
            if old_concept not in explained_concepts:
                explained_concepts.append(old_concept)
            
            # Avoid updates
            if any(k in old_concept.lower() for k in ["ai", "artificial intelligence", "introduction", "what is"]):
                for avoid_item in ["redefine_ai", "librarian_analogy", "chess_analogy"]:
                    if avoid_item not in avoid_list:
                        avoid_list.append(avoid_item)
            
            # Siri/Alexa semantic avoid update
            ans_text = request.text.lower()
            last_q = last_question.lower()
            if "siri" in ans_text or "alexa" in ans_text or "siri" in last_q or "alexa" in last_q:
                for avoid_item in ["redefine_ai", "librarian_analogy", "chess_analogy"]:
                    if avoid_item not in avoid_list:
                        avoid_list.append(avoid_item)
            
            if new_index < len(concepts):
                new_concept = concepts[new_index]
                print(f"[LEARN-PROD] [OK] Moving to next concept: {new_concept}")
                
                db["sessions"].update_one(
                    {"session_id": request.session_id},
                    {"$set": {
                        "concept_index": new_index,
                        "current_concept": new_concept,
                        "attempt_count": 0,
                        "explained_concepts": explained_concepts,
                        "avoid_list": avoid_list,
                        "cognitive_load_score": cognitive_load_score
                    }}
                )
                session["concept_index"] = new_index
                session["current_concept"] = new_concept
                session["attempt_count"] = 0
            else:
                print(f"[LEARN-PROD] [OK] All concepts completed!")
                db["sessions"].update_one(
                    {"session_id": request.session_id},
                    {"$set": {
                        "status": "completed", 
                        "conversation_state": "idle",
                        "explained_concepts": explained_concepts,
                        "avoid_list": avoid_list,
                        "stable_teaching_level": stable_teaching_level,
                        "cognitive_load_score": cognitive_load_score
                    }}
                )
                try:
                    from backend.services.event_tracker import EventTracker
                    EventTracker.track_session_completed(request.session_id, request.user_id, len(concepts))
                except Exception as e:
                    print(f"[LEARN-PROD] Failed to track session completed: {e}")
                return {
                    "response": "🎉 You've completed all the concepts! Great work!",
                    "text": "🎉 You've completed all the concepts! Great work!",
                    "intent": "answer",
                    "concept_index": session.get("concept_index", 0),
                    "concepts_total": len(concepts),
                    "advance_curriculum": True,
                    "emotion": emotion,
                    "cognitive_load": cognitive_load_score,
                    "cognitive_load_score": cognitive_load_score,
                    "session_id": request.session_id,
                    "concept": session.get("current_concept"),
                    "status": "completed",
                    "stable_teaching_level": stable_teaching_level,
                    "evaluation": "correct"
                }
        else:
            # Stay on same concept, increment attempt
            attempt_count = session.get("attempt_count", 0) + 1
            db["sessions"].update_one(
                {"session_id": request.session_id},
                {"$set": {
                    "attempt_count": attempt_count,
                    "cognitive_load_score": cognitive_load_score
                }}
            )
            print(f"[LEARN-PROD] Attempt {attempt_count} on {session.get('current_concept')}")
            session["attempt_count"] = attempt_count
    
    # ===== STEP 4: Generate Lesson =====
    current_concept = session.get("current_concept", "")
    current_teaching_mode = session.get("teaching_mode", "teach_basic")
    attempt_count = session.get("attempt_count", 0)
    
    # Implement Mastery Skip logic: praise & transition directly without forced questions
    last_success_moment = False
    question_type_override = None
    if evaluation_result == "correct":
        last_success_moment = True
        question_type_override = "none"
        
    # TODO: FUTURE RAG INTEGRATION SKELETON
    # To ground tutoring lessons in student-uploaded study materials:
    # 1. Enable a RAG feature flag (e.g. ENABLE_RAG = True)
    # 2. Retrieve user content using the user_id and current_concept (or topic):
    #    from backend.services.rag import get_user_content, get_relevant_chunk
    #    content = get_user_content(request.user_id, current_concept)
    # 3. Find the most relevant chunk matching the student query:
    #    retrieved_chunk = get_relevant_chunk(request.text, content["chunks"]) if content else None
    # 4. Pass the retrieved chunk into kwargs_for_lesson (e.g. as "retrieved_context")
    # 5. In generate_lesson() (backend/services/ai_tutor_production.py), append the text to prompt context:
    #    if retrieved_context:
    #        context_parts.append("=== RETRIEVED STUDY MATERIAL ===")
    #        context_parts.append(retrieved_context)
        
    kwargs_for_lesson = {

        "teaching_mode": current_teaching_mode,
        "attempt_count": attempt_count,
        "user_query": request.text,
        "explained_concepts": explained_concepts,
        "avoid_list": avoid_list,
        "depth_level": session.get("depth_level", "intro"),
        "lesson_stage": session.get("lesson_stage", "introduction"),
        "last_success_moment": last_success_moment,
        "question_type_override": question_type_override
    }
    
    final_text, session = generate_and_validate_lesson(
        session=session,
        concept=current_concept,
        emotion=emotion,
        evaluation_result=evaluation_result,
        intent=intent,
        classification=classification,
        kwargs_for_lesson=kwargs_for_lesson
    )
    
    # ===== STEP 5: Update Session State with PROPER Mode Transitions =====
    # Get current understanding level (from emotion + evaluation)
    if emotion in ["confused", "frustrated", "very_frustrated"]:
        understanding = "low"
    elif evaluation_result == "correct":
        understanding = "high"
    elif evaluation_result == "partial":
        understanding = "medium"
    else:
        understanding = "low"
    # Use NEW smart teaching mode transition logic
    current_mode = session.get("teaching_mode", "teach_basic")
    new_mode = update_teaching_mode(
        current_mode=current_mode,
        understanding=understanding,
        emotion=emotion,
        evaluation=evaluation_result,
        attempt_count=session.get("attempt_count", 0)
    )
    
    print(f"[LEARN-PROD] Teaching mode transition: {current_mode} -> {new_mode} (understanding={understanding}, emotion={emotion})")
    
    # Try to extract a question sentence from final_text to keep last_question updated
    last_q = ""
    if "?" in final_text:
        from backend.services.tutor_control import split_into_sentences
        sentences = split_into_sentences(final_text)
        for s in reversed(sentences):
            if "?" in s:
                last_q = s
                break
                
    # ===== STEP 6: Return FLAT Text Response (NOT STRUCTURED) =====
    last_substantive_message = {
        "text": final_text,
        "timestamp": datetime.now()
    }
    
    update_data = {
        "last_question": last_q,
        "emotion": emotion,
        "evaluation": evaluation_result,
        "conversation_state": "question_asked" if last_q else "idle",
        "last_interaction": datetime.now(),
        "teaching_mode": new_mode,  # Use the smart transition
        "stable_teaching_level": stable_teaching_level,
        "last_substantive_message": last_substantive_message,
        "avoid_list": avoid_list,
        "explained_concepts": explained_concepts,
        "cognitive_load_score": cognitive_load_score,
        **get_state_update_fields(session)
    }
    
    db_update_start = time.time()
    db["sessions"].update_one(
        {"session_id": request.session_id},
        {"$set": update_data}
    )
    db_update_time = time.time() - db_update_start
    print(f"[LEARN-PROD] [DB] Session update: {db_update_time:.3f}s")
    
    total_time = time.time() - req_start
    print(f"[LEARN-PROD] [TOTAL] Request complete: {total_time:.3f}s")
    print(f"[LEARN-PROD] Response sending...")
    
    return {
        "response": final_text,
        "text": final_text,
        "intent": intent,
        "concept_index": session.get("concept_index", 0),
        "concepts_total": len(session.get("concepts", [])),
        "advance_curriculum": True if evaluation_result == "correct" else False,
        "emotion": emotion,
        "cognitive_load": cognitive_load_score,
        "cognitive_load_score": cognitive_load_score,
        "session_id": request.session_id,
        "concept": session.get("current_concept"),
        "status": session.get("status", "active"),
        "stable_teaching_level": stable_teaching_level,
        "evaluation": evaluation_result
    }

@router.post("/learn")
def learn(request: LearningRequest, background_tasks: BackgroundTasks):
    current_time = datetime.now(timezone.utc)
    
    # Get previous timestamp before the route processes
    session = db["sessions"].find_one({"session_id": request.session_id})
    prev_time = None
    if session and "last_interaction" in session:
        prev_time = session["last_interaction"]
        if prev_time.tzinfo is None:
            prev_time = prev_time.replace(tzinfo=timezone.utc)
            
    response = _learn_internal(request)
    
    tutor_reply = response.get("response", "") if isinstance(response, dict) else ""
    if tutor_reply:
        background_tasks.add_task(
            classify_message_background,
            user_msg=request.text,
            tutor_reply=tutor_reply,
            session_id=request.session_id,
            user_id=request.user_id,
            current_timestamp=current_time,
            prev_message_timestamp=prev_time
        )
        
    return response

@router.get("/history/{user_id}")
def get_learning_history(user_id: str):
    """Get all learning sessions for user"""
    sessions = list(db["sessions"].find(
        {"user_id": user_id},
        {"conversation_state": 0}  # Exclude this field
    ))
    
    for session in sessions:
        session["_id"] = str(session["_id"])
        if "start_time" in session:
            session["start_time"] = session["start_time"].isoformat()
        if "end_time" in session:
            session["end_time"] = session["end_time"].isoformat()
    
    return {"user_id": user_id, "sessions": sessions}


@router.post("/analyze")
def analyze_answer(request: LearningRequest):
    """Detailed analysis of student answer"""
    emotion = detect_emotion(request.text)
    
    # This would expand to include more detailed metrics
    return {
        "emotion": emotion,
        "length": len(request.text),
        "has_reasoning": len(request.text) > 20
    }


@router.get("/analytics")
def get_analytics(user_id: str):
    """
    Get learning analytics for a user - REBUILT FROM EVENTS.
    Uses EventAnalytics queries instead of counting raw messages.
    
    Returns:
        {
            "user_id": "...",
            "total_sessions": N,
            "meaningful_events": count,
            "answers_attempted": count,
            "answers_correct": count,
            "concepts_mastered": count,
            "confusion_spikes": count,
            "total_active_minutes": minutes,
            "engagement_score": 0-100,
            "ready_for_streak": bool,
            "learning_dates": [dates],
            "low_value_messages": count
        }
    """
    try:
        from backend.services.event_tracker import EventAnalytics
        from datetime import datetime, timedelta
        
        # Get all sessions for this user
        sessions = list(db["sessions"].find({"user_id": user_id}))
        
        if not sessions:
            return {
                "user_id": user_id,
                "total_sessions": 0,
                "meaningful_events": 0,
                "answers_attempted": 0,
                "answers_correct": 0,
                "concepts_mastered": 0,
                "confusion_spikes": 0,
                "total_active_minutes": 0,
                "engagement_score": 0,
                "ready_for_streak": False,
                "learning_dates": [],
                "low_value_messages": 0,
                "message": "No sessions found"
            }
        
        # Aggregate metrics across all sessions using EventAnalytics
        all_meaningful_events = 0
        all_answers_attempted = 0
        all_answers_correct = 0
        all_concepts_mastered = 0
        all_examples_requested = 0
        all_confusion_spikes = 0
        all_low_value_messages = 0
        total_active_minutes = 0
        learning_dates = set()
        
        for session in sessions:
            session_id = session.get("session_id")
            
            # Get clean metrics from events (NOT raw message counts)
            metrics = EventAnalytics.get_session_metrics(session_id)
            all_meaningful_events += metrics["total_meaningful_events"]
            all_answers_attempted += metrics["answers_attempted"]
            all_answers_correct += metrics["answers_correct"]
            all_concepts_mastered += metrics["concepts_mastered"]
            all_examples_requested += metrics["examples_requested"]
            all_confusion_spikes += metrics["confusion_spikes"]
            all_low_value_messages += metrics["low_value_messages"]
            
            # Get active study time (not idle time)
            session_active_minutes = EventAnalytics.get_study_time_minutes(session_id)
            total_active_minutes += session_active_minutes
            
            # Track learning dates from session start
            start_time = session.get("start_time")
            if start_time:
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                learning_dates.add(start_time.date().isoformat())
        
        # Calculate clean engagement score from meaningful events
        engagement_score = min(
            100,
            all_concepts_mastered * 0.5 +
            all_answers_correct * 0.3 +
            all_examples_requested * 0.2
        )
        
        # Check if user has earned a streak
        # Good streak condition: at least 10 meaningful active minutes and at least 1 concept mastered
        ready_for_streak = total_active_minutes >= 10 and all_concepts_mastered >= 1
        
        print(f"[ANALYTICS] User {user_id} - Events: {all_meaningful_events}, Mastered: {all_concepts_mastered}, Active time: {total_active_minutes}m, Ready for streak: {ready_for_streak}")
        
        return {
            "user_id": user_id,
            "total_sessions": len(sessions),
            "meaningful_events": all_meaningful_events,
            "answers_attempted": all_answers_attempted,
            "answers_correct": all_answers_correct,
            "concepts_mastered": all_concepts_mastered,
            "examples_requested": all_examples_requested,
            "confusion_spikes": all_confusion_spikes,
            "total_active_minutes": total_active_minutes,
            "engagement_score": round(engagement_score, 2),
            "ready_for_streak": ready_for_streak,
            "learning_dates": sorted(list(learning_dates)),
            "low_value_messages": all_low_value_messages,
            "db_status": get_status()
        }
        
    except Exception as e:
        print(f"[ANALYTICS] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "user_id": user_id,
            "total_sessions": 0,
            "meaningful_events": 0,
            "answers_attempted": 0,
            "answers_correct": 0,
            "concepts_mastered": 0,
            "confusion_spikes": 0,
            "total_active_minutes": 0,
            "engagement_score": 0,
            "ready_for_streak": False,
            "learning_dates": [],
            "low_value_messages": 0,
            "error": str(e),
            "db_status": get_status()
        }


# ==========================================
# ADDITIVE: STUDY MATERIAL MANAGEMENT ROUTES
# ==========================================

class ContentUploadRequest(BaseModel):
    user_id: str
    topic: str
    content: str


@router.post("/upload-content")
def upload_content(request: ContentUploadRequest):
    """
    Upload study material for a topic.
    Content is chunked and stored for RAG retrieval.
    Prevents duplicate topic files by overwriting any existing topic for the user.
    """
    if not request.content or len(request.content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    if not request.topic or len(request.topic.strip()) == 0:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
        
    try:
        from backend.services.rag import save_content
        
        # Clear existing topic content for this user to prevent duplicates
        topic_normalized = request.topic.lower() if request.topic else "general"
        db["content"].delete_many({
            "user_id": request.user_id,
            "topic": {"$regex": f"^{topic_normalized}$", "$options": "i"}
        })
        
        # Fix the parameter mismatch by using text=request.content
        result = save_content(
            user_id=request.user_id,
            topic=request.topic,
            text=request.content
        )
        return result
    except Exception as e:
        print(f"[UPLOAD] Error saving content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-pdf-notes")
async def upload_pdf_notes(user_id: str, topic: str, file: UploadFile = File(...)):
    """
    Upload a PDF file containing study notes.
    This is a future-scope placeholder for PDF-based RAG retrieval.
    """
    if file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail='Only PDF files are accepted')
    if not topic or len(topic.strip()) == 0:
        raise HTTPException(status_code=400, detail='Topic cannot be empty')

    pdf_data = await file.read()
    topic_normalized = topic.lower() if topic else 'general'

    try:
        db['content'].delete_many({
            'user_id': user_id,
            'topic': {'$regex': f'^{topic_normalized}$', '$options': 'i'}
        })

        doc = {
            'content_id': str(uuid.uuid4()),
            'user_id': user_id,
            'topic': topic_normalized,
            'chunks': [],
            'original_text': '',
            'chunk_count': 0,
            'pdf_file_name': file.filename,
            'pdf_content_type': file.content_type,
            'pdf_size': len(pdf_data),
            'pdf_bytes': Binary(pdf_data),
            'uploaded_at': datetime.now(timezone.utc).isoformat()
        }
        db['content'].insert_one(doc)
        return {
            'success': True,
            'content_id': doc['content_id'],
            'pdf_file_name': file.filename,
            'pdf_size': len(pdf_data),
            'topic_normalized': topic_normalized
        }
    except Exception as e:
        print(f"[UPLOAD-PDF] Error saving PDF content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/study-materials/{user_id}")
def get_study_materials(user_id: str):
    """
    Get uploaded study materials for a specific user.
    Returns list of topics, chunk counts, etc.
    """
    try:
        materials = list(db["content"].find({"user_id": user_id}, {"_id": 0, "original_text": 0, "chunks": 0}))
        
        formatted_materials = []
        for mat in materials:
            formatted_materials.append({
                "topic": mat.get("topic", "general"),
                "chunk_count": mat.get("chunk_count", 0),
                "content_id": mat.get("content_id", ""),
                "pdf_file_name": mat.get("pdf_file_name", None),
                "upload_date": datetime.now().isoformat()
            })

        return {"success": True, "materials": formatted_materials}
    except Exception as e:
        print(f"[MATERIALS] Error fetching content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete-content/{user_id}/{topic}")
def delete_study_material(user_id: str, topic: str):
    """
    Delete study material for a specific user and topic.
    """
    try:
        topic_normalized = topic.lower() if topic else "general"
        
        result = db["content"].delete_many({
            "user_id": user_id,
            "topic": {"$regex": f"^{topic_normalized}$", "$options": "i"}
        })
        
        if result.deleted_count > 0:
            return {"success": True, "message": f"Successfully deleted study material for '{topic}'"}
        else:
            result_fallback = db["content"].delete_many({
                "user_id": user_id,
                "topic": topic
            })
            if result_fallback.deleted_count > 0:
                return {"success": True, "message": f"Successfully deleted study material for '{topic}'"}
            
            raise HTTPException(status_code=404, detail=f"No study material found for topic '{topic}'")
    except Exception as e:
        print(f"[DELETE] Error deleting content: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

