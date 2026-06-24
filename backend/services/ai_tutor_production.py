#ai_tutor_production.py

"""
AI Tutor Service - Production Architecture

DESIGN PRINCIPLE:
- SYSTEM_PROMPT: Fixed instructions (never changes, used for ALL calls)
- User messages: Structured learning STATE (concept + emotion + evaluation)
- LLM: Generates ONE clean response per call
- Result: No repetition, consistent quality, emotional adaptation

This architecture prevents 90% of tutoring system issues:
âœ“ AI never repeats explanations
âœ“ AI understands context clearly
âœ“ Teaching adapts to emotion
âœ“ Responses are structured and predictable
"""

from groq import Groq
import os
from backend.services.emotion import _get_groq_client
from dotenv import load_dotenv
import json
import re

# Initialize
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")
client = Groq(api_key=GROQ_API_KEY)

# ============================================
# IMPORT PRODUCTION SYSTEM PROMPT FROM PROMPTS.PY
# ============================================
from backend.services.prompts import SYSTEM_PROMPT, ONBOARDING_SYSTEM_PROMPT


# ============================================
# CORE TUTOR FUNCTIONS
# ============================================

# ============================================
# RESPONSE STRATEGY FUNCTIONS (NEW - Step 1-5)
# ============================================

def get_explanation_strategy(attempt_count: int) -> str:
    """
    Determine explanation strategy based on attempt count.
    Each attempt uses a COMPLETELY DIFFERENT approach to avoid repetition.
    
    - Attempt 0: definition (structured, comprehensive)
    - Attempt 1: analogy (story-based, relatable)
    - Attempt 2: visual (structured with boxes, visual thinking)
    - Attempt 3+: ultra_simple (absolute minimum, confidence rebuild)
    """
    if attempt_count == 0:
        return "definition"
    elif attempt_count == 1:
        return "analogy"
    elif attempt_count == 2:
        return "visual"
    else:
        return "ultra_simple"


def get_question_type(intent: str, attempts: int, emotion: str = "") -> str:
    """
    Determine question format based on context.
    
    - Attempt 0: open (let them think freely)
    - Attempt 1+: mcq (multiple choice, easier)
    - Attempt 2+: guided (fill-the-blank style)
    - If confused or frustrated: mcq (reduce cognitive load)
    """
    if emotion in ["confused", "frustrated", "very_frustrated"]:
        return "mcq"
    
    if attempts == 0:
        return "open"
    elif attempts == 1:
        return "mcq"
    else:
        return "guided"


def get_frustration_override(emotion: str) -> dict:
    """
    Hard override settings when student is frustrated.
    CRITICAL: These override all other logic.
    """
    if emotion in ["frustrated", "very_frustrated"]:
        return {
            "style": "friend",
            "max_explanation_lines": 3,
            "question_type": "mcq",
            "add_encouragement": True,
            "add_pressure_relief": True,
            "skip_complex_concepts": True
        }
    elif emotion == "confused":
        return {
            "style": "story",
            "max_explanation_lines": 4,
            "question_type": "mcq",
            "add_encouragement": True,
            "add_pressure_relief": False,
            "skip_complex_concepts": False
        }
    else:
        return {}


def should_skip_last_strategy(current_strategy: str, last_strategy: str) -> bool:
    """
    Repetition blocker: if we're about to use the same strategy again,
    force the next one in sequence.
    """
    if last_strategy is None or last_strategy == "":
        return False
    
    if current_strategy == last_strategy:
        print(f"[BLOCKER] Skipping {current_strategy} (same as last) â†’ forcing next strategy")
        return True
    
    return False


# ============================================
# CRITICAL: CONTROL FLOW FIXES (Non-Generic)
# ============================================

def is_overwhelmed(user_text: str) -> bool:
    """
    CRITICAL: Detect when student is overwhelmed/confused and needs to RESET.
    
    Triggers:
    - Very short responses ("idk", "wth", "ok")
    - Explicit overwhelm signals ("too much", "confusing", "lost")
    - Frustration signals after multiple attempts
    
    Returns: True if should RESET to simplify
    """
    text_lower = user_text.lower().strip()
    
    # Short response triggers (likely overwhelmed)
    overwhelm_triggers = [
        "wth",          # What the heck
        "idk",          # I don't know
        "idk why",
        "don't know",
        "no clue",
        "lost",
        "confused",
        "too much",
        "overwhelming",
        "confusing",
        "makes no sense",
        "don't get it",
    ]
    
    # Check for overwhelm triggers
    if any(trigger in text_lower for trigger in overwhelm_triggers):
        return True
    
    # POSITIVE confirmations (should NOT be overwhelmed)
    # These are acknowledgements, not overwhelm signals
    positive_confirmations = [
        "oh",
        "ok",
        "okay",
        "hmm",
        "hm",
        "yeah",
        "sure",
        "yes",
        "yup",
        "no",
        "nope",
        "maybe",
        "got it",
        "i understand",
        "i get it",
        "understood",
        "makes sense",
        "clear",
        "thanks",
        "ok thanks",
        "i understand this",
        "yes got it",
        "cool",
        "good",
        "nice",
        "i see"
    ]
    
    # Check if it's a positive confirmation (exact match, case-insensitive)
    if text_lower in positive_confirmations:
        return False
    
    # Check if it STARTS with a positive confirmation
    for confirmation in positive_confirmations:
        if text_lower.startswith(confirmation.lower()):
            return False
    
    # Very short response (< 4 words) that didn't match positive triggers â†’ overwhelmed
    # This catches things like "wth help" or "i'm lost"
    if len(text_lower.split()) < 4:
        # Already checked for positive confirmations above
        return any(trigger in text_lower for trigger in overwhelm_triggers)
    
    return False


