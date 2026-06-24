# improved_prompting.py
"""
Dynamic Adaptive Prompting Service for Non-Generic Tutoring
Replaces rigid prompt structure with behavior-driven, context-aware guidance
"""

from groq import Groq
import os
from dotenv import load_dotenv
import json
import re

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")

client = Groq(api_key=GROQ_API_KEY)


MODE_BEHAVIORS = {
    "simplify": {
        "description": "Extremely simple, foundational level",
        "guidance": "Use VERY simple language (8th grade level max). Keep explanation to 2-3 sentences. Use only everyday examples. Be encouraging and supportive."
    },
    "teach_basic": {
        "description": "Basic but complete explanation",
        "guidance": "Explain step-by-step with simple examples. 3-4 sentences for explanation. Include one real-world comparison. Ask a clarifying question."
    },
    "adaptive": {
        "description": "Balanced depth and clarity",
        "guidance": "Balance technical accuracy with clarity. Provide good explanation + practical example. Can use some technical terms if appropriate. Ask a thoughtful question."
    },
    "advanced": {
        "description": "Deeper exploration with insights",
        "guidance": "Go deeper into the concept. Include interesting edge cases or extensions. Can use technical terminology. Challenge the student slightly. Ask a question that requires real thinking."
    }
}


EMOTION_BEHAVIORS = {
    "very_frustrated": {"adjustment": "Maximum simplification", "temperature": 0.3},
    "frustrated": {"adjustment": "Strong simplification", "temperature": 0.4},
    "confused": {"adjustment": "Clarify with examples", "temperature": 0.5},
    "neutral": {"adjustment": "Standard teaching", "temperature": 0.6},
    "engaged": {"adjustment": "Slightly deeper", "temperature": 0.7},
    "very_engaged": {"adjustment": "Go deeper, challenge", "temperature": 0.8}
}


def build_adaptive_prompt(topic: str, user_input: str, emotion: str,
                         teaching_mode: str, content_chunk: str,
                         attempt_count: int = 0, last_explanation: str = "",
                         learning_style: str = "balanced", confidence: str = "medium",
                         common_mistake: str = "", last_answer_correct: bool = None) -> tuple:
    """
    Build a dynamic adaptive prompt with full student state injection.
    Returns: (prompt, temperature)
    """
    mode_behavior = MODE_BEHAVIORS.get(teaching_mode, MODE_BEHAVIORS["adaptive"])
    emotion_behavior = EMOTION_BEHAVIORS.get(emotion, EMOTION_BEHAVIORS["neutral"])
    
    # Build student state section
    understanding = 'low' if emotion in ['very_frustrated', 'frustrated', 'confused'] else (
        'high' if emotion in ['engaged', 'very_engaged'] else 'medium')
    
    student_state_lines = [
        f"Emotion: {emotion}",
        f"Learning Style: {learning_style}",
        f"Confidence: {confidence}",
        f"Understanding: {understanding}",
        f"Attempt: {attempt_count + 1}"
    ]
    
    if common_mistake:
        student_state_lines.append(f"Common Mistake: {common_mistake}")
    
    student_state_str = "\n".join(student_state_lines)
    
    # Build mistake context
    mistake_context = ""
    if last_answer_correct is False and common_mistake:
        mistake_context = f"\n\nIMPORTANT: Student got it wrong last time.\nTheir mistake: {common_mistake}\nYou MUST address what went wrong."
    
    # Build repetition strategy
    repetition_strategy = ""
    if attempt_count > 0 and last_explanation:
        last_lower = last_explanation.lower()
        if any(word in last_lower for word in ["example", "instance", "like"]):
            next_strategy = "Use a DEFINITION or CONCEPTUAL approach"
        elif any(word in last_lower for word in ["step", "first", "then", "process"]):
            next_strategy = "Use an ANALOGY or STORY"
        elif any(word in last_lower for word in ["is", "means", "definition"]):
            next_strategy = "Use a PRACTICAL EXAMPLE"
        else:
            next_strategy = "Use a completely different approach"
        repetition_strategy = f"\n\nThis is attempt {attempt_count + 1}. Use a different strategy: {next_strategy}"
    
    # Build the prompt
    prompt = f"""You are an adaptive AI tutor helping a student understand {topic}.

STUDENT CONTEXT:
{student_state_str}

STUDENT'S INPUT: "{user_input}"

TEACHING MODE: {mode_behavior['description']}
{mode_behavior['guidance']}

LEARNING STYLE GUIDANCE:
- If example_learner: Lead with concrete examples
- If step_by_step: Break into clear sequential steps
- If visual_learner: Describe visual concepts
- If conceptual: Start with big idea, then details

CONFIDENCE LEVEL ({confidence}):
- Very Low: Extremely simple, very encouraging
- Low: Simple, supportive, build confidence
- Medium: Balanced depth and support
- High: Can go deeper, can challenge
- Very High: Deep insights, complex ideas OK

RESPONSE REQUIREMENTS:
1. Always reference the student's specific learning context
2. If they made a mistake, show them what went wrong
3. Vary your approach - don't use the same strategy twice
4. Be natural and conversational, not robotic
5. Match the confidence level with your tone

{mistake_context}{repetition_strategy}

CONTENT TO WORK WITH:
{content_chunk}

RESPOND AS JSON WITH ONLY NEEDED FIELDS:
{{"explanation": "...", "example": "...", "question": "...", "encouragement": "..."}}

Include explanation, and only include other fields if they help this specific student."""
    
    temperature = emotion_behavior.get("temperature", 0.6)
    return (prompt, temperature)


def generate_adaptive_response(topic: str, user_input: str, emotion: str,
                              teaching_mode: str, content_chunk: str,
                              attempt_count: int = 0, last_explanation: str = "",
                              learning_style: str = "balanced", confidence: str = "medium",
                              common_mistake: str = "", last_answer_correct: bool = None) -> dict:
    """
    Generate a response using adaptive prompting WITH FULL STUDENT CONTEXT.
    """
    prompt, temperature = build_adaptive_prompt(
        topic=topic,
        user_input=user_input,
        emotion=emotion,
        teaching_mode=teaching_mode,
        content_chunk=content_chunk,
        attempt_count=attempt_count,
        last_explanation=last_explanation,
        learning_style=learning_style,
        confidence=confidence,
        common_mistake=common_mistake,
        last_answer_correct=last_answer_correct
    )
    
    print(f"[ADAPTIVE] Generating response with temperature={temperature}, mode={teaching_mode}, emotion={emotion}, style={learning_style}")
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are an adaptive AI tutor. Respond naturally based on the student's needs. Return ONLY valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=temperature,
            max_tokens=800,
            timeout=30
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Handle markdown code blocks
        if response_text.startswith("```"):
            response_text = re.sub(r'```json\n?', '', response_text)
            response_text = re.sub(r'```\n?', '', response_text)
        
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {"explanation": response_text}
        
        # Ensure we have required fields
        result.setdefault("explanation", "")
        result.setdefault("example", "")
        result.setdefault("question", "")
        
        return {
            "success": True,
            "explanation": result.get("explanation", ""),
            "example": result.get("example", ""),
            "question": result.get("question", ""),
            "insight": result.get("insight", ""),
            "encouragement": result.get("encouragement", ""),
            "raw_response": result,
            "temperature_used": temperature,
            "mode_used": teaching_mode,
            "emotion_detected": emotion
        }
        
    except Exception as e:
        print(f"[ADAPTIVE] Error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "explanation": "",
            "example": "",
            "question": ""
        }
