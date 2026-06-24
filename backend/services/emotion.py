from typing import Dict
import json

# Lazy load: model loads only on first use, not at import time
emotion_model = None
MODEL_LOADED = False
MODEL_LOAD_ATTEMPTED = False

def _load_emotion_model():
    """Load emotion model on first use (lazy loading to avoid startup block)"""
    global emotion_model, MODEL_LOADED, MODEL_LOAD_ATTEMPTED
    if MODEL_LOAD_ATTEMPTED:
        return
    
    MODEL_LOAD_ATTEMPTED = True
    try:
        print("[EMOTION] Loading emotion detection model...")
        from transformers import pipeline
        emotion_model = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            device=-1  # CPU (device=0 for GPU if available)
        )
        MODEL_LOADED = True
        print("[EMOTION] ✅ Model loaded successfully")
    except Exception as e:
        print(f"[EMOTION] Warning: Could not load transformer model: {e}")
        print(f"[EMOTION] Falling back to basic sentiment detection")
        MODEL_LOADED = False

# ============================================
# LEARNING CONTEXT PATTERNS
# Domain-specific emotion indicators
# ============================================

SARCASM_INDICATORS = [
    "yeah right",
    "yeah because",
    "so easy",
    "very funny",
    "right sure",
    "oh sure",
    "im sure",
    "i'm sure",
    "yeah sure",
    "obviously",  # Sarcastic obviousness
    "clearly",  # In context of confusion
    "easy right",
    "obviously everyone",  # Sarcastic generalization
    "i'm sure everyone",
    "sure everyone",
]

# Sarcasm patterns about difficulty (sarcastically calling something easy = actually frustrated)
SARCASM_DIFFICULTY_PATTERNS = [
    "so easy",
    "easy right",
    "real easy",
    "very hard",  # Actually might be sarcasm
]

LEARNING_CONFUSION_PATTERNS = [
    # Core confusion patterns
    "doesn't make sense",
    "dont make sense",
    "doesn't make sense to me",
    "dont get it",
    "don't get it",
    "i don't get it",
    "i dont get it",
    "can't understand",
    "cant understand",
    "don't understand",
    "dont understand",
    "don't follow",
    "dont follow",
    "i'm confused",
    "im confused",
    "completely confused",
    "totally confused",
    
    # Questions indicating confusion (phrase-based, not just "what")
    "what is happening",
    "what do you mean",
    "explain this",  # More specific than generic question
    "how does this work",
    "why would that",
    "can you explain",
    "can you clarify",
    "can you break that down",
    "can you go over this again",
    
    # Lost/disoriented patterns
    "i'm lost",
    "im lost",
    "totally lost",
    "completely lost",
    "lost",
    "confused",
    "confusing",
    "unclear",
    "not clear",
    "it's not clear",
    "that's not clear",
    "hard to follow",
    
    # Comprehension gaps
    "i don't understand",
    "i get lost",
    "lose track",
    "no clue",
    "no idea",
    "clueless",
    "blurry",
    "fuzzy",
    "vague",
]

LEARNING_FRUSTRATION_PATTERNS = [
    # Difficulty patterns
    "too hard",
    "so hard",
    "way too hard",
    "extremely hard",
    "too difficult",
    "so difficult",
    "too complicated",
    "so complicated",
    "way too complicated",
    "overly complicated",
    
    # Struggle patterns
    "stuck",
    "totally stuck",
    "completely stuck",
    "struggling",
    "struggling with",
    "struggling to",
    "having trouble",
    "having difficulty",
    "difficult time",
    
    # Frustration expressions
    "give up",
    "want to give up",
    "feel like giving up",
    "why is this",
    "why is this so",
    "this is impossible",
    "seems impossible",
    "never gonna get",
    "never going to",
    "can't finish",
    "cant finish",
    "can't solve",
    "cant solve",
    "can't figure",
    "cant figure",
    
    # Negative emotional expressions
    "terrible",
    "awful",
    "horrible",
    "disgusting",
    "this sucks",
    "sucks",
    "this is annoying",
    "extremely annoyed",
    "irritating",
    "exasperating",
    "fed up",
    "frustrated",
    "frustrating",
    "exasperating",
    "exhausted",
    "tired",
    "so tired",
    "worn out",
    "burned out",
    "over it",
]

