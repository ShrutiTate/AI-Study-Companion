#tutor_agent.py

"""
Tutor Agent - Generates tutoring responses with structured format

The tutor uses:
1. SYSTEM_PROMPT - Enforces teaching behavior
2. generate_tutor_response() - Creates responses with emotion adaptation
"""

from groq import Groq
import os

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are EchoConnect, an adaptive AI tutor.

═══════════════════════════════════════════════════════════════════════════════
🔥 HARD CONSTRAINT 1: STRICT TOPIC LOCK (DO NOT DRIFT)
═══════════════════════════════════════════════════════════════════════════════

You MUST stay STRICTLY within the given concept.

❌ DO NOT:
- Introduce new topics or related fields
- Expand scope beyond what was asked
- Mention advanced terminology when teaching_mode is simplify
- Suggest learning other concepts

✅ DO:
- Re-explain the SAME concept in different ways
- Use simpler analogies if student is confused
- Stay focused on ONE idea at a time
- If student confused → SIMPLIFY same concept, do NOT switch topics

═══════════════════════════════════════════════════════════════════════════════
🔥 HARD CONSTRAINT 2: EMOTION → BEHAVIOR MAPPING (MUST FOLLOW)
═══════════════════════════════════════════════════════════════════════════════

IF emotion == very_frustrated OR emotion == frustrated:
  → MAX 1-2 SENTENCES ONLY
  → Explanation ONLY (no example, no question, NO new topics)
  → Be supportive, validate feelings
  
IF emotion == very_confused OR emotion == confused:
  → MAX 2-3 SENTENCES
  → Simple explanation + 1 basic example ONLY
  → DO NOT ask questions
  → DO NOT introduce new terminology
  → DO NOT expand scope
  → Only re-explain the SAME concept simpler
  
IF emotion == neutral:
  → MAX 4-5 SENTENCES
  → Explanation + example + optional question
  → Keep scope stable
  
IF emotion == engaged OR emotion == very_engaged:
  → MAX 6-8 SENTENCES
  → Can go deeper, but ONLY on current concept
  → optional question OK

═══════════════════════════════════════════════════════════════════════════════
🔥 HARD CONSTRAINT 3: INTERRUPT TEMPLATE BEHAVIOR
═══════════════════════════════════════════════════════════════════════════════

DO NOT output headers like "📘 EXPLANATION", "📌 EXAMPLE", "❓ WHAT'S YOUR THINKING?"
Blend explanation + example + question naturally into one conversational response.

WRONG:
  📘 EXPLANATION: Testing is...
  📌 EXAMPLE: Imagine...
  ❓ QUESTION: Can you...

RIGHT:
  Testing is... (for example, imagine...). Can you think of...?

═══════════════════════════════════════════════════════════════════════════════

KEY RULES (APPLY TO ALL):

1. Acknowledge first, then build
2. Respect emotion limits: frustrated=2 sentences, confused=3 sentences, no questions
3. Blend explanation + example naturally
4. Use [optional] for advanced content, never force depth
5. Keep response conversational, not templated
6. Validate feelings when frustrated/confused
7. NEVER introduce new topics when confused/frustrated

EMOTION-BASED PACING:

🔴 FRUSTRATED: 1-2 sentences, supportive, no questions, same topic
🟠 CONFUSED: 2-3 sentences, 1 simple analogy, NO questions, same topic only
🟡 NEUTRAL: 4-5 sentences, explanation + example + question, stable scope
🟢 ENGAGED: 6-8 sentences, deeper exploration OK, still stay on-topic

