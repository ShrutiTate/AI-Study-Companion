"""
Automated Verification Suite for Session Onboarding & Orientation Layer

Tests:
1. Welcome Flow: starting a session puts it in ONBOARDING and returns a non-technical welcome roadmap.
2. Level Classification: prior experience keywords are diagnosed properly to beginner/intermediate/advanced.
3. Phase Transition: answering the onboarding prompt moves phase to LEARNING and starts first concept lesson.
4. Resume Greeting: resuming a session prepends a warm "Welcome back!" bridge on the student's next turn.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path so we can import backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
import backend.db.mongo as mongo

# ============================================
# IN-MEMORY MOCK DB FOR PERFECT ISOLATION
# ============================================
class MockMongoCollection:
    def __init__(self):
        self.data = {}

    def insert_one(self, doc):
        self.data[doc["session_id"]] = doc.copy()
        # Mock result class
        class InsertResult:
            inserted_id = "mock_id"
        return InsertResult()

    def update_one(self, filter_dict, update_dict, *args, **kwargs):
        session_id = filter_dict.get("session_id")
        if session_id in self.data:
            # apply update_dict operations
            set_ops = update_dict.get("$set", {})
            for k, v in set_ops.items():
                self.data[session_id][k] = v
        # Mock result class
        class UpdateResult:
            modified_count = 1
        return UpdateResult()

    def find_one(self, filter_dict=None, *args, **kwargs):
        session_id = filter_dict.get("session_id")
        doc = self.data.get(session_id)
        return doc.copy() if doc else None

    def delete_one(self, filter_dict, *args, **kwargs):
        session_id = filter_dict.get("session_id")
        if session_id in self.data:
            del self.data[session_id]
        # Mock result class
        class DeleteResult:
            deleted_count = 1
        return DeleteResult()

# Create collection instances
sessions_collection = MockMongoCollection()

# Monkeypatch backend.db.mongo.db
mongo.db = {
    "sessions": sessions_collection,
    "users": MockMongoCollection(),
    "chat": MockMongoCollection()
}
mongo.sessions_collection = sessions_collection

# Import app after patching the DB
from backend.main import app

client = TestClient(app)

# ============================================
# AUTOMATED VERIFICATION CASES
# ============================================

def test_welcome_flow():
    """Verify that /session/start-teaching yields onboarding welcome roadmap without technical details."""
    print("\n--- Running Test: Welcome Flow ---")
    response = client.post(
        "/session/start-teaching",
        json={
            "user_id": "test_onboarding_user",
            "topic": "Python Basics"
        }
    )
    
    assert response.status_code == 200, "Start teaching request failed"
    data = response.json()
    
    session_id = data["session_id"]
    response_text = data["response"]
    
    print(f"Onboarding Welcome Response: {response_text}")
    
    # 1. Verify we returned onboarding message, not a lesson on variables
    # It should mention Python Basics, roadmap of concepts, and ask about prior experience.
    assert "roadmap" in response_text.lower() or any(c.lower() in response_text.lower() for c in data["concepts"]), "Should mention learning concepts or roadmap"
    assert "experience" in response_text.lower() or "level" in response_text.lower() or "new" in response_text.lower(), "Should ask about prior experience/level"
    
    # Verify negative constraints (no variable coding syntax, etc.)
    assert "=" not in response_text, "Should not teach syntax like variable assignment yet"
    assert "quiz" not in response_text.lower(), "Should not contain quizzes"
    
    # 2. Check DB status
    session = sessions_collection.find_one({"session_id": session_id})
    assert session is not None
    assert session["session_phase"] == "ONBOARDING"
    assert session["onboarding_welcome_sent"] is True
    assert session["concept_index"] == 0
    print("✅ Welcome Flow Test Passed!")
    return session_id


def test_level_classification():
    """Verify that prior experience answers map correctly to beginner, intermediate, advanced levels."""
    print("\n--- Running Test: Level Classification ---")
    from backend.services.tutor_control import infer_level_from_onboarding
    
    # Test beginner keywords
    beg_level1 = infer_level_from_onboarding("I am completely new to coding and have never programmed before")
    assert beg_level1 == "beginner", f"Expected beginner, got {beg_level1}"
    
    beg_level2 = infer_level_from_onboarding("first time learning, absolute beginner no experience")
    assert beg_level2 == "beginner", f"Expected beginner, got {beg_level2}"
    
    # Test intermediate keywords
    int_level1 = infer_level_from_onboarding("I have some basic experience with Python, know the absolute basics")
    assert int_level1 == "intermediate", f"Expected intermediate, got {int_level1}"
    
    int_level2 = infer_level_from_onboarding("took a course on Java in school but pretty rusty")
    assert int_level2 == "intermediate", f"Expected intermediate, got {int_level2}"
    
    # Test advanced keywords
    adv_level1 = infer_level_from_onboarding("I'm an experienced programmer, know syntax and OOP concepts well")
    assert adv_level1 == "advanced", f"Expected advanced, got {adv_level1}"
    
    adv_level2 = infer_level_from_onboarding("expert in algorithms and recursion, just learning python details")
    assert adv_level2 == "advanced", f"Expected advanced, got {adv_level2}"
    
    print("✅ Level Classification Test Passed!")


def test_phase_transition():
    """Verify transitioning from ONBOARDING to LEARNING and getting first concept lesson with warm bridge."""
    print("\n--- Running Test: Phase Transition ---")
    
    # Create an onboarding session where welcome has been sent
    session_id = "transition_test_session"
    user_id = "test_user_onb"
    concepts = ["Variables", "Control Flow", "Functions"]
    
    session_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "topic": "Python Basics",
        "concepts": concepts,
        "concept_index": 0,
        "current_concept": "Variables",
        "messages": [],
        "start_time": datetime.now(),
        "status": "active",
        "emotion": "neutral",
        "attempt_count": 0,
        "last_question": "Prior experience query",
        "conversation_state": "question_asked",
        "stable_teaching_level": "intermediate",
        "cognitive_load_score": 1,
        "depth_level": "intro",
        "lesson_stage": "introduction",
        "explained_concepts": [],
        "avoid_list": [],
        "session_phase": "ONBOARDING",
        "onboarding_welcome_sent": True,
        "resumed_session_pending": False
    }
    sessions_collection.data[session_id] = session_doc
    
    # User replies they are completely new (beginner)
    response = client.post(
        "/learning/learn",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "text": "I am completely new to coding, this is my first time"
        }
    )
    
    assert response.status_code == 200, "Learn post request failed"
    data = response.json()
    response_text = data["text"]
    
    print(f"Transition Lesson Response: {response_text}")
    
    # 1. Verify DB phase transitioned to LEARNING
    updated_session = sessions_collection.find_one({"session_id": session_id})
    assert updated_session["session_phase"] == "LEARNING"
    assert updated_session["stable_teaching_level"] == "beginner"
    assert updated_session["concept_index"] == 0
    
    # 2. Verify warm transition bridge exists in response
    response_lower = response_text.lower()
    assert "beginner" in response_lower or "new" in response_lower or "start" in response_lower, "Should warmly address their beginner level/start"
    assert "variable" in response_lower, "Should teach first concept (Variables)"
    
    print("✅ Phase Transition Test Passed!")


def test_resume_greeting():
    """Verify that resuming a session prepends a warm welcome-back bridge on the student's next turn."""
    print("\n--- Running Test: Resume Greeting ---")
    
    # Create an active learning session in database
    session_id = "resume_test_session"
    user_id = "test_user_res"
    concepts = ["Variables", "Control Flow", "Functions"]
    
    session_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "topic": "Python Basics",
        "concepts": concepts,
        "concept_index": 0,
        "current_concept": "Variables",
        "messages": [],
        "start_time": datetime.now(),
        "status": "completed",  # ended session
        "emotion": "neutral",
        "attempt_count": 0,
        "last_question": "What is a variable?",
        "conversation_state": "question_asked",
        "stable_teaching_level": "intermediate",
        "cognitive_load_score": 1,
        "depth_level": "intro",
        "lesson_stage": "introduction",
        "explained_concepts": [],
        "avoid_list": [],
        "session_phase": "LEARNING",
        "onboarding_welcome_sent": True,
        "resumed_session_pending": False
    }
    sessions_collection.data[session_id] = session_doc
    
    # 1. Resume the session via API
    resume_resp = client.post(f"/session/resume/{session_id}")
    assert resume_resp.status_code == 200, "Resume session failed"
    resume_data = resume_resp.json()
    assert resume_data["status"] == "active"
    
    # Verify the database has resume_session_pending = True
    session_after_resume = sessions_collection.find_one({"session_id": session_id})
    assert session_after_resume["resumed_session_pending"] is True
    assert session_after_resume["status"] == "active"
    
    # 2. Simulate next user message to learn endpoint
    learn_resp = client.post(
        "/learning/learn",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "text": "A variable is a container that stores data values"
        }
    )
    
    assert learn_resp.status_code == 200, "Learn request after resume failed"
    learn_data = learn_resp.json()
    response_text = learn_data["text"]
    
    print(f"Resumed response text: {response_text}")
    
    # 3. Assert welcome-back greeting exists
    assert response_text.startswith("Welcome back!"), "Response must start with 'Welcome back!' bridge"
    assert "resume our lesson" in response_text or "variables" in response_text, "Should refer to the topic/concept being resumed"
    
    # Verify resumed_session_pending is now reset to False
    final_session = sessions_collection.find_one({"session_id": session_id})
    assert final_session["resumed_session_pending"] is False
    
    print("✅ Resume Greeting Test Passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING AUTOMATED SESSION ONBOARDING VERIFICATION SUITE")
    print("=" * 60)
    
    test_welcome_flow()
    test_level_classification()
    test_phase_transition()
    test_resume_greeting()
    
    print("\n" + "=" * 60)
    print("ALL ONBOARDING VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
