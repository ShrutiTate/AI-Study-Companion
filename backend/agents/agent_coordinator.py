#agent_coordinator.py
"""
Agent Coordinator - Simplified to core functionality

Architecture:
User Message
     ↓
Emotion Detection
     ↓
Load History
     ↓
Tutor Agent
     ↓
Save to MongoDB
     ↓
Return response
"""

import re

from backend.services.emotion import get_emotion_with_confidence
from backend.services.ai_tutor_production import generate_lesson, detect_intent, update_teaching_mode
from backend.services.session_service import get_session_history, save_message
from backend.services.analytics_engine import analytics_engine
from backend.db.mongo import db
from datetime import datetime


def normalize_text(text: str) -> str:
    if not text:
        return ""
    try:
        return re.sub(r"[^\w\s]", "", text.lower()).strip()
    except Exception:
        return text.lower().strip() if isinstance(text, str) else ""


def save_last_ai(session, response_text: str):
    """Persist the last AI response and a normalized copy to the session doc.

    `session` may be a session document (dict) or a session_id (str).
    This helper swallows all exceptions to ensure it never raises.
    """
    if not response_text:
        return
    try:
        normalized = normalize_text(response_text)
        update = {
            "last_ai_message": response_text,
            "last_ai_message_norm": normalized,
            "last_interaction": datetime.utcnow()
        }

        # Accept either a full session doc or a session_id string
        if isinstance(session, dict) and session.get("_id"):
            db["sessions"].update_one({"_id": session["_id"]}, {"$set": update})
        elif isinstance(session, str):
            # assume session is session_id
            db["sessions"].update_one({"session_id": session}, {"$set": update})
        else:
            # best-effort: try session_id key
            sid = session.get("session_id") if isinstance(session, dict) else None
            if sid:
                db["sessions"].update_one({"session_id": sid}, {"$set": update})
    except Exception:
        # Never raise from this helper
        return


def extract_question_entity(question_text: str) -> str:
    """
    Extract the target concept from a direct concept question.
    
    Returns None if the question is not a direct concept question.
    
    Examples:
        "What is ATP?" → "ATP"
        "Define photosynthesis" → "photosynthesis"
        "How does mitosis work?" → "mitosis"
        "Tell me about neurons" → "neurons"
        "What does ATP do?" → "ATP"
    """
    text = question_text.strip()
    
    # Pattern 1: "What is X?" or "What are X?" (most common)
    match = re.search(r'(?:what|What)\s+(?:is|are)\s+(?:a\s+)?([a-zA-Z0-9\s\-]+)\?', text)
    if match:
        return match.group(1).strip()
    
    # Pattern 2: "Define X" or "Define X."
    match = re.search(r'(?:define|Define)\s+([a-zA-Z0-9\s\-]+)\.?$', text)
    if match:
        return match.group(1).strip()
    
    # Pattern 3: "Explain X" (not "Explain how...")
    if 'explain' in text.lower() and 'how' not in text.lower():
        match = re.search(r'(?:explain|Explain)\s+([a-zA-Z0-9\s\-]+)\.?$', text)
        if match:
            return match.group(1).strip()
    
    # Pattern 4: "Tell me about X"
    match = re.search(r'(?:tell|Tell)\s+(?:me\s+)?(?:about|About)\s+([a-zA-Z0-9\s\-]+)\.?$', text)
    if match:
        return match.group(1).strip()
    
    # Pattern 5: "What does X mean?" or "What does X do?"
    match = re.search(r'(?:what|What)\s+(?:does|do)\s+(?:a\s+)?([a-zA-Z0-9\s\-]+)\s+(?:mean|do)\?', text)
    if match:
        return match.group(1).strip()
    
    return None


# DELETED: blend_lesson_components function
# Phase 1 cleanup: No longer needed since generate_lesson() returns natural text in "response" field


def get_session_state(session_id: str, session_data: dict = None) -> dict:
    """
    Extract tutoring state from session.
    Falls back to defaults if session_id not available.
    
    Returns:
        {
            "current_concept": "...",
            "turn_count": int,
            "struggle_count": int,
            "teaching_mode": "normal|simplified|...",
            "evaluation": None or "correct|partial|incorrect",
            "last_strategy": None or strategy name,
            "stable_teaching_level": "beginner|intermediate|advanced",
            "stable_level_confidence": float 0.0-1.0,
            "level_change_cooldown": int,
            "concept_mastery": dict,
            "last_substantive_message": dict or None,
            "concepts": [],  # For curriculum progression
            "concept_index": int,  # For tracking position
            "explained_concepts": [],  # Already-taught concepts
            "depth_level": str  # Current depth for this concept
        }
    """
    if not session_data:
        return {
            "current_concept": None,
            "turn_count": 0,
            "struggle_count": 0,
            "teaching_mode": "normal",
            "evaluation": None,
            "last_strategy": None,
            "stable_teaching_level": "intermediate",
            "stable_level_confidence": 0.5,
            "level_change_cooldown": 0,
            "concept_mastery": {},
            "last_substantive_message": None,
            "concepts": [],
            "concept_index": 0,
            "explained_concepts": [],
            "depth_level": "intro"
        }
    
    state = {
        "current_concept": session_data.get("current_concept"),
        "turn_count": session_data.get("turn_count", 0),
        "struggle_count": session_data.get("struggle_count", 0),
        "teaching_mode": session_data.get("teaching_mode", "normal"),
        "evaluation": session_data.get("evaluation"),
        "last_strategy": session_data.get("last_explanation_type"),
        "stable_teaching_level": session_data.get("stable_teaching_level", "intermediate"),
        "stable_level_confidence": session_data.get("stable_level_confidence", 0.5),
        "level_change_cooldown": session_data.get("level_change_cooldown", 0),
        "concept_mastery": session_data.get("concept_mastery", {}),
        "last_substantive_message": session_data.get("last_substantive_message"),
        "concepts": session_data.get("concepts", []),  # NEW: Curriculum progression
        "concept_index": session_data.get("concept_index", 0),  # NEW: Current position
        "explained_concepts": session_data.get("explained_concepts", []),  # NEW: Already taught
        "depth_level": session_data.get("depth_level", "intro")  # NEW: Current depth
    }
    
    print(f"[SESSION_STATE] Loaded: concept={state['current_concept']}, "
          f"turn_count={state['turn_count']}, struggle_count={state['struggle_count']}, mode={state['teaching_mode']}, "
          f"stable_level={state['stable_teaching_level']}, eval={state['evaluation']}")
    
    return state


