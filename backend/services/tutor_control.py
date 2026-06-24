# backend/services/tutor_control.py
"""
Production Tutoring Control & Orchestration Layer.
Implements:
1. Persistent Tutor State Machine (NORMAL, SIMPLIFIED, RECOVERY, CHALLENGE, ASSESSMENT)
2. Response Policy Layer (deterministic rules per state)
3. Grounding Enforcement (direct first-sentence answers)
4. Analogy Governance & Cooldown System
5. Pre-flight Response Validation & Safe Fallback Layer
"""

import re
from enum import Enum
from typing import Tuple, List, Dict, Any
from backend.services.session_defaults import ensure_session_structure

class TutorState(str, Enum):
    NORMAL = "normal"
    SIMPLIFIED = "simplified"
    RECOVERY = "recovery"
    CHALLENGE = "challenge"
    ASSESSMENT = "assessment"

class SessionPhase(str, Enum):
    ONBOARDING = "ONBOARDING"
    LEARNING = "LEARNING"
    RECOVERY = "RECOVERY"
    ASSESSMENT = "ASSESSMENT"
    CLOSING = "CLOSING"

def infer_level_from_onboarding(user_input: str) -> str:
    """
    Analyzes student's first response during onboarding to infer their prior experience.
    Returns: "complete_beginner" | "some_exposure" | "intermediate" | "advanced"
    
    RULE: If student says anything resembling "I'm new" / "never heard" / "basics please"
    → force complete_beginner, no exceptions.
    """
    text_lower = user_input.lower().strip()
    
    # FORCED complete_beginner — these are unambiguous zero-knowledge signals
    forced_beginner = [
        "i'm new", "im new", "i am new", "never heard", "no idea", "brand new",
        "completely new", "never coded", "no experience", "first time", "absolute beginner",
        "not coded", "what is coding", "no coding", "no clue", "just starting",
        "basics please", "start from scratch", "know nothing", "dont know anything",
        "don't know anything", "never programmed", "never used", "total beginner",
        "zero experience", "never learned", "i'm a beginner", "im a beginner"
    ]
    if any(ind in text_lower for ind in forced_beginner):
        print(f"[ONBOARDING] FORCED complete_beginner: matched forced pattern in '{text_lower}'")
        return "complete_beginner"
    
    # Advanced keywords
    advanced_indicators = [
        "advanced", "experienced", "years", "expert", "senior", "write a lot of code", 
        "professional", "know syntax", "oop", "decorator", "classes", "recursion", "algorithms",
        "already know", "familiar with", "plenty of", "expert in", "very comfortable"
    ]
    # Some exposure (tried it, know a bit, used another language)
    some_exposure_indicators = [
        "some", "a bit", "tried", "a little", "started", "python before", 
        "other languages", "c++", "java", "javascript", "some coding",
        "basic concepts", "played around", "watched videos", "tutorial"
    ]
    # Beginner keywords (knows the word but not much)
    beginner_indicators = [
        "beginner", "new to this", "start from scratch", "basics", "no idea",
        "never heard", "what is this", "i don't know", "never studied", 
        "no prior", "never seen", "nothing"
    ]
    
    if any(ind in text_lower for ind in advanced_indicators):
        return "advanced"
    if any(ind in text_lower for ind in some_exposure_indicators):
        return "some_exposure"
    if any(ind in text_lower for ind in beginner_indicators):
        return "complete_beginner"
        
    # Ambiguous or extremely short input defaults to complete_beginner 
    # (Starting too easy allows positive acceleration; starting too hard causes frustration)
    return "complete_beginner"


