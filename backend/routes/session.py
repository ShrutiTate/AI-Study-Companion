from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.db.mongo import db
import uuid
from datetime import datetime, timedelta, timezone
from backend.services.rag import rag_pipeline
from backend.services.emotion import detect_emotion
import os
import json
try:
    from groq import Groq
except ImportError:
    print("[SESSION] Warning: Groq not installed")

router = APIRouter()

# Session configuration
MAX_SESSION_DURATION = 12 * 60 * 60  # 12 hours in seconds
WARNING_THRESHOLD = 11 * 60 * 60     # Warn at 11 hours

class StartSessionRequest(BaseModel):
    user_id: str
    topic: str

class EndSessionRequest(BaseModel):
    session_id: str

class ChatRequest(BaseModel):
    session_id: str
    text: str

@router.post("/start")
def start_session(request: StartSessionRequest):
    """
    Start a new learning session with production tutoring state.
    
    Session tracks:
    - topic: Main topic
    - concepts: List of concepts to learn (generated)
    - concept_index: Current position (0, 1, 2...)
    - last_question: Question asked (for student to answer)
    - emotion: Detected emotion
    - evaluation: Previous answer quality (correct/partial/incorrect)
    - teaching_mode: How to adapt (normal/simplified/advanced)
    - explained_concepts: List of concepts already covered (prevents re-explanation)
    - depth_level: Current depth (intro/intermediate/advanced)
    - lesson_stage: Where we are in teaching (introduction/expansion/quiz/review)
    - last_response_mode: Type of last response (lesson/expansion/clarification)
    """
    from backend.services.ai_tutor_production import generate_concepts
    
    concepts = generate_concepts(request.topic)
    
    session = {
        "session_id": str(uuid.uuid4()),
        "user_id": request.user_id,
        "topic": request.topic,
        # ===== PRODUCTION ARCHITECTURE =====
        "concepts": concepts,  # e.g., ["What is recursion", "Base case", "Recursive call"]
        "concept_index": 0,  # Start at first concept — CRITICAL for /learn endpoint
        "current_concept": concepts[0] if concepts else request.topic,
        # ===== CHATBOT CONVERSATION HISTORY =====
        "messages": [],  # {role: "user"|"assistant", content: "..."}
        # ===== TUTORING STATE =====
        "last_question": "",  # The question student should answer
        "emotion": "neutral",  # Current emotion
        "cognitive_load_score": 1,  # 1-5 scale for cognitive overload detection
        "evaluation": None,  # Previous answer: correct|partial|incorrect
        "teaching_mode": "normal",  # How to teach: normal|simplified|advanced
        # ===== STABLE PEDAGOGICAL STATE (NEW - prevents oscillation) =====
        "stable_teaching_level": "intermediate",  # beginner|intermediate|advanced
        "stable_level_confidence": 0.5,  # 0.0-1.0
        "level_change_cooldown": 0,  # Prevents rapid mode changes
        "concept_mastery": {},  # {concept: score 0.0-1.0}
        "last_substantive_message": None,  # Preserves context
        # ===== CONVERSATIONAL PROGRESSION (NEW - prevents repetition) =====
        "explained_concepts": [],  # Concepts already taught
        "avoid_list": [],  # Dynamic list of approaches to avoid (redefine_ai, etc)
        "depth_level": "intro",  # intro | intermediate | advanced
        "last_response_mode": "lesson",  # lesson | expansion | clarification | answer | summary
        # ===== SESSION METADATA =====
        "start_time": datetime.now(),
        "end_time": None,
        "duration": 0,
        "status": "active",
        "conversation_state": "idle",  # idle | question_asked | waiting_for_evaluation
        "turn_count": 0,  # Total turns on current concept
        "struggle_count": 0,  # Number of incorrect attempts
        "created_at": datetime.now(),
        "last_interaction": datetime.now()
    }
    db["sessions"].insert_one(session)
    try:
        from backend.services.event_tracker import EventTracker
        EventTracker.track_session_started(session["session_id"], request.user_id, request.topic)
    except Exception as e:
        print(f"[SESSION] Failed to track session started: {e}")
    
    return {
        "session_id": session["session_id"],
        "user_id": session["user_id"],
        "topic": session["topic"],
        "current_concept": session["current_concept"],
        "concepts": session["concepts"],
        "concept_index": session["concept_index"],
        "status": "active",
        "conversation_state": "idle",
        "start_time": session["start_time"].isoformat()
    }