def calculate_new_stable_level(
    current_level: str,
    current_stable_confidence: float,
    message_understanding: str,
    concept_mastery: dict,
    emotion: str,
    struggle_count: int,
    cooldown_remaining: int,
    consecutive_struggles: int = 0,
    emotional_history: list = None,
    concept_index: int = 0
) -> tuple:
    """
    Calculate new stable teaching level with damping/hysteresis.
    
    PRINCIPLE: Stable level only changes when confident and sustained,
    preventing oscillation between beginner↔intermediate↔advanced.
    
    Downgrade requires 2+ consecutive confused/frustrated signals.
    Enforces minimum 5-message cooldown after any level change.
    
    Returns: (new_level, new_confidence, new_cooldown)
    """
    # If in cooldown, don't change
    if cooldown_remaining > 0:
        print(f"[STABLE_LEVEL] In cooldown for {cooldown_remaining} more messages, level={current_level}")
        return (current_level, current_stable_confidence, cooldown_remaining - 1)
    
    # Calculate average mastery across all concepts
    avg_mastery = sum(concept_mastery.values()) / len(concept_mastery) if concept_mastery else 0.5
    
    # Determine candidate level based on mastery + signals
    candidate_level = current_level
    
    # Positive Acceleration (engaged streak)
    engaged_streak = False
    if emotional_history and len(emotional_history) >= 3:
        engaged_streak = all(e in ["engaged", "very_engaged"] for e in emotional_history[-3:])
        
    if avg_mastery < 0.25:
        # candidate is beginner
        if current_level != "beginner":
            if consecutive_struggles >= 2:
                candidate_level = "beginner"
        else:
            candidate_level = "beginner"
    elif avg_mastery < 0.55:
        # candidate is intermediate
        if current_level == "advanced":
            if consecutive_struggles >= 2:
                candidate_level = "intermediate"
        elif current_level in ["beginner", "complete_beginner", "pending"]:
            # If already beginner/pending and mastery is low, do NOT bump to intermediate!
            candidate_level = current_level
        else:
            candidate_level = "intermediate"
    elif avg_mastery >= 0.75:
        # Only go to advanced if:
        # - High mastery (>= 0.75)
        # - AND at least 2 struggle_count/attempts (to prove consistency)
        # - AND positive emotion
        if struggle_count >= 2 and emotion in ["engaged", "very_engaged"]:
            candidate_level = "advanced"
        else:
            candidate_level = "intermediate"
            
    # TIER 1: Emotional overrides
    if emotion in ["frustrated", "very_frustrated"]:
        if current_level != "beginner":
            if consecutive_struggles >= 2:
                candidate_level = "beginner"
                
    # POSITIVE ACCELERATION: Upgrade from beginner if high mastery + engaged streak (not on concept 0)
    if engaged_streak and avg_mastery > 0.55 and concept_index > 0:
        if current_level in ["beginner", "complete_beginner"]:
            candidate_level = "intermediate"
            print(f"[STABLE_LEVEL] Positive Acceleration triggered: upgrading from {current_level} to intermediate")
    
    # Only change if different
    if candidate_level != current_level:
        # Decaying stable_level_confidence on level change
        new_confidence = max(0.5, current_stable_confidence - 0.2)
        
        # Calculate dynamic cooldown based on signal strength
        frustration_streak = emotional_history and len(emotional_history) >= 2 and all(e in ["frustrated", "very_frustrated"] for e in emotional_history[-2:])
        if engaged_streak or frustration_streak:
            new_cooldown = 1  # Strong signal
        elif emotion in ["engaged", "very_engaged", "frustrated", "very_frustrated"] or consecutive_struggles >= 2:
            new_cooldown = 2  # Weak signal
        else:
            new_cooldown = 3  # Neutral transition
            
        print(f"[STABLE_LEVEL] [CHANGE] {current_level} -> {candidate_level} (confidence={new_confidence:.2f}, consecutive_struggles={consecutive_struggles}, new_cooldown={new_cooldown})")
        return (candidate_level, new_confidence, new_cooldown)
    else:
        print(f"[STABLE_LEVEL] [OK] Level stable: {current_level} (mastery={avg_mastery:.2f}, confidence={current_stable_confidence:.2f})")
        return (current_level, current_stable_confidence, 0)


def update_concept_mastery_score(
    concept_mastery: dict,
    concept: str,
    evaluation: str,
    emotion: str,
    message: str,
    struggle_count: int,
    intent: str = "unknown"
) -> dict:
    """
    Lightweight heuristic update to concept mastery (NOT ML).
    
    Score range: 0.0 (no mastery) to 1.0 (complete mastery)
    """
    # Issue 1: Skip mastery scoring on specific intents or message conditions
    skip_intents = ["SHORT_ACK", "negative_confirmation", "emotional_outburst", "off_topic"]
    message_words = message.strip().split()
    
    if intent in skip_intents:
        print(f"[MASTERY] Skipping update for concept '{concept}' due to intent '{intent}'")
        return concept_mastery
        
    if len(message_words) <= 3 and emotion in ["neutral", "frustrated"]:
        print(f"[MASTERY] Skipping update for concept '{concept}' because message length <= 3 and emotion is '{emotion}'")
        return concept_mastery
        
    allowed_intents = ["answer", "ask_concept", "ask_example", "positive_confirmation",
                        "confused", "ask_simplify", "negative_confirmation", "repair"]
    if intent not in allowed_intents and emotion not in ["frustrated", "very_frustrated"]:
        print(f"[MASTERY] Skipping update for concept '{concept}' because intent '{intent}' is not in allowed intents and emotion is not frustrated")
        return concept_mastery
        
    if intent == "positive_confirmation" and len(message_words) <= 3:
        print(f"[MASTERY] Skipping update for concept '{concept}' because positive_confirmation message is <= 3 words")
        return concept_mastery

    current_score = concept_mastery.get(concept, 0.5)
    
    # Decay old score slightly (allows recovery)
    new_score = current_score * 0.92
    
    # Signal-based adjustments
    if evaluation == "correct":
        boost = 0.3 if struggle_count == 0 else 0.15
        new_score += boost
        print(f"[MASTERY] {concept}: +{boost} (correct, struggle_count={struggle_count})")
    elif evaluation == "partial":
        new_score += 0.10
        print(f"[MASTERY] {concept}: +0.10 (partial)")
    elif evaluation == "incorrect":
        new_score -= 0.20
        print(f"[MASTERY] {concept}: -0.20 (incorrect)")
    
    # Emotion signals
    if emotion in ["engaged", "very_engaged"]:
        new_score += 0.10
        print(f"[MASTERY] {concept}: +0.10 (engaged emotion)")
    elif emotion == "confused":
        if evaluation in ["correct", "partial"]:
            print(f"[MASTERY] {concept}: -0.00 (confused emotion but answer was {evaluation})")
        else:
            new_score -= 0.15
            print(f"[MASTERY] {concept}: -0.15 (confused emotion)")
    elif emotion in ["frustrated", "very_frustrated"]:
        new_score -= 0.20
        print(f"[MASTERY] {concept}: -0.20 (frustrated emotion)")
    
    # Intent-based struggle signals
    if intent == "ask_simplify":
        new_score -= 0.10
        print(f"[MASTERY] {concept}: -0.10 (ask_simplify intent)")
    elif intent == "repair":
        new_score -= 0.10
        print(f"[MASTERY] {concept}: -0.10 (repair intent)")
    elif intent == "negative_confirmation":
        new_score -= 0.10
        print(f"[MASTERY] {concept}: -0.10 (negative_confirmation intent)")
    
    # High confidence language signals
    confidence_markers = ["absolutely", "definitely", "clearly", "obviously", "certainly", "sure"]
    if any(marker in message.lower() for marker in confidence_markers):
        new_score += 0.10
        print(f"[MASTERY] {concept}: +0.10 (confident language)")
    
    # Clamp to 0.0-1.0
    new_score = max(0.0, min(1.0, new_score))
    
    print(f"[MASTERY] {concept}: {current_score:.2f} -> {new_score:.2f}")
    
    concept_mastery[concept] = new_score
    return concept_mastery