POSITIVE_LEARNING_SIGNALS = [
    # Core understanding patterns
    "i get it",
    "got it",
    "i got it",
    "now i get it",
    "finally get it",
    "now i understand",
    "i understand",
    "understand now",
    "finally understand",
    "i understand now",
    "oh i understand",
    "makes sense",
    "now it makes sense",
    "finally makes sense",
    "oh that makes sense",
    
    # Recognition/clarity patterns
    "oh i see",
    "i see",
    "ohhh i see",
    "i see now",
    "now i see",
    "clear now",
    "that's clear",
    "now it's clear",
    "is clear",
    
    # Affirmation patterns
    "cool",
    "awesome",
    "great",
    "excellent",
    "amazing",
    "fantastic",
    "wonderful",
    "brilliant",
    "super cool",
    
    # Enjoyment patterns
    "interesting",
    "fascinating",
    "love it",
    "really enjoy",
    "enjoying this",
    "fun",
    "having fun",
    "this is fun",
    
    # Positive expressions
    "finally got it",
    "finally got",
    "got the concept",
    "got the idea",
    "that explains",
    "glad you",
    "appreciate",
    "pleased",
]

UNDERSTANDING_LOW_PATTERNS = [
    # Core low understanding
    "don't understand",
    "dont understand",
    "i don't understand",
    "i dont understand",
    "don't get it",
    "dont get it",
    "i don't get it",
    "i dont get it",
    "confused",
    "completely confused",
    "totally confused",
    "lost",
    "totally lost",
    "completely lost",
    "no idea",
    "no clue",
    "clueless",
    "have no idea",
    "haven't a clue",
]

UNDERSTANDING_HIGH_PATTERNS = [
    # Core high understanding
    "i get it",
    "got it",
    "i got it",
    "understand",
    "i understand",
    "understood",
    "makes sense",
    "clear now",
    "it's clear",
    "that's clear",
    "now i see",
    "i see",
    "oh i see",
    "now it's clear",
    "finally understand",
    "finally get it",
    "got the concept",
    "got the idea",
    "crystal clear",
]

# ============================================
# EMOTION DETECTION FUNCTIONS
# ============================================

def map_emotion(label: str) -> str:
    """
    Map transformer model emotions to learning system emotions.
    
    Transformer labels: anger, disgust, fear, joy, neutral, sadness, surprise
    Learning system: frustrated, confused, engaged, neutral
    """
    label_lower = label.lower()
    
    if label_lower == "anger":
        return "frustrated"
    elif label_lower in ["sadness", "fear", "disgust"]:
        return "confused"
    elif label_lower in ["joy", "surprise"]:
        return "engaged"
    else:
        return "neutral"