# Deterministic Response Policies per State
RESPONSE_POLICIES = {
    TutorState.RECOVERY: {
        "max_sentences": 2,
        "max_concepts": 1,
        "allow_analogy": False,
        "allow_open_questions": False,
        "tone": "calm, supportive",
        "depth_level": "intro",
        "question_type": "none",
        "prompt_instructions": "Limit explanation to 1-2 ultra-simple, supportive sentences. Absolutely NO abstract analogies, NO questions/quizzes, and NO new concepts. Use daily physical items only if explaining."
    },
    TutorState.SIMPLIFIED: {
        "max_sentences": 3,
        "max_concepts": 1,
        "allow_analogy": True,  # Max 1
        "allow_open_questions": False,
        "tone": "warm, encouraging",
        "depth_level": "intro",
        "question_type": "mcq",
        "prompt_instructions": "Limit explanation to 2-3 simple sentences. Use maximum 1 concrete analogy based on daily physical items. Do not ask open-ended questions; use multiple-choice if asking."
    },
    TutorState.NORMAL: {
        "max_sentences": 5,
        "max_concepts": 2,
        "allow_analogy": True,
        "allow_open_questions": True,
        "tone": "conversational",
        "depth_level": "intermediate",
        "question_type": "open",
        "prompt_instructions": "Explain in 4-5 engaging, conversational sentences. You may use a clear analogy if helpful. Balance depth and simplicity, and close with a thoughtful question."
    },
    TutorState.CHALLENGE: {
        "max_sentences": 6,
        "max_concepts": 2,
        "allow_analogy": False,
        "allow_open_questions": True,
        "tone": "rigorous, technical",
        "depth_level": "advanced",
        "question_type": "guided",
        "prompt_instructions": "Provide a deep, rigorous explanation in 5-6 concise, highly technical sentences. Absolutely NO analogies. Challenge the student with advanced examples or deep reasoning questions."
    },
    TutorState.ASSESSMENT: {
        "max_sentences": 4,
        "max_concepts": 1,
        "allow_analogy": False,
        "allow_open_questions": False,
        "tone": "clear, objective",
        "depth_level": "intermediate",
        "question_type": "mcq",
        "prompt_instructions": "Limit explanation/feedback to 3-4 clear, objective sentences. Absolutely NO analogies. Focus entirely on assessing current understanding with objective quiz checking."
    }
}

# Known common analogy metaphors to block repetition
COMMON_METAPHORS = [
    "sandwich", "pizza", "librarian", "cards", "catalog", "piggy bank", "boxes", 
    "nesting dolls", "russian doll", "cookies", "bookshelf", "switch", "light bulb",
    "thermostat", "recipe", "soccer", "football", "highway", "traffic"
]

def split_into_sentences(text: str) -> List[str]:
    """
    Helper to split text into sentences using standard regex.
    Handles standard abbreviations to prevent splitting errors.
    """
    if not text:
        return []
    # Replace newlines with spaces and clean up double spaces
    text = text.replace("\n", " ").strip()
    text = re.sub(r'\s+', ' ', text)
    # Regex split that checks for . or ? or ! followed by space
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s', text)
    return [s.strip() for s in sentences if s.strip()]

def detect_metaphor_in_text(text: str) -> str:
    """
    Detects if any common metaphors are used in the generated response.
    Returns the first matching metaphor name or None.
    """
    text_lower = text.lower()
    for metaphor in COMMON_METAPHORS:
        # Match word boundaries for accuracy
        if re.search(r'\b' + re.escape(metaphor) + r'\b', text_lower):
            return metaphor
    return None

def is_overwhelmed_expression(text: str) -> bool:
    """
    Check if user text indicates cognitive overload.
    Extends ai_tutor_production's check to ensure perfect alignment.
    """
    text_lower = text.lower().strip()
    triggers = [
        "wth", "idk", "no clue", "lost", "confused", "too much", "overwhelming",
        "confusing", "makes no sense", "don't get it", "don't understand",
        "too fast", "stop", "slow down", "brain hurts", "stuck"
    ]
    if any(t in text_lower for t in triggers):
        return True
    
    # If the student says just "confused" or "confusing"
    if text_lower in ["confused", "confusing", "i am confused"]:
        return True
        
    return False