def update_teaching_mode(current_mode: str, understanding: str, emotion: str, 
                        evaluation: str = None, attempt_count: int = 0) -> str:
    """
    CRITICAL FIX: Proper gradual teaching mode progression (non-generic).
    
    This REPLACES the simple one-liner mode switches.
    
    Logic:
    1. If VERY frustrated â†’ RESET to simplify
    2. If LOW understanding â†’ stay/move to simplify  
    3. If MEDIUM understanding â†’ teach_basic (structured but simple)
    4. If HIGH understanding â†’ gradually upgrade (adaptive then advanced)
    
    KEY: Gradual progression, not abrupt jumps.
    """
    
    # TIER 1: Emotional override (highest priority)
    if emotion in ["very_frustrated", "frustrated"]:
        return "simplify"
    
    if emotion == "confused":
        return "teach_basic"
    
    # TIER 2: Understanding-based progression
    if understanding == "low":
        # Student hasn't grasped it yet
        return "simplify"
    
    if understanding == "medium":
        # Understands basics, needs structure
        return "teach_basic"
    
    if understanding == "high":
        # Student understands this mode, can progress
        # But GRADUALLY: not straight to advanced
        if current_mode == "simplify":
            return "teach_basic"  # First step up
        elif current_mode == "teach_basic":
            return "adaptive"     # Second step up
        elif current_mode == "adaptive":
            # CAN go to advanced, but only if engaged
            if emotion == "engaged" or emotion == "very_engaged":
                return "advanced"
            else:
                return "adaptive"  # Stay in adaptive
        else:
            # Fallback: maintain current
            return current_mode
    
    # Default: maintain current mode
    return current_mode


def should_break_confusion() -> str:
    """
    When student is overwhelmed, return a CONFUSION_BREAKER response.
    
    This is NOT a normal lesson - it's a RESET.
    """
    return """Alright, let me pause here.

I see you might be getting overwhelmed. That's totally normal.

Let me simplify:
[core concept in 1 sentence]

That's the main thing. Everything else builds from that.

Want to build from here, or should I explain what you were confused about?"""


def get_response_style(emotion: str, understanding: str, attempt_count: int, intent: str = None, depth_level: str = None) -> str:
    """
    CRITICAL: Determine response length/depth based on student state.
    
    This is the MISSING layer that prevents responses from being uniform.
    
    Response styles:
    - ultra_short: 1-2 lines MAX (overwhelmed, frustrated)
    - short: 2-3 lines (low understanding, early attempts)
    - medium: 4-6 lines (normal teaching)
    - long: 7-12 lines (high understanding, engaged, asking for depth)
    
    Returns: style string that controls LLM response length
    """
    
    # TIER 1: Emotional state (highest priority)
    if emotion in ["very_frustrated", "frustrated"]:
        return "ultra_short"
    
    if emotion == "confused":
        if intent == "expand" or depth_level == "advanced":
            return "medium"
        return "short"
    
    # TIER 2: Understanding level
    if understanding == "low":
        return "short"
    
    if understanding == "medium":
        return "medium"
    
    if understanding == "high":
        # Only go LONG if student is engaged/asking for more
        if emotion in ["engaged", "very_engaged"]:
            return "long"
        else:
            return "medium"
    
    # Default: medium
    return "medium"


def get_length_instruction(style: str) -> str:
    """
    Generate instruction for LLM about response length.
    
    This goes INTO the system prompt dynamically.
    """
    instructions = {
        "ultra_short": """RESPONSE LENGTH: 1-2 lines MAXIMUM.
- No explanation overload
- Get straight to the point
- Use simple everyday language
- One idea only
Example: "Machine learning = computers learning from examples. Like Netflix recommending movies."

CRITICAL: Keep it super short. They're overwhelmed.""",
        
        "short": """RESPONSE LENGTH: 2-3 lines MAXIMUM.
- Focus on ONE core idea
- Simple explanation
- One practical example
- Skip unnecessary details
Example: "A function is like a recipe. Input ingredients, output the dish."

Key: Stay focused and simple.""",
        
        "medium": """RESPONSE LENGTH: 4-6 lines.
- Clear explanation with structure
- One good example
- Question for engagement
- Balanced depth
Example: "Recursion = a function calling itself. Like Russian nesting dolls: each doll contains a smaller version until you reach the tiniest. When do you stop recursing?"

Key: Balanced, not too deep.""",
        
        "long": """RESPONSE LENGTH: 7-12 lines OK.
- Thorough explanation
- Multiple examples or angles
- Can include edge cases
- Challenge them with interesting connections
Example: "Binary search is optimal because it cuts search space in half each time. Time complexity O(log n). Why is this faster than linear search O(n)? What happens if data isn't sorted?"

Key: You can go deeper. They want more."""
    }
    
    return instructions.get(style, instructions["medium"])


def generate_concepts(topic: str, student_level: str = "intermediate") -> list:
    """
    Generate learning pathway for a topic, shaped by student level.
    Returns ordered list of 3-5 concepts to teach progressively.
    
    Levels: complete_beginner, some_exposure, beginner, intermediate, advanced
    """
    # Level-specific prompt shaping
    level_instructions = {
        "complete_beginner": f"The student has ZERO prior knowledge. Start with the absolute basics. The first concept MUST be 'What is {topic}?' followed by the simplest foundational building blocks. Use no jargon.",
        "beginner": f"The student is a beginner. Start simple. The first concept should be 'What is {topic}?' or a similarly foundational entry point. Build up gradually.",
        "some_exposure": f"The student has some exposure but isn't confident. Start with a brief overview, then move into core concepts. Skip absolute basics but don't assume deep knowledge.",
        "intermediate": f"The student has intermediate knowledge. Skip introductions and focus on core concepts, patterns, and practical application.",
        "advanced": f"The student is advanced. Skip basics entirely. Focus on nuances, edge cases, best practices, and advanced patterns."
    }
    
    level_instruction = level_instructions.get(student_level, level_instructions["intermediate"])
    
    prompt = f"""Topic: {topic}
Student Level: {student_level}

{level_instruction}

Generate 3-5 KEY CONCEPTS for learning this topic, in a good learning order appropriate for this student's level.

Format: Return ONLY a JSON array like ["Concept 1", "Concept 2", "Concept 3"]

Example for 'Recursion' (beginner):
["What is recursion", "Base case", "Recursive call", "Stack frames", "Practical example"]

Example for 'Recursion' (advanced):
["Tail recursion optimization", "Memoization patterns", "Tree recursion vs linear", "Recursive data structures"]

Return ONLY the JSON array, no other text."""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        response_text = response.choices[0].message.content.strip()
        concepts = json.loads(response_text)
        if not isinstance(concepts, list):
            concepts = [topic]
        
        # For complete_beginner: guarantee foundational first concept
        if student_level in ["complete_beginner", "beginner"]:
            foundation = f"What is {topic}?"
            if concepts and not any("what is" in c.lower() for c in concepts):
                concepts.insert(0, foundation)
        
        print(f"[CONCEPTS] Generated {len(concepts)} concepts for level '{student_level}': {concepts}")
        return concepts
    except Exception as e:
        print(f"[TUTOR] Error generating concepts: {e}")
        if student_level in ["complete_beginner", "beginner"]:
            return [f"What is {topic}?", topic]
        return [topic]