def learning_context_override(text: str, current_emotion: str) -> tuple:
    """
    Apply learning-context rules to catch domain-specific emotions.
    This is the KEY layer that makes the system context-aware.
    
    Priority order:
    1. Sarcasm detection (reverses positive sentiment)
    2. More specific patterns (e.g., "hard to follow" → confusion, not "hard" → frustration)
    3. Confusion patterns
    4. Frustration patterns
    5. Positive learning signals
    
    Returns: (emotion, source) where source is "model" or "learning_rules"
    """
    text_lower = text.lower()
    
    # Step 1: DETECT SARCASM (highest priority - reverses positive messages)
    # Sarcasm indicators with positive words = actual confusion/frustration
    has_sarcasm = any(pattern in text_lower for pattern in SARCASM_INDICATORS)
    has_positive_signal = any(pattern in text_lower for pattern in POSITIVE_LEARNING_SIGNALS)
    has_difficulty_sarcasm = any(pattern in text_lower for pattern in SARCASM_DIFFICULTY_PATTERNS)
    
    # Special case: Pure sarcasm in learning context = confusion
    # "yeah right", "yeah because", etc. without explicit positive signal = confused/doubtful
    if has_sarcasm and not has_positive_signal:
        # Pure sarcasm (not combined with positive) = confused or frustrated
        return "confused", "learning_rules"
    
    # Special case: "obviously everyone gets this" = sarcastic confusion
    if "obviously everyone" in text_lower or "sure everyone" in text_lower:
        return "confused", "learning_rules"
    
    if has_sarcasm and has_positive_signal:
        # Sarcastic positive = actually confused or frustrated
        return "confused", "learning_rules"
    
    # Sarcasm about difficulty (sarcastically calling something easy) = frustrated
    if has_difficulty_sarcasm and not has_positive_signal:
        # "so easy right" when actually confused = frustrated about difficulty
        return "frustrated", "learning_rules"
    
    # Step 2: Check MORE SPECIFIC patterns first (exact combinations)
    # "hard to follow" should be CONFUSION, not frustration
    if "hard to follow" in text_lower:
        return "confused", "learning_rules"
    
    # Neutral generic informational requests (should NOT override to engaged/confused)
    # These are just asking for information, not emotional learning signals
    if text_lower.startswith("what is ") and current_emotion == "engaged":
        # "what is X" questions are neutral inquiries, not engagement
        return "neutral", "learning_rules"
    
    if text_lower.startswith("tell me about "):
        # "tell me about X" is neutral information request
        return "neutral", "learning_rules"
    
    # Step 3: Check confusion patterns (before frustration for better specificity)
    if any(pattern in text_lower for pattern in LEARNING_CONFUSION_PATTERNS):
        return "confused", "learning_rules"
    
    # Step 4: Check frustration patterns
    if any(pattern in text_lower for pattern in LEARNING_FRUSTRATION_PATTERNS):
        return "frustrated", "learning_rules"
    
    # Step 5: Check positive learning signals (override neutral → engaged)
    if current_emotion == "neutral" and any(pattern in text_lower for pattern in POSITIVE_LEARNING_SIGNALS):
        return "engaged", "learning_rules"
    
    # No override needed, use model result
    return current_emotion, "model"

def intent_override(text: str, current_emotion: str) -> str:
    """
    Light intent correction for learning-specific context.
    Only override when obvious learning POSITIVE intent is detected.
    """
    text_lower = text.lower()
    
    # Strong POSITIVE learning intent signals (engagement)
    # Include both "let's" and "lets" forms
    positive_learning_keywords = [
        "let's learn", "lets learn", 
        "start learning", "want to learn",
        "got it", "i understand", "understand now",
        "i see", "makes sense"
    ]
    
    if any(keyword in text_lower for keyword in positive_learning_keywords):
        return "engaged"
    
    # Return original emotion if no override needed
    return current_emotion

def detect_understanding(text: str) -> str:
    """
    Detect student's level of understanding from text.
    
    Returns: "low", "medium", "high"
    
    Priority order: Check HIGH patterns first (positive overrides), then LOW patterns
    """
    text_lower = text.lower()
    
    # Check for HIGH understanding indicators (positive, takes priority)
    high_count = sum(1 for pattern in UNDERSTANDING_HIGH_PATTERNS if pattern in text_lower)
    
    # Check for LOW understanding indicators (negative)
    low_count = sum(1 for pattern in UNDERSTANDING_LOW_PATTERNS if pattern in text_lower)
    
    # If both found, look at text length and context
    if high_count > 0 and low_count > 0:
        # Mixed signals - use order in text (last message matters more)
        # For now, high signals override low in mixed contexts
        if high_count > low_count:
            return "high"
        elif low_count > high_count:
            return "low"
        else:
            # Equal - check which appears later in text
            last_high = max([text_lower.rfind(p) for p in UNDERSTANDING_HIGH_PATTERNS], default=-1)
            last_low = max([text_lower.rfind(p) for p in UNDERSTANDING_LOW_PATTERNS], default=-1)
            return "high" if last_high > last_low else "low"
    
    # Single signal type detected
    if high_count > 0:
        return "high"
    
    if low_count > 0:
        return "low"
    
    # Default to medium
    return "medium"