def update_tutor_state(
    session: dict, 
    user_input: str, 
    emotion: str, 
    evaluation: str, 
    classification: str, 
    intent: str
) -> dict:
    """
    Persistent Tutor State Machine transitions with:
    - Sustained emotional history smoothing
    - Level change cooldowns
    - Confidence/mastery thresholds
    
    Updates the session in-place and returns updated fields.
    """
    # Ensure session structure is fully populated
    session = ensure_session_structure(session)
    
    current_state = session.get("tutor_state", "normal")
    cooldown = session.get("level_change_cooldown", 0)
    emotional_history = session.get("sustained_emotional_history", [])
    
    # 1. Update sustained emotional history (keep last 5)
    emotional_history.append(emotion)
    if len(emotional_history) > 5:
        emotional_history = emotional_history[-5:]
    session["sustained_emotional_history"] = emotional_history
    
    # 2. Decrement cooldown if active
    if cooldown > 0:
        cooldown -= 1
        session["level_change_cooldown"] = cooldown

    # 3. Check for immediate critical override to RECOVERY
    overwhelmed = is_overwhelmed_expression(user_input) or intent == "refusal"
    
    if overwhelmed:
        print(f"[STATE-MACHINE] OVERWHELM DETECTED. Forcing immediate RECOVERY state transition.")
        if current_state != TutorState.RECOVERY.value:
            session["recovery_entries"] = session.get("recovery_entries", 0) + 1
        session["tutor_state"] = TutorState.RECOVERY.value
        session["level_change_cooldown"] = 3  # Lock in recovery for 3 turns to stabilize
        session["attempt_count"] = 0
        session["cognitive_load_score"] = 5
        return session
    
    # 4. If level change cooldown is active, check for early exit, else DO NOT change state
    if cooldown > 0:
        # Early exit from RECOVERY if they are no longer frustrated and did well or confirmed understanding
        if current_state == TutorState.RECOVERY.value and emotion not in ["frustrated", "very_frustrated"] and (evaluation in ["correct", "partial"] or intent == "positive_confirmation"):
            print(f"[STATE-MACHINE] Early exit from RECOVERY: Student recovered. Clearing cooldown.")
            session["recovery_exits"] = session.get("recovery_exits", 0) + 1
            session["level_change_cooldown"] = 0
            session["tutor_state"] = TutorState.SIMPLIFIED.value
            return session
            
        print(f"[STATE-MACHINE] Cooldown active ({cooldown} turns left). Locking state: {current_state}")
        return session

    # 5. Evaluate state transitions when cooldown is 0
    target_state = current_state
    
    # 5a. SUSTAINED EMOTIONAL STREAKS
    # Frustration streak (last 2 are a mix of frustrated/confused)
    frustration_streak = (
        len(emotional_history) >= 2 and 
        all(e in ["frustrated", "very_frustrated", "confused"] for e in emotional_history[-2:]) and
        any(e in ["frustrated", "very_frustrated"] for e in emotional_history[-2:]) # Require at least ONE frustrated to trigger full RECOVERY, otherwise it's just confusion
    )
    
    # If it's pure confusion (2 confused in a row), we can either trigger RECOVERY or let it hit SIMPLIFIED
    # But per requirements: "confused streak should also trigger RECOVERY or at least depth drop"
    # Let's make ANY 2 struggles trigger RECOVERY to be safe.
    struggle_streak = (
        len(emotional_history) >= 2 and 
        all(e in ["frustrated", "very_frustrated", "confused"] for e in emotional_history[-2:])
    )
    # Neutral/Positive streak (last 3 are neutral/engaged)
    recovery_streak = (
        len(emotional_history) >= 3 and 
        all(e in ["neutral", "engaged", "very_engaged"] for e in emotional_history[-3:])
    )
    # Confusion streak
    sustained_confusion = (
        len(emotional_history) >= 2 and 
        emotional_history[-1] == "confused" and 
        emotional_history[-2] == "confused"
    ) or classification == "confusion" or emotion == "confused"

    if struggle_streak:
        if current_state != TutorState.RECOVERY.value:
            print(f"[STATE-MACHINE] Struggle streak detected (mixed frustration/confusion). Transitioning to RECOVERY.")
            session["recovery_entries"] = session.get("recovery_entries", 0) + 1
            target_state = TutorState.RECOVERY.value
            session["level_change_cooldown"] = 3
    elif sustained_confusion:
        if current_state != TutorState.SIMPLIFIED.value and current_state != TutorState.RECOVERY.value:
            print(f"[STATE-MACHINE] Sustained confusion detected. Transitioning to SIMPLIFIED.")
            target_state = TutorState.SIMPLIFIED.value
            session["level_change_cooldown"] = 2  # Keep in simplified for at least 2 turns
    elif recovery_streak:
        if current_state in [TutorState.SIMPLIFIED.value, TutorState.RECOVERY.value]:
            print(f"[STATE-MACHINE] Recovery streak detected (3+ stable turns). Transitioning back to NORMAL.")
            if current_state == TutorState.RECOVERY.value:
                session["recovery_exits"] = session.get("recovery_exits", 0) + 1
            target_state = TutorState.NORMAL.value
            session["level_change_cooldown"] = 1

    elif intent == "question" or lesson_stage_quiz(session):
        # Trigger assessment if we are running quiz evaluations
        if current_state != TutorState.ASSESSMENT.value:
            print(f"[STATE-MACHINE] Quiz stage or assessment requested. Transitioning to ASSESSMENT.")
            target_state = TutorState.ASSESSMENT.value
            session["level_change_cooldown"] = 1

    elif evaluation == "correct":
        # Mastery-based gradual upgrades
        if current_state == TutorState.RECOVERY.value:
            print(f"[STATE-MACHINE] Correct response in RECOVERY. Moving up to SIMPLIFIED.")
            target_state = TutorState.SIMPLIFIED.value
            session["level_change_cooldown"] = 2
        elif current_state == TutorState.SIMPLIFIED.value:
            print(f"[STATE-MACHINE] Correct response in SIMPLIFIED. Moving up to NORMAL.")
            target_state = TutorState.NORMAL.value
            session["level_change_cooldown"] = 2
        elif current_state == TutorState.NORMAL.value and session.get("stable_teaching_level") == "advanced":
            print(f"[STATE-MACHINE] Correct response & advanced student. Moving up to CHALLENGE.")
            target_state = TutorState.CHALLENGE.value
            session["level_change_cooldown"] = 3

    # Fallback/Recovery from non-confused, non-frustrated states
    if target_state == current_state and current_state in [TutorState.RECOVERY.value, TutorState.SIMPLIFIED.value]:
        # If student has been stable and correct for a turn, gradually de-escalate back to normal
        if evaluation == "correct" or (emotion in ["engaged", "very_engaged", "neutral"] and not sustained_confusion):
            print(f"[STATE-MACHINE] Student stabilized. Gradually returning to NORMAL.")
            target_state = TutorState.NORMAL.value
            session["level_change_cooldown"] = 2

    session["tutor_state"] = target_state
    return session