def update_session_state(session_id: str, lesson: dict, emotion: str, understanding: str, evaluation: str = None, session_state: dict = None):
    """
    Update session document with new tutoring state after generating response.
    """
    try:
        if not session_id:
            print(f"[SESSION_UPDATE] No session_id, skipping state update")
            return
        
        # Step 1: Get current session to preserve existing values
        session_doc = db["sessions"].find_one({"session_id": session_id})
        if not session_doc:
            print(f"[SESSION_UPDATE] [WARN] Session not found: {session_id}")
            return
        
        # Step 2: Prepare update fields
        update_fields = {}
        
        # 2a: Store the strategy used (for anti-repetition next time)
        strategy_used = lesson.get("strategy_used")
        if strategy_used:
            update_fields["last_explanation_type"] = strategy_used
            print(f"[SESSION_UPDATE] Stored strategy: {strategy_used}")
            
        # 2a.1: Update sustained emotional history (Critical fix for /chat route)
        emotional_history = session_doc.get("sustained_emotional_history", [])
        if emotion:
            emotional_history.append(emotion)
            if len(emotional_history) > 5:
                emotional_history = emotional_history[-5:]
            update_fields["sustained_emotional_history"] = emotional_history
            print(f"[SESSION_UPDATE] Appended emotion '{emotion}' to history: {emotional_history}")
        
        # 2b: Increment struggle_count on struggle attempts
        # (turn_count is now incremented immediately upon session load to catch early returns)
        current_struggle_count = session_doc.get("struggle_count", 0)
        
        if understanding in ["low", "none"] or evaluation in ["incorrect", "struggling"] or emotion in ["frustrated", "very_frustrated", "confused"] or intent_from_session in ["confused", "ask_simplify"]:
            update_fields["struggle_count"] = current_struggle_count + 1
        elif evaluation in ["correct", "partial"]:
            update_fields["struggle_count"] = 0
            update_fields["consecutive_empathy_responses"] = 0
        
        # 2c: Update teaching_mode with cooldown and consecutive struggles check
        current_mode = session_doc.get("teaching_mode", "normal")
        mode_change_cooldown_remaining = session_doc.get("mode_change_cooldown", 0)
        
        # Update consecutive struggles count
        consecutive_struggles = session_doc.get("consecutive_struggles", 0)
        
        # A struggle is an incorrect answer OR an explicit signal of confusion/frustration
        is_struggle = (intent_from_session == "answer" and evaluation == "incorrect") or emotion in ["frustrated", "very_frustrated", "confused"] or intent_from_session in ["confused", "ask_simplify"]
        is_success = evaluation in ["correct", "partial"]
        
        if is_struggle:
            consecutive_struggles += 1
        elif is_success:
            consecutive_struggles = 0
        # If it's neutral (e.g. asking a question, chatting), we just leave consecutive_struggles as is rather than resetting it.
        update_fields["consecutive_struggles"] = consecutive_struggles
        
        if mode_change_cooldown_remaining > 0:
            new_mode = current_mode
            update_fields["mode_change_cooldown"] = mode_change_cooldown_remaining - 1
            print(f"[SESSION_UPDATE] Mode change is in cooldown for {mode_change_cooldown_remaining} more messages. Mode={current_mode}")
        else:
            candidate_mode = update_teaching_mode(
                current_mode=current_mode,
                understanding=understanding,
                emotion=emotion,
                evaluation=evaluation,
                attempt_count=update_fields.get("struggle_count", current_struggle_count)
            )
            
            if current_mode == "teach_basic" and candidate_mode == "simplify":
                if consecutive_struggles >= 2:
                    new_mode = "simplify"
                else:
                    new_mode = current_mode
            else:
                new_mode = candidate_mode
                
            if new_mode != current_mode:
                update_fields["teaching_mode"] = new_mode
                update_fields["mode_change_cooldown"] = 3  # Set cooldown to 3 messages
                print(f"[SESSION_UPDATE] Teaching mode changed: {current_mode} -> {new_mode}. Cooldown set to 3.")
        
        # 2d: Store evaluation if provided
        if evaluation:
            update_fields["evaluation"] = evaluation
            print(f"[SESSION_UPDATE] Evaluation: {evaluation}")
        
        # ===== NEW: STABLE LEVEL CALCULATION (prevents oscillation) =====
        if session_state:
            concept_to_teach = session_state.get("current_concept")
            
            # Update concept mastery (lightweight heuristic)
            concept_mastery = session_state.get("concept_mastery", {})
            if concept_to_teach:
                concept_mastery = update_concept_mastery_score(
                    concept_mastery=concept_mastery,
                    concept=concept_to_teach,
                    evaluation=evaluation,
                    emotion=emotion,
                    message=session_state.get("last_message", ""),
                    struggle_count=update_fields.get("struggle_count", current_struggle_count),
                    intent=session_state.get("intent", "unknown")
                )
                update_fields["concept_mastery"] = concept_mastery
                
                # Update depth_level based on mastery
                current_depth = session_doc.get("depth_level", "intro")
                concept_score = concept_mastery.get(concept_to_teach, 0.5)
                
                # Map mastery to candidate depth levels
                if concept_score >= 0.85:
                    candidate_depth = "advanced"
                elif concept_score >= 0.60:
                    candidate_depth = "intermediate"
                elif concept_score >= 0.35:
                    candidate_depth = "basic"
                else:
                    candidate_depth = "intro"
                    
                # Allow depth to increase on mastery, but also downgrade on struggle
                depth_order = ["intro", "basic", "intermediate", "advanced"]
                try:
                    current_depth_idx = depth_order.index(current_depth)
                    candidate_depth_idx = depth_order.index(candidate_depth)
                    
                    if candidate_depth_idx > current_depth_idx:
                        update_fields["depth_level"] = candidate_depth
                        update_fields["depth_advances"] = session_doc.get("depth_advances", 0) + 1
                        print(f"[SESSION_UPDATE] Depth level increased: {current_depth} -> {candidate_depth} (mastery={concept_score:.2f})")
                    elif candidate_depth_idx < current_depth_idx:
                        # Allow downgrade if they are explicitly struggling or mastery tanked
                        if emotion in ["frustrated", "very_frustrated"] or session_state.get("intent") in ["ask_simplify", "confused"] or concept_score < 0.4:
                            update_fields["depth_level"] = candidate_depth
                            update_fields["depth_drops"] = session_doc.get("depth_drops", 0) + 1
                            print(f"[SESSION_UPDATE] Depth level DROPPED: {current_depth} -> {candidate_depth} (emotion={emotion}, score={concept_score:.2f})")
                            
                            # T4: Reset attempt_count on drop
                            level_drop_magnitude = current_depth_idx - candidate_depth_idx
                            if level_drop_magnitude >= 2 or emotion in ["frustrated", "very_frustrated"] or session_state.get("intent") == "confused":
                                update_fields["attempt_count"] = 0
                                print(f"[SESSION_UPDATE] Attempt count reset to 0 due to depth level drop")
                except ValueError:
                    pass
            
            # Calculate new stable teaching level (with damping)
            current_stable_level = session_doc.get("stable_teaching_level", "intermediate")
            if current_stable_level == "pending" and session_state:
                from backend.services.tutor_control import infer_level_from_onboarding
                current_stable_level = infer_level_from_onboarding(session_state.get("last_message", ""))
                update_fields["stable_teaching_level"] = current_stable_level
                print(f"[SESSION_UPDATE] Resolved pending onboarding level to: {current_stable_level}")
                
            current_stable_confidence = session_doc.get("stable_level_confidence", 0.5)
            cooldown_remaining = session_doc.get("level_change_cooldown", 0)
            
            new_stable_level, new_confidence, new_cooldown = calculate_new_stable_level(
                current_level=current_stable_level,
                current_stable_confidence=current_stable_confidence,
                message_understanding=understanding,
                concept_mastery=concept_mastery,
                emotion=emotion,
                struggle_count=update_fields.get("struggle_count", current_struggle_count),
                cooldown_remaining=cooldown_remaining,
                consecutive_struggles=consecutive_struggles,
                emotional_history=session_doc.get("sustained_emotional_history", []),
                concept_index=session_doc.get("concept_index", 0)
            )
            
            if new_stable_level != current_stable_level:
                update_fields["stable_teaching_level"] = new_stable_level
                update_fields["stable_level_confidence"] = new_confidence
                update_fields["level_change_cooldown"] = new_cooldown
                print(f"[SESSION_UPDATE] Stable level changed: {current_stable_level} -> {new_stable_level}")
                
                # Check for acceleration event
                if current_stable_level in ["beginner", "complete_beginner"] and new_stable_level == "intermediate":
                    if session_doc.get("sustained_emotional_history", [])[-1:] in [["engaged"], ["very_engaged"]]:
                        update_fields["acceleration_events"] = session_doc.get("acceleration_events", 0) + 1
        
        # Issue 3: Populate explained_concepts
        teaching_mode = lesson.get("teaching_mode") or update_fields.get("teaching_mode") or session_doc.get("teaching_mode", "normal")
        current_concept = session_state.get("current_concept") if session_state else session_doc.get("current_concept")
        response_generated = bool(lesson.get("response"))
        if teaching_mode in ["teach_basic", "simplify"] and response_generated and current_concept:
            explained_concepts = session_doc.get("explained_concepts", [])
            if current_concept not in explained_concepts:
                explained_concepts.append(current_concept)
                update_fields["explained_concepts"] = explained_concepts
                print(f"[SESSION_UPDATE] Added {current_concept} to explained_concepts: {explained_concepts}")
        
        # 2e: Save last substantive message for context (skip for acknowledgements)
        intent_from_student = session_state.get("intent", "unknown") if session_state else "unknown"
        if intent_from_student not in ["acknowledgement", "chat", "unknown"]:
            ai_response = lesson.get("response", "")
            update_fields["last_substantive_message"] = {
                "text": ai_response[:500],
                "intent": intent_from_student,
                "concept": session_state.get("current_concept") if session_state else None
            }
            print(f"[SESSION_UPDATE] Updated last_substantive_message: {intent_from_student}")
            print(f"[SESSION_UPDATE]   → AI response saved: {ai_response[:80]}...")
            
            # Issue 4: Fix substantive message extraction / unknown fallback
            user_message = session_state.get("last_message", "") if session_state else ""
            if not ai_response or ai_response.lower().strip() == "unknown":
                if user_message and len(user_message.strip()) > 8:
                    update_fields["last_substantive_message"]["text"] = user_message.strip()
                    print(f"[SESSION_UPDATE] Fallback applied for last_substantive_message using student message")
        
        # Step 3: Apply updates to MongoDB
        if update_fields:
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$set": update_fields}
            )
            print(f"[SESSION_UPDATE] [OK] Updated session with: {list(update_fields.keys())}")
        else:
            print(f"[SESSION_UPDATE] No changes needed")
    
    except Exception as e:
        print(f"[SESSION_UPDATE] [ERROR] Error updating session: {e}")
        import traceback
        traceback.print_exc()