@router.post("/end")
def end_session(request: EndSessionRequest):
    """End an active learning session"""
    session = db["sessions"].find_one({"session_id": request.session_id})
    
    if not session:
        return {"error": "Session not found"}
    
    if session.get("status") == "completed":
        return {"error": "Session already completed"}
    
    # Calculate duration for THIS session cycle
    # If resumed: duration from resumed_at, otherwise from start_time
    resumed_at = session.get("resumed_at")
    if resumed_at:
        # Session was resumed - calculate time since resume
        current_duration = (datetime.now() - resumed_at).total_seconds()
    else:
        # First time ending - calculate from start
        start_time = session.get("start_time", datetime.now())
        current_duration = (datetime.now() - start_time).total_seconds()
    
    # Add to accumulated duration
    accumulated_duration = session.get("duration", 0)
    total_duration = accumulated_duration + current_duration
    
    # ===== FIX: Calculate dominant emotion from all messages =====
    messages = session.get("messages", [])
    emotion_counts = {
        "engaged": 0,
        "frustrated": 0,
        "confused": 0,
        "neutral": 0
    }
    
    for msg in messages:
        emotion = msg.get("emotion", "neutral")
        # Normalize emotion to our main categories
        if emotion in ["engaged", "very_engaged"]:
            emotion_counts["engaged"] += 1
        elif emotion in ["frustrated", "very_frustrated"]:
            emotion_counts["frustrated"] += 1
        elif emotion in ["confused", "very_confused"]:
            emotion_counts["confused"] += 1
        else:
            emotion_counts["neutral"] += 1
    
    # Find dominant emotion
    dominant_emotion = max(emotion_counts, key=emotion_counts.get)
    print(f"[SESSION_END] Emotion breakdown: {emotion_counts} → Dominant: {dominant_emotion}")
    
    # ===== NEW: Session Analytics Dump =====
    print("\n" + "="*50)
    print(f"[SESSION_SUMMARY] Session ID: {request.session_id}")
    print(f"  Starting Level: {session.get('initial_level', 'unknown')}")
    print(f"  Ending Level:   {session.get('stable_teaching_level', 'unknown')}")
    print(f"  Depth Drops:    {session.get('depth_drops', 0)}")
    print(f"  Depth Advances: {session.get('depth_advances', 0)}")
    print(f"  Accelerations:  {session.get('acceleration_events', 0)}")
    print(f"  RECOVERY Entries:{session.get('recovery_entries', 0)}")
    print(f"  RECOVERY Exits:  {session.get('recovery_exits', 0)}")
    print("  Final Mastery:")
    concept_mastery = session.get("concept_mastery", {})
    if not concept_mastery:
        print("    No concepts mastered.")
    for concept_name, score in concept_mastery.items():
        print(f"    - {concept_name}: {score:.2f}")
    print("="*50 + "\n")
    db["sessions"].update_one(
        {"session_id": request.session_id},
        {"$set": {
            "end_time": datetime.now(),
            "duration": int(total_duration),
            "status": "completed",
            "emotion": dominant_emotion,  # ← Update emotion to dominant
            "emotion_breakdown": emotion_counts  # Store breakdown for analytics
        }}
    )
    try:
        from backend.services.event_tracker import EventTracker
        concepts_learned = len(session.get("explained_concepts", []))
        duration_minutes = total_duration / 60.0
        EventTracker.track_session_completed(request.session_id, session.get("user_id"), concepts_learned, duration_minutes)
    except Exception as e:
        print(f"[SESSION_END] Failed to track session completed: {e}")
    
    # ===== STREAK CALCULATION (timestamp-based, uses analytics_events) =====
    try:
        user_id = session.get("user_id")
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today - timedelta(days=1)
        
        # Check if there was any analytics activity yesterday for this user
        yesterday_activity = db["analytics_events"].find_one({
            "user_id": user_id,
            "timestamp": {"$gte": yesterday_start, "$lt": today}
        })
        
        # Get current streak from user profile
        user_doc = db["users"].find_one({"user_id": user_id})
        current_streak = 0
        if user_doc:
            current_streak = user_doc.get("learning_streak", 0)
        
        if yesterday_activity:
            # User was active yesterday — extend streak
            new_streak = current_streak + 1
        else:
            # No activity yesterday — reset to 1 (today counts)
            new_streak = 1
        
        db["users"].update_one(
            {"user_id": user_id},
            {"$set": {
                "learning_streak": new_streak,
                "last_streak_date": today.isoformat()
            }},
            upsert=True
        )
        print(f"[STREAK] User {user_id}: {current_streak} → {new_streak}")
    except Exception as e:
        print(f"[STREAK] Failed to update streak (non-fatal): {e}")
    
    return {
        "session_id": request.session_id,
        "duration": int(total_duration),
        "current_cycle_duration": int(current_duration),
        "accumulated_duration": int(accumulated_duration),
        "status": "completed",
        "message": "Session ended successfully",
        "emotion": dominant_emotion,
        "emotion_breakdown": emotion_counts
    }


