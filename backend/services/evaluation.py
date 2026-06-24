#evaluation.py
"""
Answer Evaluation Service
Evaluates student answers to AI-generated questions using keyword matching
"""


def extract_question(response_text: str) -> str:
    """
    Extract the question from AI response.
    Looks for the Quick Check section.
    
    Args:
        response_text: Full AI response with structure
    
    Returns:
        Extracted question or empty string
    """
    lines = response_text.split("\n")
    
    in_question_section = False
    question = ""
    
    for line in lines:
        line_stripped = line.strip()
        
        # Look for Quick Check marker
        if "quick check" in line_stripped.lower() or "❓" in line_stripped:
            in_question_section = True
            continue
        
        # If we found section marker, capture next non-empty line
        if in_question_section:
            if line_stripped and not line_stripped.startswith("-"):
                question = line_stripped
                break
    
    return question


def evaluate_answer(user_answer: str, topic: str, ai_question: str) -> dict:
    """
    SIMPLIFIED evaluation - demo version.
    Just checking: did they give a real answer or not?
    """
    text = user_answer.lower().strip()
    
    # If answer is just "yes" or "no", that's TOO SHORT (questions shouldn't be yes/no anyway)
    if text in ["yes", "no", "yeah", "nope", "yep", "nah", "maybe", "idk"]:
        return {
            "result": "incorrect",
            "feedback": "👍 I need more detail. Can you explain your thinking?",
            "next_mode": "teach_basic"
        }
    
    # If answer is too short, they don't know
    if len(text) < 5:
        return {
            "result": "incorrect",
            "feedback": "👍 No problem, let me explain it simply.",
            "next_mode": "simplify"
        }
    
    # If they say "don't know" or "not" or "cant" / "can't"
    if "not" in text or "dont" in text or "don't" in text or "no idea" in text or "cant" in text or "can't" in text:
        # BUT: if they're saying "CAN'T" in response to "can you explain", different handling
        # Most likely: they don't understand
        return {
            "result": "incorrect",
            "feedback": "👍 No problem, let me explain it simply.",
            "next_mode": "simplify"
        }
    
    # Check for key concepts (function, steps, data, process, learns, grows, calls, itself)
    key_concepts = ["function", "steps", "data", "process", "learns", "grows", "calls", "itself", "repeat", "sequence", "solve", "problem", "pattern", "example", "example"]
    concept_count = sum(1 for word in key_concepts if word in text)
    
    if concept_count >= 2:
        # They mentioned 2+ key concepts - that's correct
        return {
            "result": "correct",
            "feedback": "✅ Good! That's correct.\n\nLet's go deeper...",
            "next_mode": "advanced"
        }
    elif concept_count == 1:
        # They mentioned 1 key concept - partial
        return {
            "result": "partial",
            "feedback": "👍 You're close! Let me refine it.",
            "next_mode": "teach_basic"
        }
    else:
        # No key concepts mentioned but they tried - partial
        return {
            "result": "partial",
            "feedback": "👍 You're on the right track! Let me refine it.",
            "next_mode": "teach_basic"
        }


def is_likely_answering(user_text: str, conversation_state: str) -> bool:
    """
    Determine if user is answering a question vs asking a new one.
    
    Args:
        user_text: User input
        conversation_state: Current state ("question_asked", "idle", etc.)
    
    Returns:
        True if user is likely answering
    """
    
    # If question was just asked, user is probably answering
    if conversation_state == "question_asked":
        return True
    
    # Check question indicators (if state is idle, but text looks like answer)
    question_indicators = ["what", "how", "why", "can you", "explain", "tell me", "help"]
    user_lower = user_text.lower()
    
    # If user is asking, not answering
    if any(indicator in user_lower for indicator in question_indicators):
        return False
    
    # If no question was asked yet, user is not answering
    if conversation_state != "question_asked":
        return False
    
    return True


def format_teaching_feedback(evaluation_result: dict, explanation: str = "") -> str:
    """
    Format the feedback and next explanation.
    
    Args:
        evaluation_result: Result from evaluate_answer()
        explanation: Optional new explanation if answer was wrong
    
    Returns:
        Formatted feedback string
    """
    feedback = evaluation_result.get("feedback", "")
    
    if evaluation_result["result"] == "correct":
        return f"{feedback} Now let's explore this more."
    
    if evaluation_result["result"] == "partial":
        return f"{feedback}"
    
    return f"{feedback} Here's a clearer explanation:"