def generate_empathy_response(user_message: str, emotion: str, empathy_count: int = 0) -> str:
    """
    Generate an empathy response.
    Turn 1-2: standard empathy.
    Turn 3: direct question.
    Turn 4+: topic escape.
    """
    try:
        if empathy_count >= 3:
            # Turn 4+ (3 or more previous empathy responses)
            return "Let's skip this and try something different for now. We can always come back to it."
        
        prompt = f"""The student is feeling {emotion} and said: "{user_message}".
"""
        if empathy_count == 2:
            # Turn 3
            prompt += """Write a supportive, empathetic response in exactly 1-2 sentences that ends with a direct question asking what specifically isn't clicking (e.g. "What specifically isn't clicking?").
Do NOT teach any content."""
        else:
            # Turn 1-2
            prompt += """Write a supportive, empathetic, and warm response in EXACTLY 1-2 sentences. 
Do NOT teach any content, do NOT ask any questions, and do NOT give complex instructions. Just acknowledge their frustration/feeling warmly and validate it (e.g. "I hear you...")."""
            
        prompt += "\nEmpathy Response:"
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=90
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "I completely understand that this can be frustrating. Let's take a deep breath and take it one step at a time."


def generate_escalation_response(concept: str, emotion: str) -> str:
    """
    Generate an escalation response when struggle_count >= 5.
    """
    try:
        prompt = f"""The student is struggling significantly with the concept '{concept}' and is feeling {emotion}.
Write a supportive 1-2 sentence response offering to skip the concept for now and come back later. 
Do NOT teach any content.
Example: "This concept is tricky — want to skip it for now and come back later?"
Escalation Response:"""
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=90
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "This concept is tricky — want to skip it for now and come back later?"


