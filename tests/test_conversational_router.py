"""
Automated Verification Suite for Dynamic Intent & Relevance Router

This file contains automated tests for:
1. Case A (Refusal): Student wants to stop studying -> Verify state resets, progression freezes, and response tone is supportive.
2. Case B (Repair): Student corrects a tutor mistake -> Verify the AI apologizes and corrects the record.
3. Case C (Doubt/Question): Student asks a conceptual question -> Verify the AI explains the doubt directly and does not advance the topic index.

Run: python -m pytest tests/test_conversational_router.py -v
  or: python tests/test_conversational_router.py
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

def create_test_session():
    """Initializes a standardized learning session in mock DB"""
    session_id = "test_router_session_123"
    user_id = "test_user_456"
    
    # Standard curriculum for recursion
    concepts = [
        "What is recursion", 
        "Base case in recursion", 
        "Recursive call", 
        "Stack frames", 
        "Practical recursion example"
    ]
    
    session_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "topic": "Recursion",
        "concepts": concepts,
        "concept_index": 1,  # Currently on "Base case in recursion" (index 1)
        "current_concept": "Base case in recursion",
        "messages": [],
        "start_time": datetime.now(),
        "status": "active",
        "emotion": "neutral",
        "attempt_count": 0,
        "last_question": "Why is a base case necessary in a recursive function?",
        "conversation_state": "question_asked",
        "stable_teaching_level": "intermediate",
        "cognitive_load_score": 1,
        "depth_level": "intro",
        "lesson_stage": "introduction",
        "explained_concepts": ["What is recursion"],
        "avoid_list": []
    }
    
    # Store in mock db
    sessions_collection.data[session_id] = session_doc
    return session_id, user_id

# ============================================
# AUTOMATED VERIFICATION CASES
# ============================================

def test_case_a_refusal():
    """Case A (Refusal): User sends 'i dont want to study now'"""
    print("\n--- Running Case A: Refusal ---")
    session_id, user_id = create_test_session()
    
    # Send refusal message
    response = client.post(
        "/learning/learn",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "text": "shut up i dont want to study now"
        }
    )
    
    assert response.status_code == 200, "Refusal request failed"
    data = response.json()
    
    # 1. Verify progression froze (index didn't advance)
    assert data["concept_index"] == 1, "Concept index should not advance on refusal"
    
    # 2. Verify state resets / updates correctly in the DB
    updated_session = sessions_collection.find_one({"session_id": session_id})
    assert updated_session["conversation_state"] == "idle", "Conversation state should be reset to idle on refusal"
    assert updated_session["cognitive_load_score"] == 5, "Cognitive load should be capped to 5 on refusal to trigger pause"
    
    # 3. Verify response tone is supportive/non-academic (doesn't ask questions or teach recursive base cases)
    response_text = data["text"].lower()
    print(f"Refusal Response: {data['text']}")
    
    assert "?" not in data["text"], "AI should not ask questions when student wants to stop"
    assert any(w in response_text for w in ["break", "pause", "rest", "stop", "understand", "take a", "no worries", "totally", "okay"]), \
        "AI should offer support, pause, or rest"
    print("✅ Case A (Refusal) Passed!")


def test_case_b_repair():
    """Case B (Repair): User corrects a tutor error"""
    print("\n--- Running Case B: Repair ---")
    session_id, user_id = create_test_session()
    
    # Add a mock previous AI message containing a bad analogy context
    session_doc = sessions_collection.find_one({"session_id": session_id})
    session_doc["last_substantive_message"] = {
        "text": "Your sandwich analogy for a recursive call stack is great, let's explore it!",
        "timestamp": datetime.now()
    }
    sessions_collection.data[session_id] = session_doc
    
    # Student corrects the AI: "I didn't say sandwich, I said boxes!"
    response = client.post(
        "/learning/learn",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "text": "I didn't say sandwich, you are confusing me"
        }
    )
    
    assert response.status_code == 200, "Repair request failed"
    data = response.json()
    
    # 1. Verify index didn't advance
    assert data["concept_index"] == 1, "Concept index should not advance on repair"
    
    # 2. Verify the response tone: AI must apologize/correct its misunderstanding
    response_text = data["text"].lower()
    print(f"Repair Response: {data['text']}")
    
    apology_keywords = ["sorry", "apologize", "my mistake", "my bad", "misunderstood", "correct", "thank you"]
    assert any(k in response_text for k in apology_keywords), "AI must apologize/correct itself when student points out a mistake"
    print("✅ Case B (Repair) Passed!")


def test_case_c_doubt():
    """Case C (Doubt/Question): User asks a conceptual question"""
    print("\n--- Running Case C: Doubt ---")
    session_id, user_id = create_test_session()
    
    # User asks a conceptual doubt instead of answering the base case prompt
    response = client.post(
        "/learning/learn",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "text": "But why does recursion actually need a base case? What happens without it?"
        }
    )
    
    assert response.status_code == 200, "Doubt request failed"
    data = response.json()
    
    # 1. Verify concept index did NOT advance
    assert data["concept_index"] == 1, "Concept index should not advance when student is asking a doubt"
    
    # 2. Verify the doubt is addressed directly
    response_text = data["text"].lower()
    print(f"Doubt Response: {data['text']}")
    
    doubt_keywords = ["infinite", "stop", "crash", "stack overflow", "memory", "forever", "loop", "base case", "nesting"]
    assert any(k in response_text for k in doubt_keywords), "AI should explain what happens without a base case (infinite recursion / stack overflow)"
    
    # 3. Verify it does not treat it as a wrong answer (attempt count doesn't increment in DB)
    updated_session = sessions_collection.find_one({"session_id": session_id})
    assert updated_session["attempt_count"] == 0, "Attempt count should not increment when student asks a question"
    print("✅ Case C (Doubt) Passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING AUTOMATED INTENT ROUTING VERIFICATION SUITE")
    print("=" * 60)
    
    test_case_a_refusal()
    test_case_b_repair()
    test_case_c_doubt()
    
    print("\n" + "=" * 60)
    print("ALL ROUTER VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
