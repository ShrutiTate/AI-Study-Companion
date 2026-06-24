#ai_tutor.py

"""
AI Tutor Service
Uses Groq to transform study material chunks into intelligent explanations with hints and practice
"""

from groq import Groq
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Groq client with API key from environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")
client = Groq(api_key=GROQ_API_KEY)


def generate_ai_response(topic: str, chunk: str, emotion: str, teaching_mode: str = "adaptive", enhanced_context: str = "") -> dict:
    """
    Transform a study material chunk into an interactive learning response using Groq.
    
    The response adapts based on student's emotion and teaching mode:
    - emotion: confused/frustrated = simpler, engaged = deeper
    - teaching_mode: simplify (very basic), teach_basic (beginner), adaptive (medium), advanced (deeper)
    - enhanced_context: Additional context to control structure and style (from learning.py)
    
    Args:
        topic: Learning topic
        chunk: Study material chunk from RAG
        emotion: Detected emotion (confused, frustrated, engaged, etc.)
        teaching_mode: How to adapt response ("simplify", "teach_basic", "adaptive", "advanced")
        enhanced_context: Additional context for structure control and style guidance
    
    Returns:
        Dictionary with explanation, example, quick_check
    """
    
    # Adapt prompt based on emotion
    emotion_guidance = {
        "confused": "Explain in VERY simple terms. Break down complex concepts. Use analogies. Be patient.",
        "very_confused": "Use the SIMPLEST possible language. Give a real-world example first. Then explain step-by-step.",
        "frustrated": "Be encouraging and motivating. Simplify more than usual. Tell them it's normal to struggle. Build confidence.",
        "very_frustrated": "Be very supportive. Acknowledge their feeling. Simplify explanations to basics only. Offer one tip at a time.",
        "engaged": "Good! Student is engaged. You can go slightly deeper. Include interesting extensions or advanced perspectives.",
        "very_engaged": "Student is doing great! Include advanced concepts, interesting extensions, or challenges.",
        "positive": "Student is positive. Maintain momentum. Explain clearly but can include some depth.",
        "neutral": "Neutral tone. Clear, structured explanation. Balance simplicity with completeness."
    }
    
    # Adapt prompt based on teaching mode
    mode_guidance = {
        "simplify": "CRITICAL: Use EXTREMELY simple language. Break everything into tiny pieces. Use only simple words.",
        "teach_basic": "Use simple language aimed at beginners. No jargon. Explain concepts from scratch.",
        "adaptive": "Balance between simplicity and depth based on emotion. Adjust based on user state.",
        "advanced": "You can use more technical terms. Include deeper concepts and interesting extensions."
    }
    
    emotion_instruction = emotion_guidance.get(emotion, emotion_guidance["neutral"])
    mode_instruction = mode_guidance.get(teaching_mode, mode_guidance["adaptive"])
    
    # Add special instruction to prevent repeated explanations
    repeat_warning = ""
    if teaching_mode in ["simplify", "teach_basic"]:
        repeat_warning = "\n⚠️ CRITICAL FOR RETRY: If the student's previous answer was wrong/partial, EXPLAIN COMPLETELY DIFFERENTLY.\nDo NOT use the same words or structure as before. Use new analogies, new examples, new wording."
    
    prompt = f"""🚨 ABSOLUTELY NO YES/NO QUESTIONS 🚨

You are an AI tutor creating: EXPLANATION + EXAMPLE + OPEN-ENDED QUESTION

TOPIC: {topic}
EMOTION: {emotion}  
MODE: {teaching_mode}
INSTRUCTION: {emotion_instruction}
MODE_GUIDANCE: {mode_instruction}{repeat_warning}

{enhanced_context}

STUDY MATERIAL:
{chunk}

---

FORMAT (STRICTLY ENFORCE THIS):

📘 Explanation:
[2-4 lines. Simple, clear. Follow teaching style above.]

📌 Example:
[1-2 lines. Real or relatable.]

❓ Quick Check:
[QUESTION - Student must EXPLAIN. NOT yes/no. Follow guidance above.]

---

🚨 BANNED QUESTION STARTS:
"Can ", "Does ", "Is ", "Would ", "Should ", "Could ", "May ", "Will "

✅ REQUIRED QUESTION STARTS:
"Explain...", "Describe...", "How...", "Why...", "What...", "Give an example...", "Tell me..."

🚨 BANNED EXAMPLES:
"Can a computer learn?" → YES/NO TRAP
"Does this work?" → YES/NO TRAP  
"Is recursion a loop?" → YES/NO TRAP

✅ CORRECT EXAMPLES:
"Explain how a computer learns from data"
"Describe what machine learning is"
"How would you explain this to a friend?"
"Why is this useful?"
"Give an example of machine learning"

Your ONLY job:
1. Explain topic (with teaching style)
2. Show example (real-world or easy)
3. Ask OPEN-ENDED question (Explain/Describe/How/Why/What/Give)

DO NOT ask yes/no questions. If you do, you FAIL."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
            timeout=30  # 30 second timeout for Groq
        )
        
        ai_response_text = response.choices[0].message.content
        
        # Parse the response into sections
        result = parse_ai_response(ai_response_text)
        
        return {
            "success": True,
            "explanation": result.get("explanation", ""),
            "example": result.get("example", ""),
            "quick_check": result.get("quick_check", ""),
            "full_response": ai_response_text
        }
        
    except Exception as e:
        print(f"[AI_TUTOR] Error calling Groq: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "explanation": "Unable to generate response at the moment.",
            "example": "Try rephrasing your question.",
            "quick_check": ""
        }


def fix_yes_no_question(question: str) -> str:
    """
    Post-processing: Fix any yes/no questions that slipped through.
    Converts "Can you...?" to "Explain how you would..."
    """
    question = question.strip()
    
    # Check if question is yes/no format
    banned_starts = ["can ", "does ", "is ", "would ", "should ", "could ", "may ", "will "]
    question_lower = question.lower()
    
    is_yes_no = False
    for start in banned_starts:
        if question_lower.startswith(start):
            is_yes_no = True
            break
    
    # If it ends with just "?" it's likely yes/no
    if is_yes_no and question.endswith("?"):
        # Convert "Can a computer..." to "Explain how a computer..."
        if question_lower.startswith("can "):
            question = "Explain how " + question[4:-1]
        elif question_lower.startswith("does "):
            question = "Describe what happens when " + question[5:-1]
        elif question_lower.startswith("is "):
            question = "Explain what " + question[3:-1] + " is"
        elif question_lower.startswith("would "):
            question = "Describe what would happen if " + question[6:-1]
        elif question_lower.startswith("should "):
            question = "Explain when you should " + question[7:-1]
        elif question_lower.startswith("could "):
            question = "Explain how you could " + question[6:-1]
        elif question_lower.startswith("may "):
            question = "Describe what may " + question[4:-1]
        elif question_lower.startswith("will "):
            question = "Describe what will " + question[5:-1]
    
    # Ensure it ends with proper punctuation
    if not question.endswith("?"):
        question = question.rstrip(".!") + "?"
    
    return question


def parse_ai_response(response_text: str) -> dict:
    """
    Parse the new compact AI response format.
    Extracts: Explanation, Example, Quick Check
    Fixes any yes/no questions that slipped through.
    
    Args:
        response_text: Raw response from Groq
    
    Returns:
        Dictionary with parsed sections
    """
    
    sections = {
        "explanation": "",
        "example": "",
        "quick_check": ""
    }
    
    text_lower = response_text.lower()
    
    # Find section markers (more flexible matching)
    explanation_patterns = ["explanation:", "📘"]
    example_patterns = ["example:", "📌"]
    quick_check_patterns = ["quick check:", "❓"]
    
    # Find indices for new format
    explanation_idx = -1
    example_idx = -1
    quick_check_idx = -1
    
    for pattern in explanation_patterns:
        idx = text_lower.find(pattern)
        if idx != -1:
            explanation_idx = idx
            break
    
    for pattern in example_patterns:
        idx = text_lower.find(pattern)
        if idx != -1:
            example_idx = idx
            break
    
    for pattern in quick_check_patterns:
        idx = text_lower.find(pattern)
        if idx != -1:
            quick_check_idx = idx
            break
    
    # Extract Explanation
    if explanation_idx != -1:
        start = response_text.find(":", explanation_idx) + 1
        # End at next section or end of text
        end_candidates = [idx for idx in [example_idx, quick_check_idx, len(response_text)] if idx > explanation_idx and idx != -1]
        end = min(end_candidates) if end_candidates else len(response_text)
        
        content = response_text[start:end].strip()
        content = content.replace("**", "").replace("*", "").replace("📘", "").replace("📌", "").replace("❓", "").strip()
        sections["explanation"] = content
    
    # Extract Example
    if example_idx != -1:
        start = response_text.find(":", example_idx) + 1
        end_candidates = [idx for idx in [quick_check_idx, len(response_text)] if idx > example_idx and idx != -1]
        end = min(end_candidates) if end_candidates else len(response_text)
        
        content = response_text[start:end].strip()
        content = content.replace("**", "").replace("*", "").replace("📘", "").replace("📌", "").replace("❓", "").strip()
        sections["example"] = content
    
    # Extract Quick Check
    if quick_check_idx != -1:
        start = response_text.find(":", quick_check_idx) + 1
        end = len(response_text)
        
        content = response_text[start:end].strip()
        content = content.replace("**", "").replace("*", "").replace("📘", "").replace("📌", "").replace("❓", "").strip()
        
        # FIX ANY YES/NO QUESTIONS THAT SLIPPED THROUGH
        content = fix_yes_no_question(content)
        
        sections["quick_check"] = content
    
    # Fallback: if no sections found, treat whole response as explanation
    if not sections["explanation"] and not sections["example"] and not sections["quick_check"]:
        sections["explanation"] = response_text.strip()
    
    return sections