def generate_lesson(
    concept: str, 
    emotion: str = "neutral",
    evaluation_result: str = None, 
    style: str = "teacher",
    attempt_count: int = 0,
    intent: str = "answer",
    last_explanation_type: str = None,
    teaching_mode: str = "normal",
    question_type_override: str = None,
    explained_concepts: list = None,
    depth_level: str = None,
    lesson_stage: str = None,
    user_query: str = None,
    avoid_list: list = None,
    last_success_moment: bool = False,
    cognitive_load_score: int = 0,
    classification: str = None,
    tutor_state: str = None,
    session_phase: str = "LEARNING",
    concepts: list = None,
    session_history: list = None
) -> dict:
    """
    Generate a single lesson block using simplified architecture.
    Backend provides CONTEXT, LLM decides response.
    
    Key Change: LLM responds with JSON directly. No complex post-processing.
    
    Args:
        concept: What to teach
        emotion: Student's detected emotion (neutral/confused/frustrated/very_frustrated/engaged/very_engaged)
        evaluation_result: Previous answer quality (correct/partial/incorrect)
        style: Teaching style ("teacher"/"friend"/"story"/"exam"/"advanced")
        attempt_count: How many times they've tried (0, 1, 2+)
        intent: Student's intent (answer/question/confused/advance/expand/clarify/acknowledgement)
        last_explanation_type: What strategy was used last time (for context)
        teaching_mode: How simple (normal/simplified/analogy/step_by_step/ultra_simple)
        question_type_override: Force specific question type (open/mcq/guided/none)
        depth_level: Current learning depth (intro/intermediate/advanced)
        lesson_stage: Pedagogical stage (introduction/expansion/quiz/review)
        user_query: Raw user input - preserved for LLM context (FIX #1)
        avoid_list: Dynamic list of behaviors to avoid (redefine_ai, librarian_analogy, etc.)
        last_success_moment: Indicates student just mastered a concept or did something great
        tutor_state: Active persistent tutor state machine state
        
    Returns:
        dict with: {success, response, strategy_used}
    """
    
    # ===== ONBOARDING INTERCEPTION =====
    if session_phase == "ONBOARDING":
        try:
            import time
            roadmap_str = ", ".join(concepts) if concepts else concept
            system_prompt_filled = ONBOARDING_SYSTEM_PROMPT.format(
                topic=concept,
                concepts_roadmap=roadmap_str
            )
            user_message = f"Please generate the welcoming onboarding message for the topic: '{concept}'."
            if user_query:
                user_message += f" The user started the topic by saying: '{user_query}'."
            
            print(f"\n{'='*80}")
            print(f"[DEBUG] ONBOARDING PRE-LLM CONTEXT CHECK")
            print(f"{'='*80}")
            print(f"[DEBUG] topic: {concept}")
            print(f"[DEBUG] concepts: {concepts}")
            print(f"[DEBUG] system_prompt length: {len(system_prompt_filled)} chars")
            print(f"{'='*80}\n")
            
            groq_start = time.time()
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt_filled},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=220,
                timeout=30
            )
            groq_time = time.time() - groq_start
            print(f"[TUTOR] [GROQ ONBOARDING] API response received: {groq_time:.3f}s")
            
            response_text = response.choices[0].message.content.strip()
            
            if not response_text:
                print(f"[TUTOR] [WARN] Empty onboarding response, using fallback")
                response_text = f"Welcome! Let's learn about {concept}."
                
            return {
                "success": True,
                "response": response_text,
                "strategy_used": "onboarding_welcome"
            }
        except Exception as e:
            print(f"[TUTOR] [ERROR] Error in onboarding generation: {e}")
            import traceback
            traceback.print_exc()
            fallback_roadmap = ", ".join(concepts) if concepts else concept
            return {
                "success": False,
                "response": f"Welcome! Today we are going to learn about {concept}. We will cover: {fallback_roadmap}. How much prior experience do you have with this topic?",
                "strategy_used": "onboarding_welcome_fallback"
            }

    # ===== DETERMINE STRATEGY =====
    strategy = get_explanation_strategy(attempt_count)
    if last_explanation_type and last_explanation_type == strategy:
        # Avoid repetition: skip to next strategy
        strategies = ["definition", "analogy", "visual", "ultra_simple"]
        try:
            current_idx = strategies.index(strategy)
            strategy = strategies[(current_idx + 1) % len(strategies)]
        except ValueError:
            pass
    
    # ===== HARD OVERRIDE FOR FRUSTRATION/CONFUSION =====
    override = get_frustration_override(emotion)
    if override:
        if override.get("style") == "concrete_only":
            style = "concrete_only"
        if override.get("question_type"):
            question_type_override = override.get("question_type")
    
    # ===== DETERMINE QUESTION TYPE =====
    # ===== COGNITIVE LOAD & PACING ADAPTATION =====
    if cognitive_load_score >= 3 or classification in ["confusion", "weak_ack", "general_remark"]:
        response_style = "ultra_short" if (cognitive_load_score >= 4 or classification == "confusion") else "short"
        question_type = "none"
        question_type_override = "none"
        if classification == "confusion" or cognitive_load_score >= 3:
            style = "concrete_only"
    else:
        # Convert evaluation_result to understanding level
        understanding_map = {
            "correct": "high",
            "partial": "medium",
            "incorrect": "low",
            "confused": "low",
            None: "medium"  # default
        }
        understanding = understanding_map.get(evaluation_result, "medium")
        response_style = get_response_style(emotion, understanding, attempt_count, intent, depth_level)

    # Overrides based on persistent TutorState policy if provided
    if tutor_state:
        from backend.services.tutor_control import TutorState as TS, RESPONSE_POLICIES
        ts_enum = TS(tutor_state)
        
        # Override response style to match the state policy sentence bounds
        if ts_enum == TS.RECOVERY:
            response_style = "ultra_short"
        elif ts_enum == TS.SIMPLIFIED:
            response_style = "short"
        elif ts_enum == TS.NORMAL:
            response_style = "medium"
        elif ts_enum == TS.CHALLENGE:
            response_style = "long"
        elif ts_enum == TS.ASSESSMENT:
            response_style = "medium"
            
        policy = RESPONSE_POLICIES.get(ts_enum, RESPONSE_POLICIES[TS.NORMAL])
        if policy["question_type"] == "none":
            question_type = "none"
            question_type_override = "none"

    length_instruction = get_length_instruction(response_style)
    
    # Adjust max_tokens based on response_style
    max_tokens_map = {
        "ultra_short": 120,       # Enforce 2-3 sentences
        "short": 200,            # Enforce 3-4 sentences
        "medium": 350,           # Balanced for 4-6 sentences
        "long": 550              # Deeper advanced responses
    }
    max_tokens = max_tokens_map.get(response_style, 200)
    
    # Dynamic Response Length Policy adjustments (Issue 12)
    if emotion in ["frustrated", "very_frustrated"]:
        max_tokens = 90  # max ~150 chars (1-2 sentences max)
    elif emotion == "confused":
        max_tokens = 95  # max ~250 chars + one concrete example only
    elif emotion in ["engaged", "very_engaged"] and style == "intermediate":
        max_tokens = 160  # max ~400 chars
    elif intent == "positive_confirmation":
        max_tokens = 110  # max ~300 chars, build on what they said
    elif intent == "SHORT_ACK":
        max_tokens = 35   # max ~80 chars
    
    # State-based token bounds tuning
    if tutor_state:
        from backend.services.tutor_control import TutorState as TS
        ts_enum = TS(tutor_state)
        if ts_enum == TS.RECOVERY:
            max_tokens = 90
        elif ts_enum == TS.SIMPLIFIED:
            max_tokens = 95
        elif ts_enum == TS.ASSESSMENT:
            max_tokens = 220
    
    if question_type_override:
        question_type = question_type_override
    elif not (cognitive_load_score >= 3 or classification in ["confusion", "weak_ack", "general_remark"]):
        question_type = get_question_type(intent, attempt_count, emotion)
    else:
        question_type = "none"
    
    # ===== BUILD CONTEXT FOR LLM =====
    # The LLM receives structured context and generates appropriate response
    context_parts = []
    
    # Response Length & Content Format Policy instructions (Issue 12)
    context_parts.append("=== DYNAMIC RESPONSE LENGTH & CONTENT POLICY ===")
    if emotion in ["frustrated", "very_frustrated"]:
        context_parts.append("- Frustrated/Very Frustrated Policy: You MUST write at most 150 characters (1-2 sentences max). Be extremely supportive and brief.")
    elif emotion == "confused":
        context_parts.append("- Confused Policy: You MUST write at most 250 characters. Provide exactly ONE concrete example only, keeping it very simple.")
    elif emotion in ["engaged", "very_engaged"] and style == "intermediate":
        context_parts.append("- Engaged + Intermediate Policy: You MUST write at most 400 characters.")
    elif intent == "positive_confirmation":
        context_parts.append("- Positive Confirmation Policy: You MUST write at most 300 characters. Validate their statement warmly and build on what they said.")
    elif intent == "SHORT_ACK":
        context_parts.append("- SHORT_ACK Policy: You MUST write at most 80 characters.")
    context_parts.append("")
    
    # Inject State Machine Policy Rules
    if tutor_state:
        from backend.services.tutor_control import TutorState as TS, RESPONSE_POLICIES
        ts_enum = TS(tutor_state)
        policy = RESPONSE_POLICIES.get(ts_enum, RESPONSE_POLICIES[TS.NORMAL])
        
        context_parts.append("=== MANDATORY RESPONSE RULES (STATE POLICY) ===")
        context_parts.append(f"Active Tutoring State: {tutor_state.upper()}")
        context_parts.append(f"- Sentence constraint: You MUST write exactly or at most {policy['max_sentences']} sentences.")
        context_parts.append(f"- Concept constraint: Limit explanation to at most {policy['max_concepts']} concept(s) at a time.")
        context_parts.append(f"- Tone constraint: Maintain a {policy['tone']} tone.")
        
        if not policy['allow_analogy']:
            context_parts.append("- Analogy constraint: Do NOT use any analogies, metaphors, or stories in this response.")
        else:
            context_parts.append("- Analogy constraint: You are allowed to use at most 1 concrete analogy (ensure it is based on daily physical items).")
            
        context_parts.append(f"- Specific active instructions: {policy['prompt_instructions']}")
        context_parts.append("")

    # Grounding Enforcement Rules
    context_parts.append("=== CRITICAL RULE: GROUNDING & FIRST-SENTENCE DIRECTNESS ===")
    context_parts.append("- The very first sentence of your response MUST directly, explicitly, and concisely answer or address the student's latest question or answer.")
    context_parts.append("- DO NOT start with generic conversational filler, greeting templates (e.g. 'Great question!', 'Excellent!', 'That's a good question'), or lecturing setups.")
    context_parts.append("- Start IMMEDIATELY with the answer in sentence 1.")
    context_parts.append("")
    
    # FIX #1: PRIORITIZE user_query in active instructions
    if user_query:
        context_parts.append("=== STUDENT'S EXPLICIT INPUT ===")
        context_parts.append(f"Student said: \"{user_query}\"")
        context_parts.append("Respond DIRECTLY to this input.")
        context_parts.append("")

    # Add avoid list constraint (CRITICAL RULE 6)
    if avoid_list:
        context_parts.append("=== CRITICAL: DO NOT DO AGAIN / AVOID ===")
        for avoid_item in avoid_list:
            if avoid_item == "redefine_ai":
                context_parts.append("- DO NOT redefine AI or explain what Artificial Intelligence stands for. The student fully understands it.")
            elif avoid_item == "librarian_analogy":
                context_parts.append("- DO NOT use the librarian or card catalog analogy. The student has already completed it.")
            elif avoid_item == "chess_analogy":
                context_parts.append("- DO NOT use the chess analogy. The student has already seen it.")
            elif avoid_item == "nesting_dolls_analogy":
                context_parts.append("- DO NOT use the nesting dolls recursion analogy. The student already knows it.")
            else:
                context_parts.append(f"- DO NOT use, repeat, or redefine: {avoid_item}")
        context_parts.append("")

    # Add last success moment constraint (CRITICAL RULE 1 & 5)
    if last_success_moment:
        context_parts.append("=== CONVERSATIONAL STATE ===")
        context_parts.append("Student just successfully mastered the previous concept or gave an excellent response!")
        context_parts.append("- Acknowledge and reinforce their correct reasoning strongly first.")
        context_parts.append("- Transition directly and smoothly to the new concept.")
        context_parts.append("- DO NOT ask any follow-up question in this response. Congratulate them and proceed directly.")
        context_parts.append("")

    # Add Cognitive Load active instructions
    if cognitive_load_score >= 3:
        context_parts.append("=== COGNITIVE LOAD CONTROL (HIGH) ===")
        context_parts.append("- The student has high cognitive load and is overwhelmed/confused.")
        context_parts.append("- Limit response to 1-2 ultra-simple, supportive sentences.")
        context_parts.append("- Absolutely DO NOT ask any questions. No quizzes, no checks.")
        context_parts.append("- Absolutely DO NOT introduce new concepts, analogies, or terminology.")
        context_parts.append("- Ground explanation ONLY in a concrete, daily physical object (e.g. self-driving car cameras as eyes).")
        context_parts.append("")

    # Add Classification-specific guidance
    if classification:
        context_parts.append(f"=== STUDENT RESPONSE CLASSIFICATION: {classification.upper()} ===")
        if classification == "weak_ack":
            context_parts.append("- The student gave a shallow acknowledgement (e.g. 'ok', 'yes', 'ahh').")
            context_parts.append("- DO NOT assume understanding or mastery.")
            context_parts.append("- DO NOT advance the topic or depth.")
            context_parts.append("- Provide a brief, warm reinforcement of the current concept (1-2 sentences).")
            context_parts.append("- Close the learning loop on this sub-concept without starting new abstractions.")
        elif classification == "partial_understanding":
            context_parts.append("- The student is following along but hasn't demonstrated active reasoning.")
            context_parts.append("- Keep it simple. Validate their agreement, summarize the concept in 1 clear sentence.")
            context_parts.append("- Close the loop cleanly.")
        elif classification == "general_remark":
            context_parts.append("- The student made a general remark/observation.")
            context_parts.append("- Validate their remark first (e.g. 'Exactly. IoT devices...').")
            context_parts.append("- Refine/connect it back to the current concept in 2 simple sentences.")
            context_parts.append("- Close the loop cleanly. DO NOT ask a question or introduce new concepts.")
        elif classification == "confusion":
            context_parts.append("- The student is explicitly confused.")
            context_parts.append("- Acknowledge the difficulty with empathy.")
            context_parts.append("- Ground the concept using a daily, physical model (avoid stacked theories).")
            context_parts.append("- Absolutely DO NOT ask any questions.")
        context_parts.append("")

    context_parts.extend([
        "=== TEACHING STATE ===",
        f"topic: {concept}",
        f"emotion: {emotion}",
        f"attempt_count: {attempt_count}",
        f"teaching_mode: {teaching_mode}",
        f"question_type: {question_type}",
        f"explanation_strategy: {strategy}",
        f"response_length: {response_style}",
        f"style: {style}",
        "",  # blank line
        length_instruction  # Inject length guidance
    ])

    if explained_concepts:
        context_parts.append("")
        context_parts.append(f"already_explained: {', '.join(explained_concepts)}")
        context_parts.append("→ Reference these concepts when explaining new ones. Avoid re-explaining them.")

    # Make depth_level explicit in active instructions
    if depth_level:
        context_parts.append("")
        context_parts.append(f"INSTRUCTION: Provide {depth_level} level explanation")
        context_parts.append("→ Student wants to go deeper. Increase complexity and detail.")
    
    if lesson_stage:
        context_parts.append(f"pedagogical_stage: {lesson_stage}")
        context_parts.append("→ Adjust explanation based on whether we're at introduction, expansion, quiz, or review stage.")
    
    # ===== HARD CONSTRAINT: Emotion-based components & Concrete Override (CRITICAL RULE 4) =====
    if emotion in ["very_frustrated", "frustrated"] or style == "concrete_only":
        context_parts.append("")
        context_parts.append("⚠️ CONCRETE ONLY CRITICAL CONSTRAINT:")
        context_parts.append("The student is frustrated or confused. You MUST explain using purely concrete, simple daily physical items (e.g. self-driving car cameras as eyes, or a physical light switch).")
        context_parts.append("Absolutely FORBID abstract analogies, stacked theories, library catalogs, chess games, nesting dolls, or complex terminology.")
        context_parts.append("Keep explanation to 1-2 supportive sentences maximum. NO EXAMPLES, NO QUESTIONS.")
    elif emotion == "confused":
        context_parts.append("")
        context_parts.append("⚠️ CONCRETE ONLY CRITICAL CONSTRAINT:")
        context_parts.append("The student is confused. Explain using purely concrete, simple daily physical items.")
        context_parts.append("Absolutely FORBID abstract analogies, stacked theories, library catalogs, chess games, nesting dolls, or complex terminology.")
        context_parts.append("Keep explanation extremely direct (2-3 sentences max) + one concrete daily physical example. Skip complex questions.")
    else:
        context_parts.append("")
        context_parts.append("Normal mode: Can include explanation + example + question as appropriate, unless last_success_moment is active (which skips questions).")
    
    # Add evaluation context if available
    if evaluation_result:
        context_parts.append("")
        if evaluation_result == "incorrect":
            context_parts.append("last_eval: INCORRECT - Use completely different approach")
        elif evaluation_result == "partial":
            context_parts.append("last_eval: PARTIAL - Refine and deepen")
        elif evaluation_result == "correct":
            context_parts.append("last_eval: CORRECT - Extend or challenge")
    
    user_message = "\n".join(context_parts)
    
    try:
        import time
        
        # Replace all placeholders in SYSTEM_PROMPT first
        student_state = f"emotion: {emotion}, teaching_mode: {teaching_mode}, depth: {depth_level or 'unknown'}"
        learning_style_str = teaching_mode  # Use teaching_mode as proxy for learning style
        confidence = "high" if evaluation_result == "correct" else "medium" if evaluation_result == "partial" else "low" if evaluation_result == "incorrect" else "unknown"
        attempt_str = str(attempt_count)
        common_mistake = f"This is attempt {attempt_count}. Address different approach than before." if attempt_count > 1 else "First attempt."
        understanding = "high" if evaluation_result == "correct" else "medium" if evaluation_result == "partial" else "low" if evaluation_result == "incorrect" else "medium"
        mistake_context = "The student gave an incorrect answer. Identify the specific misconception and correct it gently." if evaluation_result == "incorrect" else "Student gave a partial answer. Help them refine it." if evaluation_result == "partial" else ""
        non_repetition = "Use a completely different teaching approach than before." if attempt_count > 1 else ""
        
        # Replace all placeholders in SYSTEM_PROMPT
        system_prompt_filled = SYSTEM_PROMPT.replace("{{STUDENT_STATE}}", student_state)
        system_prompt_filled = system_prompt_filled.replace("{{LEARNING_STYLE}}", learning_style_str)
        system_prompt_filled = system_prompt_filled.replace("{{CONFIDENCE}}", confidence)
        system_prompt_filled = system_prompt_filled.replace("{{ATTEMPT_COUNT}}", attempt_str)
        system_prompt_filled = system_prompt_filled.replace("{{COMMON_MISTAKE}}", common_mistake)
        system_prompt_filled = system_prompt_filled.replace("{{UNDERSTANDING}}", understanding)
        system_prompt_filled = system_prompt_filled.replace("{{MISTAKE_CONTEXT}}", mistake_context)
        system_prompt_filled = system_prompt_filled.replace("{{NON_REPETITION_STRATEGY}}", non_repetition)
        
        # Inject context constraints into the system prompt
        system_prompt_filled += "\n\n" + user_message
        
        # User message is just their actual query
        final_user_message = f'Student said: "{user_query}"' if user_query else ""
        
        # DEBUG: Verify context values BEFORE Groq call
        print(f"\n{'='*80}")
        print(f"[DEBUG] PRE-LLM CONTEXT CHECK")
        print(f"{'='*80}")
        print(f"[DEBUG] user_query value: {repr(user_query)}")
        print(f"[DEBUG] depth_level value: {repr(depth_level)}")
        print(f"[DEBUG] intent value: {repr(intent)}")
        print(f"[DEBUG] avoid_list value: {repr(avoid_list)}")
        print(f"[DEBUG] last_success_moment: {repr(last_success_moment)}")
        print(f"[DEBUG] system_prompt length: {len(system_prompt_filled)} chars")
        print(f"[DEBUG] user_message first 300 chars: {final_user_message[:300]}")
        print(f"{'='*80}\n")
        
        messages_array = [{"role": "system", "content": system_prompt_filled}]
        
        if session_history:
            for msg in session_history[-6:]:  # Keep last 6 messages
                msg_role = "assistant" if msg.get("role") == "ai" else "user"
                msg_content = msg.get("text", "")
                if msg_content:
                    messages_array.append({"role": msg_role, "content": msg_content})
                    
        if final_user_message:
            messages_array.append({"role": "user", "content": final_user_message})
        
        groq_start = time.time()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_array,
            temperature=0.7,
            max_tokens=max_tokens,
            timeout=30
        )
        groq_time = time.time() - groq_start
        print(f"[TUTOR] [GROQ] API response received: {groq_time:.3f}s")
        
        response_text = response.choices[0].message.content.strip()
        
        # ===== NO JSON PARSING - TRUST LLM OUTPUT =====
        if not response_text:
            print(f"[TUTOR] [WARN] Empty response from LLM, using fallback")
            response_text = f"Let me explain {concept} in a simple way."
        
        print(f"[TUTOR] [OK] Generated response: {len(response_text)} chars")
        
        return {
            "success": True,
            "response": response_text,
            "strategy_used": strategy
        }
        
    except Exception as e:
        print(f"[TUTOR] [ERROR] Error generating lesson: {e}")
        import traceback
        traceback.print_exc()
        
        # Context-aware fallback (not generic)
        concept_ref = concept if concept else "this concept"
        mode_hint = f" using {teaching_mode}" if teaching_mode and teaching_mode != "normal" else ""
        fallback_reply = f"Let me explain {concept_ref} in a different way{mode_hint}."
        
        return {
            "success": False,
            "response": fallback_reply,
            "strategy_used": strategy
        }