@router.get("/history/{user_id}")
def get_session_history(user_id: str):
    """Get all sessions for a user, sorted by start time (newest first)"""
    try:
        print(f"[HISTORY] Fetching sessions for user: {user_id}")
        
        sessions = list(db["sessions"].find(
            {"user_id": user_id}
        ).sort("start_time", -1))
        
        print(f"[HISTORY] Found {len(sessions)} sessions for {user_id}")
        
        # Format for frontend
        formatted_sessions = []
        for session in sessions:
            # Defensive: use .get() for fields that might be missing
            topic = session.get("topic", "Untitled Session")
            start_time = session.get("start_time")
            end_time = session.get("end_time")
            
            formatted_sessions.append({
                "session_id": session.get("session_id", "unknown"),
                "topic": topic,
                "start_time": start_time.isoformat() if start_time else datetime.now().isoformat(),
                "end_time": end_time.isoformat() if end_time else None,
                "duration": session.get("duration", 0),
                "status": session.get("status", "unknown"),
                "message_count": len(session.get("messages", [])),
                "emotion": session.get("emotion", "neutral"),
                "current_concept": session.get("current_concept", topic)
            })
        
        print(f"[HISTORY] Formatted {len(formatted_sessions)} sessions successfully")
        
        return {
            "user_id": user_id,
            "total_sessions": len(formatted_sessions),
            "sessions": formatted_sessions,
            "status": "success"
        }
    except Exception as e:
        print(f"[HISTORY] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "status": "error",
            "sessions": []
        }