def enforce_emotion_constraints(response: str, emotion: str, message: str = "") -> str:
    """
    DEPRECATED: This was post-processing guard for simple pipeline.
    
    With generate_lesson(), emotion constraints are handled in LLM SYSTEM_PROMPT.
    This function is kept for backward compatibility but is now a no-op.
    """
    # Just return response unchanged - generate_lesson() already handles emotion
    return response.strip() if response else ""


# ============================================
# INTENT-BASED HANDLERS (for lightweight responses)
# ============================================

def handle_acknowledgement(topic: str, message: str, emotion: str) -> dict:
    """
    Handle short acknowledgements: "ok", "yes", "good", "thanks", etc.
    
    Returns lightweight response instead of full lesson.
    Preserves context for next substantive message.
    """
    acknowledgements = {
        "ok": "Got it! 👍 Ready to continue?",
        "yes": "Great! Shall we move forward?",
        "good": "Perfect! Let me explain the next part.",
        "thanks": "Happy to help! Any questions so far?",
        "makes sense": "Excellent! You've got the idea.",
        "got it": "Awesome! Shall we dive deeper?",
        "understood": "Wonderful! Keep going?",
        "clear": "Glad that's clear! Ready for more?",
    }
    
    text_lower = message.lower().strip()
    
    # Find matching acknowledgement
    for key, response in acknowledgements.items():
        if key in text_lower or text_lower in key:
            return {
                "emotion": emotion,
                "understanding": "high",
                "confidence": 0.95,
                "response": response,
                "status": "success",
                "adaptation_applied": {
                    "intent": "acknowledgement",
                    "handled_as": "lightweight_response"
                }
            }
    
    # Fallback
    return {
        "emotion": emotion,
        "understanding": "high",
        "confidence": 0.9,
        "response": "Thanks for that! Ready to continue learning?",
        "status": "success",
        "adaptation_applied": {
            "intent": "acknowledgement",
            "handled_as": "lightweight_response"
        }
    }