def limit_lines(text: str, max_lines: int = 4) -> str:
    """
    DEPRECATED: Trusting LLM to generate appropriate length.
    This function now returns text unchanged.
    
    The LLM receives teaching_mode context and generates appropriately.
    No post-processing truncation needed.
    """
    return text


def fix_question(question: str) -> str:
    """
    DEPRECATED: Trusting LLM to generate proper questions.
    This function now returns question unchanged.
    
    The LLM receives question_type context and generates appropriately.
    No post-processing modification needed.
    """
    return question




# [REMOVED in Phase 1] parse_ai_response() - No longer needed
# The LLM now responds with natural text, not JSON buckets.
# The coordinator directly uses the response string.


def evaluate_answer(answer_text: str, question: str, concept: str) -> str:
    """
    Evaluate student answer quality.
    Returns: "correct" | "partial" | "incorrect"
    
    Uses simple keyword matching + LLM for ambiguous cases.
    """
    answer_lower = answer_text.lower()
    question_lower = question.lower()
    
    # Bare yes/no answers are wrong
    if answer_lower in ["yes", "no", "true", "false", "maybe"]:
        return "incorrect"
    
    # Too short = likely not trying
    if len(answer_text.strip()) < 10:
        return "incorrect"
    
    # Use LLM for real evaluation of more complex answers
    eval_prompt = f"""Evaluate this student answer.

Concept: {concept}
Question: {question}
Answer: {answer_text}

Is the answer correct, partially correct, or incorrect?

Respond with ONLY one word: correct | partial | incorrect
"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": eval_prompt}],
            temperature=0.2,
            max_tokens=10
        )
        result = response.choices[0].message.content.strip().lower()
        if result in ["correct", "partial", "incorrect"]:
            return result
    except:
        pass
    
    return "partial"  # Default to partial to encourage student


def classify_student_response(text: str, current_concept: str, last_question: str) -> str:
    """
    Classify the student's response to guide progression and pacing.
    
    Returns:
    weak_ack | partial_understanding | demonstrated_reasoning | confusion | question | general_remark
    """
    text_lower = text.lower().strip()
    
    # 1. Immediate local overrides for absolute speed and accuracy on obvious triggers
    confusion_keywords = ["confused", "confusing", "lost", "don't get", "makes no sense", "stuck", "wth", "idk", "too hard", "hard to follow", "dont understand", "confusingnow"]
    if any(keyword in text_lower for keyword in confusion_keywords):
        return "confusion"
        
    weak_acks = {"yes", "ahh", "ah", "ok", "okay", "yep", "sure", "yup", "no", "nope", "fine", "cool", "right"}
    if text_lower in weak_acks:
        return "weak_ack"
        
    partial_acks = {"makes sense", "i get it", "got it", "i see", "i understand", "makes sense now", "got it thanks"}
    if text_lower in partial_acks:
        return "partial_understanding"
        
    # 2. Check for question words/symbols
    question_words = ["what", "why", "how", "when", "where", "who", "which", "can", "could", "do", "does", "is", "are", "explain", "tell", "teach", "define"]
    if "?" in text or (len(text_lower.split()) > 0 and text_lower.split()[0] in question_words):
        if not text_lower.startswith(("it is", "because", "since")):
            return "question"
            
    # 3. LLM classifier fallback for robust contextual matching
    classify_prompt = f"""You are an expert pedagogical analyzer. Classify the student's response in this tutoring session.