@router.get("/{session_id}")
def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    try:
        session = db["sessions"].find_one({"session_id": session_id})
        
        if not session:
            return {"error": "Session not found", "status": "error"}
        
        topic = session.get("topic", "Untitled Session")
        start_time = session.get("start_time", datetime.now())
        end_time = session.get("end_time")
        resumed_at = session.get("resumed_at")
        
        # Calculate total duration properly
        # If session is active and resumed, add current elapsed time
        accumulated_duration = session.get("duration", 0)
        if session.get("status") == "active" and resumed_at:
            # Session is currently resumed - add time since resume
            current_elapsed = (datetime.now() - resumed_at).total_seconds()
            total_duration = accumulated_duration + int(current_elapsed)
        else:
            total_duration = accumulated_duration
        
        # Convert messages to frontend format
        converted_messages = []
        for msg in session.get("messages", []):
            if msg and (msg.get("text") or msg.get("content")):
                converted = {
                    "role": "user" if msg.get("role") in ["student", "user"] else "assistant",
                    "content": (msg.get("text") or msg.get("content") or "").strip(),
                    "emotion": msg.get("emotion")  # ← Include emotion field
                }
                converted_messages.append(converted)
        
        print(f"[SESSION_DETAILS] Converted {len(converted_messages)} messages from {len(session.get('messages', []))} total")
        if converted_messages:
            print(f"[SESSION_DETAILS] First message: {converted_messages[0]}")
        
        return {
            "session_id": session.get("session_id", "unknown"),
            "user_id": session.get("user_id", "unknown"),
            "topic": topic,
            "start_time": start_time.isoformat() if start_time else datetime.now().isoformat(),
            "end_time": end_time.isoformat() if end_time else None,
            "resumed_at": resumed_at.isoformat() if resumed_at else None,
            "duration": total_duration,
            "accumulated_duration": accumulated_duration,
            "status": session.get("status", "unknown"),
            "messages": converted_messages,
            "emotion": session.get("emotion", "neutral"),
            "current_concept": session.get("current_concept", topic),
            "concepts": session.get("concepts", []),
            "concept_index": session.get("concept_index", 0),
            "message_count": len(session.get("messages", [])),
            "status_ok": "success"
        }
    except Exception as e:
        print(f"[SESSION_DETAILS] Error: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.post("/resume/{session_id}")
def resume_session(session_id: str):
    """Resume an ended session - preserves accumulated duration"""
    try:
        session = db["sessions"].find_one({"session_id": session_id})
        
        if not session:
            return {"error": "Session not found", "status": "error"}
        
        if session.get("status") == "active":
            return {"error": "Session is already active", "status": "error"}
        
        # Preserve the previous duration (accumulated time)
        previous_duration = session.get("duration", 0)
        
        # Resume the session - keep accumulated duration, reset end_time
        db["sessions"].update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "active",
                "end_time": None,
                "duration": previous_duration,  # Keep accumulated duration
                "resumed_at": datetime.now(),
                "total_paused_time": session.get("total_paused_time", 0) + (previous_duration or 0),
                "resumed_session_pending": True
            }}
        )
        
        # Get updated session
        updated_session = db["sessions"].find_one({"session_id": session_id})
        
        if not updated_session:
            return {"error": "Session not found after resume", "status": "error"}
        
        topic = updated_session.get("topic", "Untitled Session")
        return {
            "session_id": session_id,
            "topic": topic,
            "status": "active",
            "current_concept": updated_session.get("current_concept", topic),
            "message_count": len(updated_session.get("messages", [])),
            "accumulated_duration": previous_duration,
            "resumed_at": datetime.now().isoformat(),
            "message": "Session resumed successfully"
        }
    except Exception as e:
        print(f"[RESUME] Error: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.post("/force-close/{session_id}")
def force_close_session(session_id: str):
    """Force close an active session immediately (fixes runaway timers)"""
    try:
        session = db["sessions"].find_one({"session_id": session_id})
        
        if not session:
            return {"error": "Session not found", "status": "error"}
        
        if session.get("status") == "completed":
            return {
                "session_id": session_id,
                "message": "Session already completed",
                "status": "already_closed"
            }
        
        # Calculate final duration
        resumed_at = session.get("resumed_at")
        if resumed_at:
            current_duration = (datetime.now() - resumed_at).total_seconds()
        else:
            start_time = session.get("start_time", datetime.now())
            current_duration = (datetime.now() - start_time).total_seconds()
        
        accumulated_duration = session.get("duration", 0)
        total_duration = accumulated_duration + int(current_duration)
        
        # Close the session
        db["sessions"].update_one(
            {"session_id": session_id},
            {"$set": {
                "end_time": datetime.now(),
                "duration": int(total_duration),
                "status": "completed"
            }}
        )
        
        print(f"[FORCE_CLOSE] Session {session_id} force closed. Duration: {total_duration}s")
        
        return {
            "session_id": session_id,
            "duration": int(total_duration),
            "message": "Session force closed",
            "status": "success"
        }
    except Exception as e:
        print(f"[FORCE_CLOSE] Error: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/close-all-active")
def close_all_active_sessions():
    """Close ALL active sessions (admin function for cleanup)"""
    try:
        result = db["sessions"].update_many(
            {"status": "active"},
            {"$set": {
                "end_time": datetime.now(),
                "status": "completed"
            }}
        )
        
        print(f"[CLOSE_ALL] Closed {result.modified_count} active sessions")
        
        return {
            "sessions_closed": result.modified_count,
            "message": f"Closed {result.modified_count} active sessions",
            "status": "success"
        }
    except Exception as e:
        print(f"[CLOSE_ALL] Error: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.delete("/{session_id}")
def delete_session(session_id: str):
    """Delete a session from history"""
    try:
        result = db["sessions"].delete_one({"session_id": session_id})
        
        if result.deleted_count == 0:
            return {"error": "Session not found", "status": "error"}
        
        return {
            "session_id": session_id,
            "message": "Session deleted successfully",
            "status": "success"
        }
    except Exception as e:
        print(f"[DELETE] Error: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.post("/extract-concepts/{session_id}")
def extract_key_concepts(session_id: str):
    """
    Extract key learning concepts from a session using Groq AI.
    
    Uses the session's chat history to identify meaningful learning points
    and returns them as a structured list.
    """
    try:
        # Get session
        session = db["sessions"].find_one({"session_id": session_id})
        
        if not session:
            return {"error": "Session not found", "status": "error", "concepts": []}
        
        # Extract AI assistant messages
        messages = session.get("messages", [])
        ai_responses = []
        
        for msg in messages:
            if msg and msg.get("role") in ["assistant", "ai"]:
                content = msg.get("text") or msg.get("content") or ""
                if content.strip():
                    ai_responses.append(content)
        
        if not ai_responses:
            return {
                "session_id": session_id,
                "concepts": [],
                "message": "No AI responses found in session",
                "status": "success"
            }
        
        # Join all AI responses for analysis
        combined_content = "\n\n".join(ai_responses)
        
        # Get Groq API key
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            print("[CONCEPTS] Warning: GROQ_API_KEY not set")
            return {
                "session_id": session_id,
                "concepts": [],
                "message": "Groq API key not configured",
                "status": "error"
            }
        
        # Initialize Groq client
        client = Groq(api_key=groq_api_key)
        
        # Create prompt for concept extraction
        prompt = f"""You are an expert educator. Analyze the following educational chat session and extract the 5-7 most important learning concepts or topics covered.

Return your response as a JSON array of strings, where each string is a key concept (e.g., ["Recursion", "Base case", "Time complexity"]).

Do NOT include general phrases like "I'm here to help" or "Feel free to ask". Focus only on actual learning concepts, techniques, or knowledge points.

Educational content from session:
{combined_content}

Return ONLY the JSON array, no other text."""

        # Call Groq API
        message = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1024
        )
        
        # Parse response
        response_text = message.choices[0].message.content.strip()
        
        # Extract JSON from response (in case there's extra text)
        try:
            # Try to parse as JSON directly
            concepts = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON array from response
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                concepts = json.loads(json_match.group())
            else:
                # Fallback: return empty list
                print(f"[CONCEPTS] Could not parse Groq response: {response_text}")
                concepts = []
        
        # Ensure it's a list of strings
        if not isinstance(concepts, list):
            concepts = [str(concepts)]
        
        concepts = [str(c).strip() for c in concepts if c]
        
        print(f"[CONCEPTS] Extracted {len(concepts)} concepts from session {session_id}")
        
        return {
            "session_id": session_id,
            "concepts": concepts[:7],  # Limit to 7 concepts
            "message_count": len(ai_responses),
            "status": "success"
        }
    
    except Exception as e:
        print(f"[CONCEPTS] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "session_id": session_id,
            "concepts": [],
            "status": "error"
        }

@router.get("/active/{user_id}")
def get_active_session(user_id: str):
    """Get active session for user"""
    try:
        session = db["sessions"].find_one({
            "user_id": user_id,
            "status": "active"
        })
        
        if not session:
            return {"session_id": None, "status": "no_active_session"}
        
        topic = session.get("topic", "Untitled Session")
        start_time = session.get("start_time", datetime.now())
        return {
            "session_id": session.get("session_id", "unknown"),
            "topic": topic,
            "start_time": start_time.isoformat() if start_time else datetime.now().isoformat(),
            "status": "active"
        }
    except Exception as e:
        print(f"[ACTIVE_SESSION] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "status": "error"}


# Helper functions for conversation state management

def update_conversation_state(session_id: str, state: str, question: str = "") -> bool:
    """
    Update session conversation state.
    
    Args:
        session_id: Session ID
        state: New state ("idle", "question_asked", etc.)
        question: Question text if state is "question_asked"
    
    Returns:
        True if successful
    """
    try:
        update_data = {
            "conversation_state": state,
            "question_asked_at": datetime.now() if state == "question_asked" else None
        }
        
        if question:
            update_data["last_question"] = question
        
        db["sessions"].update_one(
            {"session_id": session_id},
            {"$set": update_data}
        )
        return True
    except Exception as e:
        print(f"Error updating conversation state: {e}")
        return False


def get_session_state(session_id: str) -> dict:
    """
    Get current session state including conversation context.
    
    Args:
        session_id: Session ID
    
    Returns:
        Session state dict or None
    """
    try:
        session = db["sessions"].find_one({"session_id": session_id})
        if not session:
            print(f"[SESSION] ⚠️ Session not found: {session_id}")
            return None
            
        state_dict = {
            "conversation_state": session.get("conversation_state", "idle"),
            "last_question": session.get("last_question", ""),
            "topic": session.get("topic", "")
        }
        print(f"[SESSION] Retrieved state: {state_dict}")
        return state_dict
    except Exception as e:
        print(f"Error getting session state: {e}")
        import traceback
        traceback.print_exc()
        return None


@router.post("/start-teaching")
def start_teaching(request: StartSessionRequest):
    """
    Start a learning session with production tutoring state.
    
    Flow:
    1. Generate concepts for topic
    2. Create session with concept tracking
    3. Generate first lesson (Explanation + Example + Question)
    4. Return session_id + first lesson
    
    Response structure:
    {
      "session_id": "...",
      "explanation": "...",
      "example": "...",
      "question": "...",
      "current_concept": "...",
      "concept_index": 0,
      "concepts": ["...", "...", "..."]
    }
    """
    from backend.services.ai_tutor_production import generate_concepts, generate_lesson
    
    try:
        # Input validation
        if not request.user_id or len(request.user_id.strip()) == 0:
            return {"error": "user_id required", "status": "error"}
        
        if not request.topic or len(request.topic.strip()) == 0:
            return {"error": "topic required", "status": "error"}
        
        if len(request.topic.strip()) > 200:
            return {"error": "topic too long (max 200 characters)", "status": "error"}
        
        print(f"[START_TEACHING] Creating session for user: {request.user_id}, topic: {request.topic}")
        
        # 1. Defer concept generation to post-onboarding
        # Concepts will be generated AFTER student answers the onboarding question
        # so we can shape the path based on their level
        concepts = [request.topic]  # Placeholder — real list generated after onboarding
        first_concept = request.topic
        
        # 2. Create session with production schema
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "user_id": request.user_id,
            "topic": request.topic,
            # PRODUCTION STATE
            "concepts": concepts,
            "concept_index": 0,
            "current_concept": first_concept,
            "last_question": "Prior experience query",
            "emotion": "neutral",
            "evaluation": None,
            "teaching_mode": "normal",
            # ===== STABLE PEDAGOGICAL STATE =====
            "stable_teaching_level": "pending",  # Set after onboarding classification
            "stable_level_confidence": 0.5,  # 0.0-1.0
            "level_change_cooldown": 0,  # Prevents rapid mode changes
            "concept_mastery": {},  # {concept: score 0.0-1.0}
            "last_substantive_message": None,  # Preserves context
            # ===== CONVERSATIONAL PROGRESSION =====
            "explained_concepts": [],  # Concepts already taught
            "depth_level": "intro",  # intro | intermediate | advanced — set after onboarding
            "last_response_mode": "lesson",  # lesson | expansion | clarification | answer | summary
            "session_phase": "ONBOARDING",
            "onboarding_welcome_sent": True,
            "concepts_generated": False,  # Flag: true after post-onboarding generation
            "resumed_session_pending": False,
            # CHATBOT CONVERSATION HISTORY
            "messages": [],
            # SESSION METADATA
            "start_time": datetime.now(),
            "status": "active",
            "conversation_state": "question_asked",
            "turn_count": 0,
            "struggle_count": 0
        }
        
        # 3. Generate first lesson (Onboarding Welcome — asks about experience)
        lesson = generate_lesson(
            concept=request.topic,
            emotion="neutral",
            evaluation_result=None,
            session_phase="ONBOARDING",
            concepts=concepts
        )
        
        explanation = lesson.get("explanation") or lesson.get("response", "")
        example = lesson.get("example", "")
        question = lesson.get("question", "")
        
        # 4. Add initial AI message to conversation WITH EMOTION
        content_parts = [part for part in [explanation, example, question] if part]
        initial_message = {
            "role": "assistant",
            "content": "\n\n".join(content_parts).strip(),
            "emotion": "neutral"  # ← Store emotion with initial message
        }
        session["messages"].append(initial_message)
        
        db["sessions"].insert_one(session)
        print(f"[START_TEACHING] Session created: {session_id}")
        try:
            from backend.services.event_tracker import EventTracker
            EventTracker.track_session_started(session_id, request.user_id, request.topic)
            EventTracker.track_concept_presented(session_id, request.user_id, first_concept)
        except Exception as e:
            print(f"[START_TEACHING] Failed to track session started/concept presented: {e}")
        
        return {
            "session_id": session_id,
            "user_id": request.user_id,
            "topic": request.topic,
            "current_concept": first_concept,
            "concepts": concepts,
            "concept_index": 0,
            "status": "active",
            "conversation_state": "question_asked",
            "start_time": session["start_time"].isoformat(),
            "explanation": explanation,
            "example": example,
            "question": question,
            "emotion": "neutral",
            "evaluation": None,
            "response": lesson.get("response", explanation)
        }
        
    except Exception as e:
        print(f"[START-TEACHING] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "status": "error"
        }


# ===== HELPER FUNCTIONS FOR LEARNING LOOP =====

def extract_question(text: str) -> str:
    """
    Extract the first question from response text.
    Looks for sentences ending with '?'
    
    Args:
        text: Response text
        
    Returns:
        First question found, or empty string
    """
    for line in text.split("\n"):
        line_stripped = line.strip()
        if "?" in line_stripped:
            # Clean up markdown symbols
            line_cleaned = line_stripped.replace("❓", "").replace("**", "").replace("*", "").strip()
            if line_cleaned:
                return line_cleaned
    return ""


def is_actual_answer(text: str, conversation_state: str) -> bool:
    """
    Determine if user input is an actual answer (not a new question/doubt).
    
    Args:
        text: User input
        conversation_state: Current state ("question_asked", "idle", etc.)
        
    Returns:
        True if user is likely answering a question
    """
    
    # System expects an answer, user is probably answering
    if conversation_state != "question_asked":
        return False
    
    text_lower = text.lower().strip()
    
    # If text contains question marks, user is asking, not answering
    if "?" in text:
        return False
    
    # If text starts with question words, user is asking
    question_starters = ["what", "why", "how", "can you", "explain", "tell me", "help", "which"]
    if any(text_lower.startswith(starter) for starter in question_starters):
        return False
    
    # Empty text is not an answer
    if not text_lower:
        return False
    
    return True


def format_response(explanation: str, example: str, question: str) -> dict:
    """
    Format response parts into a clean structure.
    
    Args:
        explanation: The explanation part
        example: The example part
        question: The follow-up question
        
    Returns:
        Formatted response dict
    """
    return {
        "explanation": explanation.strip() if explanation else "",
        "example": example.strip() if example else "",
        "quick_check": question.strip() if question else ""
    }


# ===== CHATBOT TUTOR ENDPOINT =====

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chatbot tutor endpoint using Agent Coordinator with Memory.
    
    AGENT-BASED ARCHITECTURE WITH STEP 3 (CONVERSATION MEMORY):
    1. Load session from MongoDB
    2. Use Agent Coordinator to process message with session_id
    3. Coordinator automatically:
       - Loads conversation history via session_service
       - Generates response with full context
       - Saves messages to MongoDB
    4. Return structured response
    
    The coordinator handles:
    - Emotion detection (confused/frustrated/engaged)
    - Understanding level assessment
    - Conversation memory (via session_service)
    - Topic-focused tutoring response generation
    - Structured response format (Explanation → Example → Question)
    """
    from backend.agents.agent_coordinator import process_student_message
    
    try:
        # DEBUG: Log incoming request
        print(f"\n[CHAT] ========== REQUEST START ==========")
        print(f"[CHAT] session_id: {request.session_id}")
        print(f"[CHAT] message: '{request.text}'")
        
        # Input validation
        if not request.session_id or len(request.session_id.strip()) == 0:
            print(f"[CHAT] ❌ ERROR: session_id required")
            return {"error": "session_id required", "status": "error"}
        
        if not request.text or len(request.text.strip()) == 0:
            print(f"[CHAT] ❌ ERROR: message cannot be empty")
            return {"error": "message cannot be empty", "status": "error"}
        
        if len(request.text.strip()) > 2000:
            print(f"[CHAT] ❌ ERROR: message too long")
            return {"error": "message too long (max 2000 characters)", "status": "error"}
        
        # 1. Get session from MongoDB
        session = db["sessions"].find_one({"session_id": request.session_id})
        if not session:
            print(f"[CHAT] ❌ ERROR: Session not found in DB")
            return {"error": "Session not found", "status": "error"}
        
        print(f"[CHAT] ✅ Session loaded: topic={session.get('topic')}")
        print(f"[CHAT] Session status: {session.get('status')}")
        
        # AUTO-CLOSE CHECK: If session exceeded max duration, close it
        if session.get("status") == "active":
            resumed_at = session.get("resumed_at")
            accumulated_duration = session.get("duration", 0)
            
            if resumed_at:
                current_duration = (datetime.now() - resumed_at).total_seconds()
            else:
                start_time = session.get("start_time", datetime.now())
                current_duration = (datetime.now() - start_time).total_seconds()
            
            total_duration = accumulated_duration + current_duration
            
            # Check if exceeded max duration
            if total_duration > MAX_SESSION_DURATION:
                print(f"[CHAT] ⚠️ Session {request.session_id} exceeded max duration ({total_duration}s > {MAX_SESSION_DURATION}s)")
                print(f"[CHAT] Auto-closing session...")
                
                # Auto-close the session
                db["sessions"].update_one(
                    {"session_id": request.session_id},
                    {"$set": {
                        "end_time": datetime.now(),
                        "duration": int(total_duration),
                        "status": "expired",
                        "auto_closed": True
                    }}
                )
                
                return {
                    "error": "Session exceeded maximum duration (12 hours) and was automatically closed",
                    "status": "session_expired",
                    "final_duration": int(total_duration)
                }
            
            # WARN if approaching limit
            if total_duration > WARNING_THRESHOLD:
                minutes_left = (MAX_SESSION_DURATION - total_duration) / 60
                print(f"[CHAT] ⚠️ Session {request.session_id} approaching limit: {minutes_left:.1f} minutes remaining")
        
        topic = session.get("topic", "unknown topic")
        
        # 2. USE AGENT COORDINATOR WITH SESSION_ID
        # The coordinator will:
        # - Load history from session_service
        # - Generate response with full context
        # - Save messages automatically
        print(f"[CHAT] → Calling process_student_message(topic={topic})")
        result = process_student_message(
            topic=topic,
            student_message=request.text,
            session_id=request.session_id  # Pass session_id for automatic memory management
        )
        
        # Extract results from agent coordinator
        ai_response = result["response"]
        emotion = result["emotion"]
        understanding = result["understanding"]
        confidence = result.get("confidence", 0.75)
        
        # DEBUG: Log emotion being returned
        print(f"[CHAT] ✅ Coordinator returned:")
        print(f"[CHAT]   emotion: {emotion}")
        print(f"[CHAT]   understanding: {understanding}")
        print(f"[CHAT]   response (first 100 chars): {ai_response[:100]}")
        
        # 3. UPDATE SESSION METADATA (emotion, understanding state)
        # Note: Messages are already saved by agent coordinator
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": {
                "emotion": emotion,
                "understanding": understanding,
                "last_user_message": request.text,
                "last_update": datetime.now()
            }}
        )
        
        # 4. Return response with emotion + understanding context
        response = {
            "response": ai_response,
            "emotion": emotion,
            "understanding": understanding,
            "confidence": confidence,
            "status": "success",
            "message_count": len(session["messages"]),
            "structured": result.get("structured", {})
        }
        
        print(f"[CHAT] ========== RESPONSE ==========")
        print(f"[CHAT] Status: success")
        print(f"[CHAT] Response: {response}")
        print(f"[CHAT] ========== REQUEST END ==========\n")
        
        return response
        
    except Exception as e:
        print(f"[CHAT] ❌ Error in agent coordinator: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "status": "error"
        }