# Initialize Groq for LLM-based fallback emotion detection
groq_client = None
def _get_groq_client():
    global groq_client
    if groq_client is not None:
        return groq_client
    
    try:
        import os
        from groq import Groq
        from dotenv import load_dotenv
        
        # Determine path to .env dynamically relative to emotion.py location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(current_dir, "..", ".env")
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()
            
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            groq_client = Groq(api_key=api_key)
            print("[EMOTION] Groq client initialized successfully for fallback")
    except Exception as e:
        print(f"[EMOTION] Warning: Could not initialize Groq client: {e}")
        
    return groq_client

def detect_emotion_via_llm(text: str, previous_tutor_message: str = "", context: dict = None) -> dict:
    """Classify student emotion using Groq Llama 3.1 model, returning label and confidence."""
    client = _get_groq_client()
    if not client:
        return {"emotion": "neutral", "confidence": 1.0}
        
    try:
        prev_tutor = ""
        topic = ""
        concept = ""
        is_first = False
        
        if context:
            prev_tutor = context.get("previous_tutor_message", "")
            topic = context.get("session_topic", "")
            concept = context.get("current_concept", "")
            is_first = context.get("is_first_message", False)
        else:
            prev_tutor = previous_tutor_message
            
        prompt = f"""You are a pedagogical assistant. Analyze the emotional state of a student based on their message and the context.

Context:
- Tutor just said: "{prev_tutor}"
- Session Topic: "{topic}"
- Current Concept: "{concept}"
- Is First Message: {is_first}

Student Message: "{text}"

Classify into exactly one of these categories:
- engaged
- confused
- frustrated
- neutral

Provide a confidence score between 0.0 and 1.0. If the student is replying to a first message or answering a clarifying question, be conservative and prefer neutral/engaged.
Return JSON format:
{{
  "emotion": "engaged|confused|frustrated|neutral",
  "confidence": 0.85
}}"""
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50,
            response_format={"type": "json_object"},
            timeout=5
        )
        
        data = json.loads(response.choices[0].message.content.strip())
        emotion = data.get("emotion", "neutral").lower().strip()
        confidence = float(data.get("confidence", 0.70))
        
        if emotion in ["engaged", "confused", "frustrated", "neutral"]:
            return {"emotion": emotion, "confidence": confidence}
            
        for em in ["engaged", "confused", "frustrated", "neutral"]:
            if em in emotion:
                return {"emotion": em, "confidence": confidence}
    except Exception as e:
        print(f"[EMOTION] Groq classification failed: {e}")
        
    return {"emotion": "neutral", "confidence": 1.0}