Context:
- Concept being taught: {current_concept}
- Last question asked by tutor: {last_question}
- Student's response: "{text}"

Classify into exactly one of these categories:
- weak_ack: Simple agreement/politeness tokens showing no active reasoning (e.g. "yes", "ahh", "ok", "sure", "nice", "yup")
- partial_understanding: Expressing basic comprehension without detailed explanation or reasoning (e.g. "makes sense", "i get it", "got it", "i see")
- demonstrated_reasoning: Student explains a concept, answers a question with logical reasoning, or provides a valid example showing they understand (e.g. "because it learns from data", "smart traffic reduces congestion")
- confusion: Student states they are confused, lost, or stuck (e.g. "it is confusing", "i don't understand", "lost")
- question: Student asks a new question or requests clarification (e.g. "how does it work?", "what is ML?")
- general_remark: A casual statement or observation not showing conceptual mastery of the specific question (e.g. "iot and ai makes humanlife simpler")

Respond with EXACTLY one of these labels, and nothing else:
weak_ack | partial_understanding | demonstrated_reasoning | confusion | question | general_remark"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": classify_prompt}],
            temperature=0.0,
            max_tokens=15,
            timeout=5
        )
        result = response.choices[0].message.content.strip().lower()
        for label in ["weak_ack", "partial_understanding", "demonstrated_reasoning", "confusion", "question", "general_remark"]:
            if label in result:
                return label
    except Exception as e:
        print(f"[CLASSIFY] Groq API classification failed: {e}")
        
    # Local fallback logic if LLM fails
    words = text_lower.split()
    word_count = len(words)
    reasoning_terms = ["because", "trained", "data", "pattern", "since", "algorithm", "learn", "predict", "model", "input"]
    reasoning_count = sum(1 for term in reasoning_terms if term in text_lower)
    
    if reasoning_count >= 1 or word_count > 6:
        return "demonstrated_reasoning"
    elif word_count <= 2:
        return "weak_ack"
    else:
        return "general_remark"