def lesson_stage_quiz(session: dict) -> bool:
    """Helper to check if session is currently in a quiz/assessment stage."""
    return session.get("lesson_stage") == "quiz" or session.get("conversation_state") == "quiz"

def validate_response(response_text: str, state: str, session: dict) -> Tuple[bool, str]:
    """
    Pre-flight Response Validation Layer.
    Verifies that the generated response strictly follows:
    1. Grounding (answering immediately in the first sentence)
    2. Length limits (sentence counts per state policy)
    3. Analogy governance (cooldown, bans, repetition blockers)
    4. Concept overload limits
    
    Returns: (is_valid: bool, error_reason: str)
    """
    sentences = split_into_sentences(response_text)
    if not sentences:
        return False, "Response is empty."
        
    policy = RESPONSE_POLICIES.get(TutorState(state), RESPONSE_POLICIES[TutorState.NORMAL])
    max_sentences = policy["max_sentences"]
    allow_analogy = policy["allow_analogy"]
    
    # --- 1. Grounding Enforcement Check ---
    first_sentence = sentences[0].lower()
    # Filler templates to reject as first sentence
    filler_patterns = [
        "great question", "excellent question", "that's an interesting", "that's a good question",
        "let's first", "sure, let's explore", "i see you're asking", "awesome!", "wonderful question",
        "no worries at all", "exactly!", "spot on!", "great job!"
    ]
    
    # Exception: if it is recovery and we are comforting them, let empathetic responses pass,
    # but still enforce that they directly address confusion.
    # Otherwise, reject filler setups.
    if state != TutorState.RECOVERY.value:
        if any(filler in first_sentence for filler in filler_patterns):
            # Check if there is an actual direct answer in the sentence or if it's purely generic intro
            if len(first_sentence.split()) < 6 or first_sentence.startswith("great question") or first_sentence.startswith("let's first"):
                return False, f"First sentence is filler/greeting evasion: '{sentences[0]}'"

    # --- 2. Length (Sentence Count) Check ---
    if len(sentences) > max_sentences:
        return False, f"Response length ({len(sentences)} sentences) exceeds state policy max ({max_sentences})."

    # --- 3. Analogy Governance Check ---
    analogy_keywords = ["analogy", "metaphor", "imagine a", "think of a", "similar to a", "like a", "comparable to"]
    has_analogy_triggers = any(keyword in response_text.lower() for keyword in analogy_keywords)
    detected_metaphor = detect_metaphor_in_text(response_text)
    
    analogy_detected = has_analogy_triggers or (detected_metaphor is not None)
    
    # Cooldown check
    cooldown = session.get("analogy_cooldown", 0)
    
    if analogy_detected:
        if not allow_analogy:
            return False, f"Analogy used in state '{state}' which strictly prohibits analogies."
        
        if cooldown > 0:
            return False, f"Analogy used during active analogy cooldown ({cooldown} turns remaining)."
            
        if detected_metaphor:
            used_analogies = session.get("used_analogies", [])
            if detected_metaphor in used_analogies:
                return False, f"Repetitive analogy detected: Metaphor '{detected_metaphor}' was already used in this session."

    # --- 4. Concept Overload Check ---
    # Recovery or Simplified should never contain dense connective logic or too many transitions
    if state in [TutorState.RECOVERY.value, TutorState.SIMPLIFIED.value]:
        # Dense phrases indicating stacking concepts
        stacking_indicators = ["additionally,", "furthermore,", "in addition,", "moreover,", "on the other hand"]
        if any(ind in response_text.lower() for ind in stacking_indicators):
            return False, "Response introduces multiple concepts/transitions during overload."

    return True, ""

