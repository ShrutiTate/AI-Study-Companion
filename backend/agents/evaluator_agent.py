#evaluator_agent.py
"""
Answer Evaluator Agent - Determines if student answer is correct, partial, or confused

This agent runs BEFORE the tutor agent to:
1. Check if student is answering a question (vs asking a new question)
2. Evaluate quality of the answer
3. Return appropriate feedback type

This prevents repetition of explanations!
"""

from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

EVALUATOR_PROMPT = """
You are an evaluation agent that determines if a student's answer is correct, confused, or partial.

Task:
Analyze the student's answer to a question and return ONE word evaluation only.

Context:
- Topic: {topic}
- Question Asked: {question}
- Student Answer: {student_message}

RETURN ONLY ONE OF THESE WORDS (nothing else):
- correct
- partial  
- confused
- unanswering

Examples:

Question: "What is a machine?"
Answer: "A fan"
Return: correct

Question: "What is a machine?"
Answer: "I don't know"
Return: confused

Question: "What is a machine?"
Answer: "What is electricity?"
Return: unanswering

Question: "What is a machine?"
Answer: "A machine uses energy"
Return: partial
"""


def evaluate_answer(topic: str, previous_question: str, student_message: str):
    """
    Evaluate if student's message is an answer to the question, and if so, how good it is.
    
    Args:
        topic: The learning topic (e.g., "machines", "lever")
        previous_question: The question the tutor asked
        student_message: The student's response
    
    Returns:
        dict: {
            "evaluation": "correct|partial|confused|unanswering",
            "reasoning": "why this evaluation",
            "should_praise": bool
        }
    """
    
    if not previous_question:
        # No previous question, so student is not answering - they're asking
        return {
            "evaluation": "unanswering",
            "reasoning": "No previous question to answer",
            "should_praise": False
        }
    
    # Build prompt
    prompt = EVALUATOR_PROMPT.format(
        topic=topic,
        question=previous_question,
        student_message=student_message
    )
    
    try:
        # Call Groq LLM
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Very low for consistent evaluation
            max_tokens=20  # Just need a single word
        )
        
        result_text = response.choices[0].message.content.strip().lower()
        
        # Parse simple word response
        # Extract the evaluation type from the response
        valid_types = ["correct", "partial", "confused", "unanswering"]
        
        for eval_type in valid_types:
            if eval_type in result_text:
                return {
                    "evaluation": eval_type,
                    "reasoning": f"LLM evaluation: {eval_type}",
                    "should_praise": eval_type in ["correct", "partial"]
                }
        
        # If couldn't parse, use fallback
        print(f"[EVALUATOR] Could not parse LLM response: {result_text}")
        return evaluate_answer_fallback(student_message)
    
    except Exception as e:
        print(f"[EVALUATOR] Error: {e}")
        return evaluate_answer_fallback(student_message)


def evaluate_answer_fallback(student_message: str):
    """
    Fallback rule-based evaluation if LLM fails.
    Simple but effective.
    """
    
    text_lower = student_message.lower()
    
    # Check for confusion signals
    if any(word in text_lower for word in ["don't know", "idk", "not sure", "confused", "i don't", "dunno"]):
        return {
            "evaluation": "confused",
            "reasoning": "Student expressed confusion",
            "should_praise": False
        }
    
    # Check for asking questions instead of answering
    if "?" in student_message:
        return {
            "evaluation": "unanswering",
            "reasoning": "Student asked a question instead of answering",
            "should_praise": False
        }
    
    # If message is short and direct, likely an answer
    if len(student_message.split()) <= 5:
        return {
            "evaluation": "correct",
            "reasoning": "Direct answer provided",
            "should_praise": True
        }
    
    # Otherwise it's a partial/related response
    return {
        "evaluation": "partial",
        "reasoning": "Related response but incomplete",
        "should_praise": True
    }


def generate_evaluation_response(evaluation: dict, student_message: str, topic: str) -> str:
    """
    Generate appropriate response based on evaluation.
    
    This is called if evaluation is NOT "unanswering" (i.e., student DID answer).
    """
    
    eval_type = evaluation["evaluation"]
    reasoning = evaluation["reasoning"]
    should_praise = evaluation["should_praise"]
    
    if eval_type == "correct":
        return f"✅ Yes! Exactly! {student_message} is a great example of {topic}.\n\nNow let's explore this further. What else do you know about {topic}?"
    
    elif eval_type == "partial":
        return f"✅ Good thinking! You're on the right track. {student_message} relates to {topic}.\n\nHere's more complete picture: Let me clarify the full concept..."
    
    elif eval_type == "confused":
        return f"I understand - let me explain {topic} in a simpler way.\n\nThink of it like this: {topic} are things that..."
    
    else:
        # Default for "unanswering" or unknown
        return f"I see! Let me help you understand {topic} more clearly..."