def detect_emotion_via_rules(text: str) -> str:
    """
    Check explicit local keywords/patterns for quick emotion detection.
    Returns: "frustrated" | "confused" | "engaged" | None
    """
    text_lower = text.lower().strip()
    
    # 1. Sarcasm detection first (indicates confusion/frustration)
    has_sarcasm = any(pattern in text_lower for pattern in SARCASM_INDICATORS)
    has_positive = any(pattern in text_lower for pattern in POSITIVE_LEARNING_SIGNALS)
    has_diff_sarcasm = any(pattern in text_lower for pattern in SARCASM_DIFFICULTY_PATTERNS)
    
    if has_sarcasm and not has_positive:
        return "confused"
    if has_sarcasm and has_positive:
        return "confused"
    if has_diff_sarcasm and not has_positive:
        return "frustrated"
        
    # 2. Specific confusion overrides
    if "hard to follow" in text_lower:
        return "confused"
        
    # 3. Learning confusion patterns
    if any(pattern in text_lower for pattern in LEARNING_CONFUSION_PATTERNS):
        return "confused"
        
    # 4. Learning frustration patterns
    if any(pattern in text_lower for pattern in LEARNING_FRUSTRATION_PATTERNS):
        return "frustrated"
        
    # 5. Positive learning signals
    if any(pattern in text_lower for pattern in POSITIVE_LEARNING_SIGNALS):
        return "engaged"
        
    return None

import functools

@functools.lru_cache(maxsize=128)
def detect_emotion(text: str, previous_tutor_message: str = "", context: dict = None) -> str:
    """
    Detect emotion from text using a robust hybrid pipeline:
    1. Local rule-based checks (instant, zero cost, handles explicit patterns)
    2. Local Transformer model (if loaded and confident)
    3. Groq LLM model (fallback for non-neutral detection on complex text)
    4. Default fallback: neutral
    """
    res = get_emotion_with_confidence(text, previous_tutor_message=previous_tutor_message, context=context)
    return res["emotion"]

@functools.lru_cache(maxsize=128)
def get_emotion_with_confidence(text: str, previous_tutor_message: str = "", context: dict = None) -> Dict:
    """
    Detect emotion and return confidence score with source tracking.
    """
    if not text or not text.strip():
        return {"emotion": "neutral", "confidence": 1.0, "source": "empty_input", "understanding": "medium"}
        
    word_count = len(text.split())
    
    # Check rules first
    rule_emotion = detect_emotion_via_rules(text)
    if rule_emotion:
        emotion = rule_emotion
        confidence = 0.95
        source = "rules"
    else:
        # Try model
        _load_emotion_model()
        model_passed = False
        if MODEL_LOADED:
            try:
                result = emotion_model(text)[0]
                label = result["label"]
                score = result["score"]
                model_emotion = map_emotion(label)
                mapped_emotion, source = learning_context_override(text, model_emotion)
                
                text_lower = text.lower()
                has_sarcasm = any(pattern in text_lower for pattern in SARCASM_INDICATORS)
                if not has_sarcasm:
                    mapped_emotion = intent_override(text, mapped_emotion)
                    
                required_threshold = 0.75 if word_count < 10 else 0.60
                if mapped_emotion != "neutral" and score > required_threshold:
                    emotion = mapped_emotion
                    confidence = score
                    source = "model"
                    model_passed = True
            except:
                pass
                
        if not model_passed:
            # Fallback to Groq LLM
            llm_res = detect_emotion_via_llm(text, previous_tutor_message=previous_tutor_message, context=context)
            emotion = llm_res.get("emotion", "neutral")
            confidence = llm_res.get("confidence", 0.70)
            source = "groq_llm"
            
    # Apply confidence filtering threshold for short messages (< 10 words)
    if word_count < 10 and emotion != "neutral":
        if confidence < 0.75:
            print(f"[EMOTION] Downgrading '{emotion}' to 'neutral' for short message ({word_count} words) with confidence {confidence} < 0.75")
            emotion = "neutral"
            confidence = 1.0
            
    return {
        "emotion": emotion,
        "confidence": round(confidence, 2),
        "model_label": source,
        "source": source,
        "understanding": detect_understanding(text)
    }

def adaptive_response(emotion: str) -> str:
    """
    Generate adaptive response based on detected emotion.
    """
    responses = {
        "frustrated": "Let's simplify this topic.",
        "confused": "Here's a hint.",
        "engaged": "Try a harder question.",
        "neutral": "Let me help you understand this better."
    }
    return responses.get(emotion, "Keep going!")