def update_analogy_tracking(response_text: str, session: dict) -> dict:
    """
    If the response uses an analogy, registers it in `used_analogies`
    and sets the `analogy_cooldown` to 4 turns. Decrements cooldown otherwise.
    """
    cooldown = session.get("analogy_cooldown", 0)
    used_analogies = session.get("used_analogies", [])
    
    detected_metaphor = detect_metaphor_in_text(response_text)
    analogy_keywords = ["analogy", "metaphor", "imagine a", "think of a", "similar to a", "like a", "comparable to"]
    has_analogy = any(keyword in response_text.lower() for keyword in analogy_keywords) or (detected_metaphor is not None)
    
    if has_analogy:
        # Set cooldown and record metaphor if found
        session["analogy_cooldown"] = 4
        if detected_metaphor and detected_metaphor not in used_analogies:
            used_analogies.append(detected_metaphor)
            session["used_analogies"] = used_analogies
            print(f"[ANALOGY-GOVERNANCE] Registered metaphor '{detected_metaphor}' and set cooldown to 4.")
    else:
        if cooldown > 0:
            session["analogy_cooldown"] = max(0, cooldown - 1)
            
    return session

def deterministic_fallback_trim(response_text: str, state: str) -> str:
    """
    Safe deterministic post-processing trim.
    Guarantees the response strictly meets length and filler constraints:
    1. Removes greeting filler from the first sentence if present.
    2. Truncates sentence count to state policy max.
    3. Reconstructs a clean response ending.
    """
    sentences = split_into_sentences(response_text)
    if not sentences:
        return "Let me break that down simply."
        
    policy = RESPONSE_POLICIES.get(TutorState(state), RESPONSE_POLICIES[TutorState.NORMAL])
    max_sentences = policy["max_sentences"]
    
    # 1. Strip greeting filler sentence if it is the first sentence
    filler_patterns = [
        "great question", "excellent question", "that's an interesting", "that's a good question",
        "let's first", "sure, let's explore", "i see you're asking", "awesome!", "wonderful question",
        "exactly!", "spot on!", "great job!"
    ]
    if len(sentences) > 1:
        first_sentence = sentences[0].lower()
        if any(filler in first_sentence for filler in filler_patterns):
            # If the first sentence is short greeting filler, strip it!
            if len(first_sentence.split()) < 7 or first_sentence.startswith("great question") or first_sentence.startswith("let's first"):
                print(f"[VALIDATION-FALLBACK] Stripping filler first sentence: '{sentences[0]}'")
                sentences = sentences[1:]

    # 2. Truncate to maximum sentences allowed by policy
    if len(sentences) > max_sentences:
        print(f"[VALIDATION-FALLBACK] Truncating response from {len(sentences)} to {max_sentences} sentences.")
        sentences = sentences[:max_sentences]
        
    # Reassemble
    trimmed_text = " ".join(sentences)
    return trimmed_text