def handle_chat_greeting(topic: str, message: str) -> dict:
    """
    Handle chat/greetings: "hi", "hello", "how are you?", etc.
    
    Just greet and introduce topic, don't start teaching yet.
    """
    return {
        "emotion": "neutral",
        "understanding": "medium",
        "confidence": 0.8,
        "response": f"Hi there! 👋 Today we're learning about {topic}. What would you like to know?",
        "status": "success",
        "adaptation_applied": {
            "intent": "chat",
            "handled_as": "greeting_only"
        }
    }


def handle_confused_intent(topic: str, message: str, emotion: str, session_state: dict, 
                          teaching_mode: str = None) -> dict:
    """
    Handle explicit confusion intent.
    Calls generate_lesson() with forced simplified mode.
    """
    print(f"[INTENT] Handling confused intent with message: {message[:60]}...")
    
    lesson = generate_lesson(
        concept=session_state.get("current_concept", topic),
        emotion=emotion,
        evaluation_result="incorrect",
        style="teacher",
        attempt_count=session_state.get("attempt_count", 0) + 1,
        intent="confused",
        last_explanation_type=session_state.get("last_strategy"),
        teaching_mode="simplify"
    )
    
    reply = lesson.get("response", f"I understand you're confused. Let me simplify {topic}.")
    
    return {
        "emotion": emotion,
        "understanding": "low",
        "confidence": 0.7,
        "response": reply,
        "status": "success",
        "adaptation_applied": {
            "intent": "confused",
            "strategy_used": lesson.get("strategy_used")
        }
    }, lesson


# ============================================
# PROGRESSION HANDLERS (Topic Advancement)
# ============================================

def handle_expand_intent(topic: str, message: str, emotion: str, session_state: dict, session_id: str = None):
    """
    Handle EXPAND intent - deepen current concept without advancing.
    """
    print(f"[PROGRESSION] [EXPAND] Expand intent - deepening current concept")
    
    current_concept = session_state.get("current_concept", topic)
    current_depth = session_state.get("depth_level", "intro")
    new_depth = "advanced" if current_depth == "intermediate" else "intermediate"
    
    lesson = generate_lesson(
        concept=current_concept,
        emotion=emotion,
        evaluation_result="correct",
        style="teacher",
        attempt_count=min(session_state.get("attempt_count", 0), 2),
        intent="expand",
        last_explanation_type=session_state.get("last_strategy"),
        teaching_mode="advanced"
    )
    
    if session_id:
        try:
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$set": {
                    "depth_level": new_depth,
                    "lesson_stage": "expansion",
                    "emotion": emotion,
                    "last_interaction": datetime.now() if 'datetime' in dir() else None
                }}
            )
            print(f"[PROGRESSION] Updated depth_level: {current_depth} -> {new_depth}")
        except Exception as e:
            print(f"[PROGRESSION] Error updating session: {e}")
    
    reply = lesson.get("response", f"Let me go deeper into {current_concept}.")
    
    return {
        "emotion": emotion,
        "understanding": "high",
        "confidence": 0.85,
        "response": reply,
        "status": "success",
        "adaptation_applied": {
            "intent": "expand",
            "depth_level": new_depth,
            "strategy_used": lesson.get("strategy_used")
        }
    }, lesson
    final_text = final_text.strip()
    
    return {
        "emotion": emotion,
        "understanding": "high",
        "confidence": 0.85,
        "response": final_text,
        "status": "success",
        "adaptation_applied": {
            "intent": "expand",
            "depth_level": new_depth,
            "strategy_used": lesson.get("strategy_used")
        }
    }, lesson


def handle_advance_intent(topic: str, message: str, emotion: str, session_state: dict, session_id: str = None):
    """
    Handle ADVANCE intent - move to next concept in curriculum.
    """
    print(f"[PROGRESSION] [NEXT] Advance intent - moving to next concept")
    
    concepts = session_state.get("concepts", [])
    current_index = session_state.get("concept_index", 0)
    current_concept = session_state.get("current_concept", "")
    next_index = current_index + 1
    
    if next_index < len(concepts):
        next_concept = concepts[next_index]
        print(f"[PROGRESSION] Advancing: {current_concept} -> {next_concept}")
        
        explained_concepts = session_state.get("explained_concepts", [])
        if current_concept and current_concept not in explained_concepts:
            explained_concepts.append(current_concept)
        
        if session_id:
            try:
                db["sessions"].update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "concept_index": next_index,
                        "current_concept": next_concept,
                        "explained_concepts": explained_concepts,
                        "depth_level": "intro",
                        "lesson_stage": "introduction",
                        "attempt_count": 0,
                        "emotion": emotion,
                        "last_interaction": datetime.now() if 'datetime' in dir() else None
                    }}
                )
                print(f"[PROGRESSION] Session updated: concept_index={next_index}")
            except Exception as e:
                print(f"[PROGRESSION] Error updating session: {e}")
        
        lesson = generate_lesson(
            concept=next_concept,
            emotion=emotion,
            evaluation_result=None,
            style="teacher",
            attempt_count=0,
            intent="answer",
            last_explanation_type=None,
            teaching_mode="normal"
        )
        
        reply = lesson.get("response", f"Great! Let's explore {next_concept}.")
        
        return {
            "emotion": emotion,
            "understanding": "medium",
            "confidence": 0.8,
            "response": reply,
            "status": "success",
            "adaptation_applied": {
                "intent": "advance",
                "previous_concept": current_concept,
                "new_concept": next_concept,
                "concept_index": next_index,
                "strategy_used": lesson.get("strategy_used")
            }
        }, lesson
    else:
        return {
            "emotion": emotion,
            "understanding": "high",
            "confidence": 0.95,
            "response": "🎉 You've completed all the concepts! Great work!",
            "status": "completed",
            "adaptation_applied": {
                "intent": "advance",
                "result": "curriculum_complete"
            }
        }, {"strategy_used": "completion"}


def handle_clarify_intent(topic: str, message: str, emotion: str, session_state: dict, session_id: str = None):
    """
    Handle CLARIFY intent - provide focused clarification.
    """
    print(f"[PROGRESSION] [IDEA] Clarify intent - providing clarification")
    
    current_concept = session_state.get("current_concept", topic)
    
    if session_id:
        try:
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$set": {
                    "emotion": emotion,
                    "last_interaction": datetime.now() if 'datetime' in dir() else None
                }}
            )
        except Exception as e:
            print(f"[PROGRESSION] Error updating session: {e}")
    
    lesson = generate_lesson(
        concept=current_concept,
        emotion=emotion,
        evaluation_result="partial",
        style="teacher",
        attempt_count=1,
        intent="clarify",
        last_explanation_type=session_state.get("last_strategy"),
        teaching_mode="ultra_simple",
        explained_concepts=session_state.get("explained_concepts", []),
        depth_level=session_state.get("depth_level"),
        lesson_stage=session_state.get("lesson_stage")
    )
    
    reply = lesson.get("response", f"Let me clarify {current_concept}.")
    
    return {
        "emotion": emotion,
        "understanding": "medium",
        "confidence": 0.75,
        "response": reply,
        "status": "success",
        "adaptation_applied": {
            "intent": "clarify",
            "concept": current_concept,
            "strategy_used": lesson.get("strategy_used")
        }
    }, lesson


