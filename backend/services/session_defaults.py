# backend/services/session_defaults.py
"""
Session schema validation and defaults.
Ensures every session has all required fields to prevent missing key errors.
"""

from datetime import datetime
from typing import Optional

def ensure_session_structure(session: dict) -> dict:
    """
    Ensure session document has all required fields with safe defaults.
    Call after EVERY database fetch to guarantee field existence.
    
    This prevents:
    - KeyError: 'concept_index' when accessing session.get("concept_index")
    - Undefined behavior from missing pedagogical fields
    - Inconsistent session states
    
    Args:
        session: Session document from MongoDB
    
    Returns:
        Session with all required fields initialized
    """
    
    if not session:
        return {}
    
    # Compute safe defaults based on existing data
    concepts = session.get("concepts", [])
    concepts_total = len(concepts)
    
    # Default values for all required fields
    required_fields = {
        # Core identifiers
        "session_id": "",
        "user_id": "",
        "status": "active",
        
        # Curriculum progression
        "concept_index": 0,  # CRITICAL: Prevent KeyError
        "concepts": [],
        "current_concept": concepts[0] if concepts else "Introduction",
        
        # Teaching state
        "teaching_mode": "teach_basic",
        "lesson_stage": "introduction",
        "depth_level": "intro",
        "conversation_state": "active",
        "session_phase": "ONBOARDING",
        "onboarding_welcome_sent": False,
        "resumed_session_pending": False,
        
        # Emotional & Cognitive State
        "emotion": "neutral",
        "cognitive_load_score": 1,
        
        # Tutor State Machine (NEW)
        "tutor_state": "normal",
        "level_change_cooldown": 0,
        "sustained_emotional_history": [],
        
        # Analogy Governance (NEW)
        "analogy_cooldown": 0,
        "used_analogies": [],
        
        # Learning Progress
        "explained_concepts": [],
        "avoid_list": [],
        "attempt_count": 0,
        "stable_teaching_level": "intermediate",
        
        # Interaction Tracking
        "last_question": "",
        "last_substantive_message": None,
        "last_interaction": datetime.now(),
        
        # Metadata
        "created_at": datetime.now(),
    }
    
    # Check each field and initialize if missing
    initialized_fields = []
    for field, default_value in required_fields.items():
        if field not in session:
            session[field] = default_value
            initialized_fields.append(field)
    
    # Log all initializations
    if initialized_fields:
        print(f"[SESSION] Initialized {len(initialized_fields)} missing fields: {initialized_fields}")
    
    # Sanity checks after initialization
    if session.get("concept_index", 0) >= len(session.get("concepts", [])):
        if session.get("concepts"):
            print(f"[SESSION] Warning: concept_index ({session['concept_index']}) >= concepts_total ({len(session['concepts'])})")
            session["concept_index"] = len(session["concepts"]) - 1
    
    return session


def get_session_snapshot(session: dict) -> dict:
    """
    Extract session state for response/logging without modifying original.
    
    Returns:
        Safe copy of session with only important fields
    """
    return {
        "session_id": session.get("session_id", ""),
        "user_id": session.get("user_id", ""),
        "status": session.get("status", "active"),
        "concept_index": session.get("concept_index", 0),
        "concepts_total": len(session.get("concepts", [])),
        "current_concept": session.get("current_concept", ""),
        "emotion": session.get("emotion", "neutral"),
        "cognitive_load_score": session.get("cognitive_load_score", 1),
        "teaching_mode": session.get("teaching_mode", "teach_basic"),
        "stable_teaching_level": session.get("stable_teaching_level", "intermediate"),
        "tutor_state": session.get("tutor_state", "normal"),
        "analogy_cooldown": session.get("analogy_cooldown", 0),
    }


def validate_session_bounds(session: dict) -> bool:
    """
    Validate session has sane boundaries.
    Raises ValueError if state is corrupted.
    """
    concept_index = session.get("concept_index", 0)
    concepts_total = len(session.get("concepts", []))
    
    if concept_index < 0:
        raise ValueError(f"[SESSION] concept_index negative: {concept_index}")
    
    if concept_index > concepts_total:
        raise ValueError(
            f"[SESSION] concept_index ({concept_index}) exceeds total ({concepts_total})"
        )
    
    cognitive_load = session.get("cognitive_load_score", 1)
    if cognitive_load < 1 or cognitive_load > 5:
        raise ValueError(f"[SESSION] cognitive_load_score out of range: {cognitive_load}")
    
    return True