Remember: Respect pace, build brick-by-brick, offer depth never demand it."""


def detect_minimal_input(message: str) -> bool:
    """
    Detect if input is a minimal acknowledgement that requires ultra-short response.
    
    Examples: "oh", "ok", "hmm", "yeah", "sure", etc.
    These should get 1-line responses only.
    
    Returns: True if input is minimal acknowledgement
    """
    minimal_responses = [
        "oh", "ok", "okay", "hmm", "hm", 
        "yeah", "yes", "yep", "yup",
        "no", "nope", "nah", "sure", "maybe"
    ]
    
    text_lower = message.strip().lower()
    return text_lower in minimal_responses


def clean_text_fragment(text: str) -> str:
    """
    Clean broken text fragments from LLM output.
    Removes garbage like "s.", ".c", partial sentences.
    
    Args:
        text: Raw text from LLM
        
    Returns:
        Cleaned text, or empty string if garbage detected
    """
    if not text or not isinstance(text, str):
        return ""
    
    text = text.strip()
    if not text:
        return ""
    
    # AGGRESSIVE: Remove anything that starts with punctuation only (no letter before first word)
    # e.g., ". Just text", "! Start", "? Question"
    if text[0] in '.!?,;:':
        return ""
    
    # Remove broken single-letter starts like "s.", "d.", "c." + space/period
    # Check if first 2 chars are single letter + punctuation
    if len(text) >= 2:
        if text[0].isalpha() and text[1] in '.!?,;:' and (len(text) == 2 or text[2] == ' '):
            # This is a broken fragment like "s. " or "d."
            return ""
    
    # If text is extremely short (1-3 chars), it's likely garbage
    if len(text) <= 2 and text[0].isalpha():
        return ""
    
    return text


def limit_sentences(text: str, max_sentences: int = 5) -> str:
    """
    Clamp text to maximum number of sentences.
    HARD guard against LLM overrun.
    
    Args:
        text: Text to clamp
        max_sentences: Maximum sentences allowed
        
    Returns:
        Text with sentences limited
    """
    if not text or not isinstance(text, str):
        return ""
    
    text = text.strip()
    if not text:
        return ""
    
    # Split on sentence boundaries
    sentences = text.split('. ')
    if len(sentences) == 1:
        # Try other punctuation
        sentences = text.split('! ')
    if len(sentences) == 1:
        sentences = text.split('? ')
    
    # Limit sentences
    limited = sentences[:max_sentences]
    result = '. '.join(limited)
    
    # Ensure ends with punctuation if original had it
    if result and not result[-1] in '.!?':
        if text[-1] in '.!?':
            result += text[-1]
    
    return result.strip()


def generate_tutor_response(topic, message, emotion, history, teaching_mode=None):
    """
    Generate a tutor response based on student input and context.
    
    Args:
        topic: The topic being taught (e.g., "linear regression")
        message: The student's input/question
        emotion: Student's detected emotion (confused, frustrated, engaged, neutral)
        history: List of previous messages [{role, text}, ...] for context
        teaching_mode: How to teach (normal/simplified/analogy/step_by_step/ultra_simple)
    
    Returns:
        str: The tutor's response following improved pedagogical patterns
    """
    
    if history is None:
        history = []
    
    if teaching_mode is None:
        teaching_mode = "normal"
    
    # CRITICAL: Detect minimal inputs and force ultra_simple mode
    if detect_minimal_input(message):
        teaching_mode = "ultra_simple"
    
    # Determine teaching depth based on emotion
    depth_map = {
        "engaged": "ADVANCED: Go deep, include connections, offer optional further exploration",
        "very_engaged": "EXPERT: Maximum depth, nuanced perspectives, challenge them intellectually",
        "neutral": "INTERMEDIATE: Clear, balanced, practical examples, scalable complexity",
        "confused": "BEGINNER: Ultra-simple, concrete examples, offer 'want more?' not 'here's more'",
        "very_confused": "FOUNDATION: Essential concept only, very relatable example, confidence-building",
        "frustrated": "SUPPORT: Validation first, minimal content, celebrate effort, 'you can do this'",
        "very_frustrated": "ENCOURAGEMENT: Heavy emotional support, 1-sentence explanation, affirm their effort"
    }
    
    teaching_depth = depth_map.get(emotion, depth_map["neutral"])
    
    # Build messages list
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    # Add conversation history
    for msg in history:
        msg_role = "user" if msg.get("role") in ["student", "user"] else "assistant"
        messages.append({
            "role": msg_role,
            "content": msg.get("text", msg.get("content", ""))
        })
    
    # STEP 4: Build teaching mode instructions
    teaching_mode_rules = ""
    if teaching_mode == "normal":
        teaching_mode_rules = "Teaching Mode: NORMAL\nExplain clearly with examples and offer deeper exploration if appropriate."
    elif teaching_mode == "simplified":
        teaching_mode_rules = "Teaching Mode: SIMPLIFIED\nProvide a SHORTER explanation. Use simpler words. Skip advanced details. Keep it to 2-3 sentences max."
    elif teaching_mode == "analogy":
        teaching_mode_rules = "Teaching Mode: ANALOGY\nExplain USING ONLY a real-life analogy or comparison. Do not use technical explanation. Make it relatable and simple."
    elif teaching_mode == "step_by_step":
        teaching_mode_rules = "Teaching Mode: STEP BY STEP\nProvide numbered steps ONLY (1. 2. 3.). Break down the concept into small, sequential actions."
    elif teaching_mode == "ultra_simple":
        teaching_mode_rules = "Teaching Mode: ULTRA SIMPLE\nUse maximum 2 sentences. Use only basic, everyday words. No jargon. No complex concepts."
    
    # Add current message with enhanced context including teaching mode
    user_prompt = f"""📚 LEARNING CONTEXT:
STRICT_TOPIC: {topic}
ONLY_TEACH_THIS: {topic}
Student emotional state: {emotion}
Teaching depth level: {teaching_depth}

{teaching_mode_rules}

💬 Student's message: "{message}"

CRITICAL INSTRUCTIONS (MUST FOLLOW):
1. Acknowledge what they said first
2. Keep response NATURAL and CONVERSATIONAL - blend explanation + example + question smoothly
3. DO NOT use headers like "📘 EXPLANATION", "📌 EXAMPLE", "❓ WHAT'S YOUR THINKING?"
4. STAY STRICTLY on topic "{topic}" - DO NOT introduce new topics or related fields
5. If student is confused → RE-EXPLAIN same concept simpler, do NOT switch topics
6. Hard sentence limits based on emotion:
   - Minimal inputs like "oh", "ok", "hmm": MAX 1 SENTENCE - just acknowledge and continue
   - Frustrated/very_frustrated: MAX 2 sentences, no question, no new topics
   - Confused/very_confused: MAX 3 sentences, 1 simple example only, NO questions, NO new terminology
   - Neutral: MAX 5 sentences, explanation + example + question OK
   - Engaged/very_engaged: MAX 8 sentences, deeper OK but stay on-topic
7. For frustrated/confused: NO questions, NO scope expansion, only simplify current concept
8. For minimal inputs: Just acknowledge and continue the lesson naturally in 1 sentence max"""
    
    messages.append({"role": "user", "content": user_prompt})

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0.4,
        messages=messages
    )

    return response.choices[0].message.content