# ============================================
# LIGHTWEIGHT RESPONSE GENERATORS (Conversational Modes)
# ============================================

def is_clarification_request(message: str, session_state: dict) -> bool:
    """
    Detect if student is asking clarification on a specific term.
    
    Examples:
    - "narrow what?" (clarifying previous mention)
    - "What does neural mean?"
    - "Clarify photosynthesis"
    """
    text = message.lower().strip()
    
    # Pattern: starts with "what"
    if text.startswith("what"):
        return True
    
    # Pattern: "X what?" - asking what a mentioned term means
    if text.endswith("what?") or text == "what?":
        return True
    
    # Pattern: "clarify X"
    if text.startswith("clarify"):
        return True
    
    # Pattern: very short question (likely clarification on a term)
    if len(text.split()) <= 3 and "?" in text:
        return True
    
    return False


def is_partial_answer(message: str, session_state: dict) -> bool:
    """
    Detect if student answered part of question correctly (not fully).
    
    Examples:
    - "mitochondria gives energy" (partial, missing ATP conversion detail)
    - "photosynthesis uses sunlight" (partial, missing water + CO2)
    """
    text = message.lower().strip()
    
    # Too short to be a real answer
    word_count = len(text.split())
    if word_count < 3:
        return False
    
    # Too long - probably a full answer or explanation
    if word_count > 20:
        return False
    
    # Partial answer signals
    partial_signals = [
        "mitochondria",
        "energy",
        "sunlight",
        "food",
        "nucleus",
        "plant",
        "animal",
        "cell",
        "enzyme",
        "protein"
    ]
    
    # If they mentioned a biological term, it's likely a partial answer
    has_bio_term = any(signal in text for signal in partial_signals)
    if has_bio_term and 3 <= word_count <= 20:
        return True
    
    return False


def is_expansion_request(message: str) -> bool:
    """
    Detect if student wants deeper/more advanced explanation.
    
    Examples:
    - "Tell me more"
    - "Go deeper"
    - "How does it work in detail?"
    """
    text = message.lower().strip()
    
    expansion_patterns = [
        "tell me more",
        "go deeper",
        "advanced",
        "more details",
        "how does",
        "how exactly",
        "elaborate",
        "explain more",
        "more about",
        "deeper"
    ]
    
    return any(pattern in text for pattern in expansion_patterns)


def generate_clarification_response(term: str, context: str = "", emotion: str = "neutral") -> str:
    """
    Generate brief clarification (1-2 sentences, not a full lesson).
    
    Uses LLM but with constraint to keep response SHORT.
    """
    print(f"[MODE] Generating clarification for '{term}'...")
    
    try:
        from backend.services.ai_tutor_production import client
        
        prompt = f"""Briefly explain what "{term}" means in the context of {context}.
Keep it to 1-2 sentences, simple and direct.
Do NOT provide a full lesson or examples.

Answer:"""
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=50
        )
        result = response.choices[0].message.content.strip()
        print(f"[CLARIFY] Generated: {result[:80]}...")
        return result
    except Exception as e:
        print(f"[CLARIFY] Error: {e}, using fallback")
        return f"'{term}' refers to a specific part of {context}. Would you like me to explain it more?"


def generate_encouragement_response(student_answer: str, concept: str, emotion: str = "neutral") -> str:
    """
    Validate correct parts and gently refine incorrect parts.
    
    Examples:
    Student: "mitochondria makes energy"
    Tutor: "Great start! Mitochondria converts food into ATP, which cells use for energy."
    """
    print(f"[MODE] Generating encouragement response...")
    
    try:
        from backend.services.ai_tutor_production import client
        
        prompt = f"""Student said: "{student_answer}"
Topic: {concept}

Respond in EXACTLY 1-2 sentences. Stop after 2 sentences maximum.
Format: Start with validation, then add one refinement.

Example:
Student: "mitochondria gives energy"
Response: "Exactly right! Mitochondria produces ATP, the cell's energy currency."

Your response (max 2 sentences, no more):"""
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=60  # Reduced further to force brevity
        )
        result = response.choices[0].message.content.strip()
        
        # Post-process: ensure max 2 sentences
        sentences = result.split('.')
        if len(sentences) > 3:  # More than 2 sentences (accounts for trailing empty)
            result = '.'.join(sentences[:2]) + '.'
        
        print(f"[ENCOURAGE] Generated: {result[:100]}...")
        return result
    except Exception as e:
        print(f"[ENCOURAGE] Error: {e}, using fallback")
        return f"Good thinking! You've got the key idea. Let me add one more detail: [concept] is actually..."


def select_response_mode(intent: str, message: str, session_state: dict, emotion: str, concept: str) -> tuple:
    """
    Determine which response mode to use based on intent and message context.
    
    Returns: (response_mode, should_call_generate_lesson)
    
    Response modes:
    - "acknowledge": Brief confirmation (already handled)
    - "chat": Greeting (already handled)
    - "clarify": Answer specific term clarification
    - "encourage": Validate partial answer
    - "expand": Deepen understanding (call generate_lesson with advanced mode)
    - "explain": Normal full lesson
    """
    text = message.lower().strip()
    
    # Already handled by specialized handlers above, shouldn't reach here
    if intent in ["acknowledgement", "chat"]:
        return (intent, False)
    
    # Progressive learning intents - NEW EXPLICIT HANDLERS
    if intent == "advance":
        print(f"[COORDINATOR] [NEXT] Advance intent detected: moving to next topic")
        return ("advance", True)
    
    if intent == "expand":
        print(f"[COORDINATOR] [EXPAND] Expand intent detected: deepening current topic")
        return ("expand", True)
    
    if intent == "clarify":
        print(f"[COORDINATOR] [CLARIFY] Clarify intent detected: answering specific term")
        return ("clarify", False)
    
    # Mode: CLARIFY - asking what a term means
    if intent == "question" and is_clarification_request(message, session_state):
        print(f"[COORDINATOR] [CLARIFY] Detected clarification request: {text[:40]}...")
        return ("clarify", False)  # Don't call generate_lesson
    
    # Mode: ENCOURAGE - partial correct answer
    if intent == "answer" and is_partial_answer(message, session_state):
        print(f"[COORDINATOR] [OK] Detected partial answer: {text[:40]}...")
        return ("encourage", False)  # Don't call generate_lesson
    
    # Mode: EXPAND - asking for deeper explanation
    if is_expansion_request(message):
        print(f"[COORDINATOR] [EXPAND] Detected expansion request: {text[:40]}...")
        return ("expand", True)  # Call generate_lesson with advanced mode
    
    # Mode: SIMPLIFY - confused (already routed earlier, but fallback)
    if intent == "confused":
        return ("simplify", True)
    
    # Mode: EXPLAIN - normal learning request
    # This is the default for genuine questions and answers
    print(f"[COORDINATOR] [EXPLAIN] Standard explain mode")
    return ("explain", True)

