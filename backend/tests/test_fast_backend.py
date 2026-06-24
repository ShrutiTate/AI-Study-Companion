import pytest
from backend.agents.agent_coordinator import calculate_new_stable_level
from backend.services.ai_tutor_production import detect_intent

def test_calculate_new_stable_level():
    # Test emotional override (frustrated -> beginner)
    level, conf, cd = calculate_new_stable_level(
        current_level="intermediate",
        current_stable_confidence=0.5,
        message_understanding="low",
        concept_mastery={"conceptA": 0.8},
        emotion="frustrated",
        attempt_count=1,
        cooldown_remaining=0
    )
    assert level == "beginner"
    assert cd == 2

    # Test cooldown prevents change
    level, conf, cd = calculate_new_stable_level(
        current_level="intermediate",
        current_stable_confidence=0.5,
        message_understanding="low",
        concept_mastery={"conceptA": 0.2},
        emotion="neutral",
        attempt_count=1,
        cooldown_remaining=1
    )
    assert level == "intermediate"
    assert cd == 0

    # Test high mastery promotes to advanced if engaged
    level, conf, cd = calculate_new_stable_level(
        current_level="intermediate",
        current_stable_confidence=0.5,
        message_understanding="high",
        concept_mastery={"conceptA": 0.9, "conceptB": 0.8},
        emotion="engaged",
        attempt_count=2,
        cooldown_remaining=0
    )
    assert level == "advanced"
    assert cd == 2

def test_detect_intent():
    # Test keywords fallback or basic identification
    # We mock the LLM internally if possible or rely on the keyword fallback.
    # Because Groq requires an API key, we test the keyword logic by ensuring
    # clear intent words trigger the fallback if LLM is mocked or fails.
    
    intent = detect_intent("I don't understand this", current_concept="test")
    # Even without LLM, "don't understand" should yield 'confused' or similar
    assert intent in ["confused", "question", "chat"] # Might vary based on LLM response if live
    
    intent2 = detect_intent("hello there", current_concept="test")
    assert intent2 in ["chat", "greeting"]