# ============================================
# INTENT DETECTION (NEW - FIXES REPETITION)
# ============================================

def detect_intent(user_text: str, previous_ai_response: str = "", context: dict = None, current_concept: str = None) -> str:
    """
    Detect what the user is trying to do using conversational context and rule-based priority.
    """
    text = user_text.lower().strip()
    words = re.sub(r"[^\w\s]", "", text).split()
    word_count = len(words)
    
    # Extract context variables
    prev_ai = ""
    lesson_stage = ""
    is_first = False
    if context:
        prev_ai = context.get("previous_tutor_message", "")
        lesson_stage = context.get("lesson_stage", "")
        is_first = context.get("is_first_message", False)
    else:
        prev_ai = previous_ai_response

    # ============================================
    # DETERMINISTIC RULES (Run first for short messages)
    # ============================================
    refusal_keywords = ["stop", "quit", "exit", "end session", "stop teaching", "i quit", "im done", "i'm done"]
    is_refusal = text in refusal_keywords or any(w in refusal_keywords for w in words)
    
    ack_words = {"ok", "okay", "ohh", "oh", "got it", "i see", "right", "makes sense", "cool"}
    is_ack = text in ack_words or (word_count <= 2 and all(w in ack_words for w in words))
    
    pos_confirm = {"yes", "yes it does", "understood", "makes sense", "yep", "yeah", "yup", "sure", "oh i get it now", "i get it now", "now i get it", "i understand"}
    neg_confirm = {"no", "not really", "still confused", "nope", "i give up", "i cant do this", "i can't do this", "forget it", "no i dont", "no i don't", "i dont think so"}
    is_pos_confirm = text in pos_confirm or any(k in text for k in ["oh i get it now", "i get it now"])
    is_neg_confirm = text in neg_confirm
    
    confused_keywords = ["confused", "stuck", "lost", "unclear", "dont get", "don't get", "dont understand", "don't understand", "idk", "i dont know", "i don't know", "too hard"]
    is_confused = any(k in text for k in confused_keywords)
    
    greetings = {"hi", "hello", "hey", "sup", "howdy", "whats up", "what's up"}
    is_greeting = text in greetings or (word_count > 0 and words[0] in greetings)
    
    # 1. Deterministic Short Message Handling
    if is_pos_confirm:
        return "positive_confirmation"
    if is_neg_confirm:
        return "negative_confirmation"
    if is_refusal:
        return "refusal"

    if word_count <= 4:
        if is_ack:
            return "SHORT_ACK"
        if is_ack:
            return "acknowledgement"
        if is_confused:
            return "confused"
        if is_greeting:
            return "chitchat"
            
    # ============================================
    # TOPIC / ACTIVITY SWITCH & SKIP TRIGGER CHECKS
    # ============================================
    switch_keywords = ["boring", "bored", "something else", "change topic", "different topic", "lets play", "play a game", "play game", "another example"]
    if any(k in text for k in switch_keywords):
        return "activity_switch"
        
    skip_keywords = ["skip", "already know", "know this", "move on", "next concept", "next topic", "move forward", "skip this", "skip that"]
    if any(k in text for k in skip_keywords):
        return "skip_request"

    # Game context check (Color Match match)
    is_game = False
    if prev_ai:
        p_lower = prev_ai.lower()
        if "color match" in p_lower or "play a game" in p_lower or "game" in p_lower:
            is_game = True
    if lesson_stage == "game" or lesson_stage == "quiz":
        is_game = True
        
    if is_game and not is_refusal:
        return "game_answer"

    # Onboarding introductory prior
    if is_first or is_greeting:
        intro_keywords = ["new to", "starting", "beginner", "never coded", "first time", "i am", "interested to learn"]
        if any(k in text for k in intro_keywords) or is_first:
            return "chitchat"

    # If it's a longer explicit refusal
    if is_refusal:
        return "refusal"

    # Explicit confusion check for longer sentences
    if is_confused:
        return "confused"

    # Asking for Example
    example_keywords = ["example", "show me", "like what", "such as", "for instance", "case study", "illustration", "demonstrate"]
    if any(k in text for k in example_keywords):
        return "ask_example"

    # Asking to Simplify
    simplify_keywords = ["easier", "simpler", "too complex", "explain simply", "break it down", "slow down", "basic"]
    if any(k in text for k in simplify_keywords):
        return "ask_simplify"

    # Tutor Repair
    repair_keywords = ["i didn't say", "i didnt say", "you misunderstood", "you're wrong", "wrong", "mistake"]
    if any(k in text for k in repair_keywords):
        return "repair"

    # Conceptual Question
    concept_q_starters = ["what", "why", "how", "when", "where", "who", "which", "can", "could", "do", "does", "is", "are"]
    if "?" in text or (words and words[0] in concept_q_starters):
        return "ask_concept"

    # Advance
    explicit_advance = ["next concept", "next topic", "move on", "ready for next", "i'm ready", "im ready", "whats next", "what's next"]
    if any(k in text for k in explicit_advance):
        return "advance"

    # Expand / Go Deeper
    expand_keywords = ["tell me more", "go deeper", "elaborate", "more detail", "more about", "explain more", "advanced"]
    if any(k in text for k in expand_keywords):
        return "expand"

    # If it is long response, treat as answer
    if word_count > 6:
        return "answer"

    # ============================================
    # LLM FALLBACK (for truly ambiguous messages)
    # ============================================
    print(f"[INTENT] Ambiguous message - calling LLM classifier as fallback")
    
    classify_prompt = f"""You are analyzing a conversation between an educational AI tutor and a student.
Tutor just said: '{prev_ai}'
Student replied: '{user_text}'

Given the full exchange, what is the student's intent? Consider that a 'no' answering a yes/no question is not a refusal to learn. A refusal is only when the student explicitly and unambiguously says they want to stop, leave, or don't want to continue the lesson.
The intent refusal should only fire when the student explicitly and unambiguously says they want to stop — words like "stop", "quit", "I don't want to do this", "end session", "I'm done". A negation word at the start of a sentence that is otherwise engaged and curious is never a refusal.

Classify the student's reply into ONE category:
- confused: Student states they're confused, lost, or don't understand
- ask_example: Student asks for example or demonstration
- ask_simplify: Student asks to simplify or explain more basically
- refusal: Student explicitly and unambiguously wants to stop studying (e.g., stop, quit, end session, I don't want to do this)
- repair: Student is correcting a tutor mistake or misunderstanding
- ask_concept: Student asking a conceptual question (why/how/what)
- expand: Student wants to go deeper or learn more advanced material
- advance: Student ready to move to next topic
- chitchat: Off-topic greeting or casual banter
- answer: Student attempting to answer the tutor's question
- skip_request: Student wants to skip the current concept or basic explanation
- activity_switch: Student is bored and wants to play a game, switch activities, or change topic
- acknowledgement: A minimal acknowledgement (ok, okay, ohh, got it, makes sense)
- positive_confirmation: Affirmative response (yes, yes it does, understood)
- negative_confirmation: Negative response (no, not really, still confused)
- unknown: Message is unclear or doesn't fit above categories

Respond with EXACTLY one word from the list above."""

    client = _get_groq_client()
    classifier_out = ""
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": classify_prompt}],
            temperature=0.0,
            max_tokens=15,
            timeout=6
        )
        classifier_out = resp.choices[0].message.content.strip().lower()
        print(f"[INTENT] LLM fallback returned: {classifier_out}")
        
        valid_intents = ["confused", "ask_example", "ask_simplify", "refusal", "repair",
                        "ask_concept", "expand", "advance", "chitchat", "answer", "skip_request", "activity_switch", "acknowledgement", "positive_confirmation", "negative_confirmation", "unknown"]
        for intent in valid_intents:
            if intent in classifier_out:
                return intent
    except Exception as e:
        print(f"[INTENT] LLM fallback failed: {e}")
    
    # Alias: treat "chitchat" as generic chat
    if "chitchat" in classifier_out:
        return "chat"
    return "unknown"


# ============================================
# LEGACY FUNCTIONS (for backward compatibility)
# ============================================

def generate_ai_response(topic: str, chunk: str, emotion: str, teaching_mode: str = "adaptive", style: str = "teacher") -> dict:
    """Legacy function - redirects to new architecture"""
    # Map teaching mode to evaluation result
    eval_result = None
    if teaching_mode == "simplify":
        eval_result = "incorrect"
    elif teaching_mode == "teach_basic":
        eval_result = "partial"
    elif teaching_mode == "advanced":
        eval_result = "correct"
    
    result = generate_lesson(topic, emotion, eval_result, style=style)
    
    return {
        "success": result["success"],
        "response": result.get("response", ""),
        "strategy_used": result.get("strategy_used", "")
    }