def process_learning_message(topic, message, session_id=None, teaching_mode=None):
    """
    SIMPLIFIED Phase 1 - Thin orchestration, strong LLM.
    """
    
    try:
        # Step 1: Detect emotion
        emotion_data = get_emotion_with_confidence(message)
        emotion = emotion_data["emotion"]
        understanding = emotion_data.get("understanding", "medium")
        confidence = emotion_data.get("confidence", 0.75)
        
        print(f"[COORDINATOR] Message: {message[:60]}...")
        print(f"[COORDINATOR] Emotion: {emotion}")
        
        # Step 2: Load session state
        session_state = {}
        session_doc = None
        if session_id:
            session_doc = db["sessions"].find_one({"session_id": session_id})
            
            # FIX: Increment turn_count immediately to guarantee single authoritative increment
            # regardless of downstream routing or early returns.
            if session_doc:
                db["sessions"].update_one(
                    {"session_id": session_id},
                    {"$inc": {"turn_count": 1}}
                )
                session_doc["turn_count"] = session_doc.get("turn_count", 0) + 1
            
            # Issue 5: Reject messages if session is already completed
            if session_doc and session_doc.get("status") == "completed":
                print(f"[COORDINATOR] Session {session_id} is already completed, rejecting message")
                return {
                    "emotion": "neutral",
                    "understanding": "high",
                    "confidence": 1.0,
                    "response": "🎉 You've completed all the concepts! Great work!",
                    "status": "completed",
                    "adaptation_applied": {
                        "intent": "unknown",
                        "handled_as": "session_completed"
                    }
                }
            
            if session_doc and session_doc.get("status") == "expired":
                print(f"[COORDINATOR] Session {session_id} is expired, requesting resume or restart")
                return {
                    "emotion": "neutral",
                    "understanding": "high",
                    "confidence": 1.0,
                    "response": "Welcome back! Your previous session expired. Want to continue from where you left off, or start fresh?",
                    "status": "expired",
                    "adaptation_applied": {
                        "intent": "unknown",
                        "handled_as": "session_expired"
                    }
                }
            
            session_state = get_session_state(session_id, session_doc)
        else:
            session_state = get_session_state(None)
        
        # Fix 2: Acknowledgement fast-path
        import string
        clean_msg = message.lower().translate(str.maketrans('', '', string.punctuation)).strip()
        filler_list = ["ohhh", "ok", "okay", "cool", "got it", "sure", "nice", "wow"]
        words = clean_msg.split()
        if len(words) <= 2 and (clean_msg in filler_list or any(w in filler_list for w in words)):
            fast_reply = "Got it! Do you have any questions or should we move on?"
            if session_id:
                save_message(session_id, "student", message)
                save_message(session_id, "ai", fast_reply, emotion=emotion)
                try:
                    save_last_ai(session_doc if session_doc else session_id, fast_reply)
                    db["sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {"last_interaction": datetime.utcnow()}}
                    )
                except Exception:
                    pass
            return {
                "emotion": emotion,
                "understanding": "medium",
                "confidence": 0.9,
                "response": fast_reply,
                "status": "success",
                "adaptation_applied": {
                    "intent": "fast_ack",
                    "handled_as": "fast_path_acknowledgement"
                }
            }

        # Step 3: Detect intent
        prev_ai_response = session_state.get("last_substantive_message", "")
        if isinstance(prev_ai_response, dict):
            prev_ai_response = prev_ai_response.get("text", "")

        intent = detect_intent(message, previous_ai_response=prev_ai_response)
        
        # Fix 1: Intent mapping and catch-all
        intent_map = {
            "curious": "ask_concept"
        }
        if intent in intent_map:
            intent = intent_map[intent]
            
        known_intents = [
            "confused", "ask_example", "ask_simplify", "refusal", "repair",
            "ask_concept", "expand", "advance", "chitchat", "answer",
            "skip_request", "activity_switch", "acknowledgement",
            "positive_confirmation", "negative_confirmation", "SHORT_ACK"
        ]
        
        if intent not in known_intents:
            intent = "ask_concept"
            
        print(f"[COORDINATOR] Intent: {intent} (context-aware)")

        # Issue 10: SHORT_ACK pre-check in coordinator
        if intent == "SHORT_ACK" and emotion in ["neutral", "engaged", "very_engaged"]:
            lightweight_reply = "Got it! Want me to continue, or do you have a question?"
            
            # Save messages
            if session_id:
                save_message(session_id, "student", message)
                save_message(session_id, "ai", lightweight_reply, emotion=emotion)
                try:
                    save_last_ai(session_doc if session_doc else session_id, lightweight_reply)
                    db["sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {"last_interaction": datetime.utcnow()}}
                    )
                except Exception:
                    pass
                    
            return {
                "emotion": emotion,
                "understanding": "medium",
                "confidence": 0.9,
                "response": lightweight_reply,
                "status": "success",
                "adaptation_applied": {
                    "intent": "SHORT_ACK",
                    "handled_as": "lightweight_continuation"
                }
            }

        # Issue 11: Empathy layer before re-teaching on negative messages
        is_negative_intent = intent in ["negative_confirmation", "refusal", "repair", "confused", "unknown"] or \
                             message.lower() in ["shutup", "stop", "please dont", "leave me alone", "don't explain", "no", "not interested"]
                             
        if emotion in ["frustrated", "very_frustrated"] and is_negative_intent:
            consecutive_empathy = session_doc.get("consecutive_empathy_count", 0) if session_doc else 0
            
            # Increment tracking counters
            consecutive_empathy += 1
            update_fields = {"consecutive_empathy_count": consecutive_empathy}
            
            if consecutive_empathy >= 2:
                current_struggle = session_doc.get("struggle_count", 0) if session_doc else 0
                update_fields["struggle_count"] = current_struggle + 1
                session_state["struggle_count"] = current_struggle + 1
            
            if session_id:
                db["sessions"].update_one(
                    {"session_id": session_id},
                    {"$set": update_fields}
                )
            
            from backend.services.ai_tutor_production import generate_empathy_response
            empathy_reply = generate_empathy_response(message, emotion, consecutive_empathy)
            
            # Save messages & update last interaction but skip mastery/mode changes
            if session_id:
                save_message(session_id, "student", message)
                save_message(session_id, "ai", empathy_reply, emotion=emotion)
                try:
                    save_last_ai(session_doc if session_doc else session_id, empathy_reply)
                    
                    db["sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "last_interaction": datetime.utcnow(),
                            "emotion": emotion
                        }}
                    )
                except Exception:
                    pass
                    
            return {
                "emotion": emotion,
                "understanding": "low",
                "confidence": 0.5,
                "response": empathy_reply,
                "status": "success",
                "adaptation_applied": {
                    "intent": intent,
                    "handled_as": "empathy_acknowledgement"
                }
            }

        # Step 4: If the student means advance, update the concept index and move on.
        if intent == "advance" and session_id:
            concepts = session_state.get("concepts", [])
            current_index = session_state.get("concept_index", 0)
            next_index = current_index + 1
            if next_index < len(concepts):
                next_concept = concepts[next_index]
                explained_concepts = session_state.get("explained_concepts", []) or []
                current_concept = session_state.get("current_concept")
                if current_concept and current_concept not in explained_concepts:
                    explained_concepts.append(current_concept)
                try:
                    db["sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "concept_index": next_index,
                            "current_concept": next_concept,
                            "explained_concepts": explained_concepts,
                            "depth_level": "intro",
                            "turn_count": 0, # Reset on topic advance
                            "struggle_count": 0,
                            "consecutive_empathy_responses": 0,
                            "emotion": emotion,
                            "last_interaction": datetime.utcnow()
                        }}
                    )
                    print(f"[COORDINATOR] [ADVANCE] Session updated: concept_index={next_index}")
                    session_state["current_concept"] = next_concept
                    session_state["concept_index"] = next_index
                    session_state["explained_concepts"] = explained_concepts
                except Exception as e:
                    print(f"[COORDINATOR] [ADVANCE] Error updating session: {e}")
            else:
                print(f"[COORDINATOR] [ADVANCE] No next concept, staying on current concept")

        # Step 5: For all other intents, call generate_lesson and trust it
        concept_to_teach = session_state.get("current_concept", topic)
        
        # Reset consecutive empathy on positive re-engagement
        if session_id and intent not in ["negative_confirmation", "refusal", "repair", "unknown"]:
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$set": {"consecutive_empathy_count": 0}}
            )
            session_state["consecutive_empathy_count"] = 0
            
        # Struggle Escalation System
        struggle_count = session_state.get("struggle_count", 0)
        escalation_mode = None
        
        if struggle_count >= 5:
            from backend.services.ai_tutor_production import generate_escalation_response
            escalation_text = generate_escalation_response(concept_to_teach, emotion)
            
            if session_id:
                save_message(session_id, "student", message)
                save_message(session_id, "ai", escalation_text, emotion=emotion)
                try:
                    save_last_ai(session_doc if session_doc else session_id, escalation_text)
                    db["sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {"last_interaction": datetime.utcnow()}}
                    )
                except Exception: pass
                
            return {
                "emotion": emotion,
                "understanding": "low",
                "confidence": 1.0,
                "response": escalation_text,
                "status": "success",
                "adaptation_applied": {
                    "intent": intent,
                    "handled_as": "struggle_escalation"
                }
            }
        
        if struggle_count >= 3:
            escalation_mode = "tier1"
            teaching_mode = "simplify"
        
        # Get session history for context
        session_history = get_session_history(session_id, limit=6) if session_id else None
        
        # DEBUG: Log full state before LLM call (excluding lesson_stage)
        print(f"\n[COORDINATOR] ========== STATE BEFORE LLM ==========")
        print(f"[COORDINATOR] concept: {concept_to_teach}")
        print(f"[COORDINATOR] emotion: {emotion}")
        print(f"[COORDINATOR] intent: {intent}")
        print(f"[COORDINATOR] user_message: {message[:80]}")
        print(f"[COORDINATOR] session_state keys: {list(session_state.keys())}")
        print(f"[COORDINATOR] explained_concepts: {session_state.get('explained_concepts', [])}")
        print(f"[COORDINATOR] ==========================================\n")
        
        print(f"[COORDINATOR] Calling generate_lesson for: {concept_to_teach}")
        
        # Evaluator injection for semantic correctness of answers
        if intent == "answer":
            from backend.agents.evaluator_agent import evaluate_answer
            prev_substantive = session_state.get("last_substantive_message", {})
            prev_q = prev_substantive.get("text", "") if isinstance(prev_substantive, dict) else prev_substantive
            eval_dict = evaluate_answer(concept_to_teach, prev_q, message)
            raw_eval = eval_dict.get("evaluation")
            if raw_eval == "confused":
                session_state["evaluation"] = "incorrect"
            elif raw_eval == "unanswering":
                session_state["evaluation"] = None
            else:
                session_state["evaluation"] = raw_eval
            print(f"[EVALUATOR] Explicit semantic evaluation: {raw_eval} -> mapped to {session_state['evaluation']}")
        
        lesson = generate_lesson(
            concept=concept_to_teach,
            emotion=emotion,
            evaluation_result=session_state.get("evaluation"),
            style="teacher",
            attempt_count=session_state.get("struggle_count", 0), # Use struggle_count as attempt count proxy in generator
            intent=intent,
            last_explanation_type=session_state.get("last_strategy"),
            teaching_mode=teaching_mode or "normal",
            explained_concepts=session_state.get("explained_concepts", []),
            depth_level=session_state.get("depth_level"),
            user_query=message,
            session_history=session_history
        )
        
        # Step 6: Get the natural response text (no parsing, no reconstruction)
        reply = lesson.get("response", "").strip()

        if not reply:
            print(f"[COORDINATOR] WARNING: Empty response, using fallback")
            reply = f"Let me explain {topic} in a different way."
        
        print(f"[COORDINATOR] Response: {len(reply)} chars")
        
        # Step 7: Update session state
        if session_id:
            session_state["last_message"] = message
            session_state["intent"] = intent
            update_session_state(
                session_id=session_id,
                lesson=lesson,
                emotion=emotion,
                understanding=understanding,
                evaluation=session_state.get("evaluation"),
                session_state=session_state
            )
        
        # Step 8: Save messages
        if session_id:
            save_message(session_id, "student", message)
            save_message(session_id, "ai", reply, emotion=emotion)
            try:
                save_last_ai(session_doc if session_doc else session_id, reply)
            except Exception:
                pass
        
        # Step 9: Return response
        return {
            "emotion": emotion,
            "understanding": understanding,
            "confidence": confidence,
            "response": reply,
            "status": "success",
            "adaptation_applied": {
                "intent": intent,
                "handled_as": "confused_lesson" if intent == "confused" else "standard_lesson",
                "strategy_used": lesson.get("strategy_used"),
                "teaching_mode": teaching_mode or "normal"
            }
        }
    
    except Exception as e:
        print(f"[COORDINATOR] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            err_text = "I'm having trouble processing your message. Please try again."
            if 'session_doc' in locals() and session_doc:
                save_last_ai(session_doc, err_text)
            elif session_id:
                save_last_ai(session_id, err_text)
        except Exception:
            pass

        return {
            "emotion": "neutral",
            "understanding": "medium",
            "confidence": 0.0,
            "response": "I'm having trouble processing your message. Please try again.",
            "status": "error",
            "error": str(e)
        }


# ===== BACKWARD COMPATIBILITY WRAPPER =====
def process_student_message(topic, student_message, session_id=None, conversation_history=None, teaching_mode=None):
    """Wrapper for process_learning_message - kept for backward compatibility"""
    return process_learning_message(topic, student_message, session_id, teaching_mode)
