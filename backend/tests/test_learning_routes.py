# backend/tests/test_learning_routes.py
"""
Test suite for learning route response schema consistency.
Focuses on repair/refusal/overwhelm branches to ensure no KeyError.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestLearningResponseSchema:
    """Validate all /learning/learn responses have required fields."""
    
    def test_overwhelm_branch_has_all_required_fields(self, client, mock_session):
        """
        CRITICAL TEST: Repair branch must return complete schema.
        This was failing with KeyError: 'concept_index'
        """
        # Setup session in DB
        from backend.db.mongo import db
        db["sessions"].insert_one(mock_session)
        
        # Mock the overwhelm detector
        with patch("backend.services.ai_tutor_production.is_overwhelmed", return_value=True):
            with patch("backend.services.ai_tutor_production.generate_lesson") as mock_lesson:
                # Mock lesson response
                mock_lesson.return_value = {
                    "success": True,
                    "response": "Let me simplify this.",
                    "strategy_used": "ultra_simple"
                }
                
                response = client.post(
                    "/learning/learn",
                    json={
                        "text": "I can't handle this!",
                        "user_id": "test-user-123",
                        "session_id": "test-session-123"
                    }
                )
        
        # Assertions
        assert response.status_code == 200
        body = response.json()
        
        # Check all REQUIRED fields exist
        required_fields = [
            "response", "text", "intent", "concept_index", "concepts_total",
            "advance_curriculum", "emotion", "cognitive_load",
            "cognitive_load_score", "session_id", "concept", "status",
            "stable_teaching_level", "evaluation"
        ]
        
        for field in required_fields:
            assert field in body, f"❌ Missing required field: '{field}'"
            # None is only allowed for evaluation field
            if field != "evaluation":
                assert body[field] is not None, f"❌ Field '{field}' cannot be None"
        
        # Type checks
        assert isinstance(body["concept_index"], int), "concept_index must be int"
        assert isinstance(body["advance_curriculum"], bool), "advance_curriculum must be bool"
        assert isinstance(body["cognitive_load_score"], int), "cognitive_load_score must be int"
        
        # Schema validation for overwhelm
        assert body["intent"] == "repair"
        assert body["advance_curriculum"] is False
        assert body["concept_index"] >= 0
        
        print(f"✅ Overwhelm branch passed: {body['intent']}")
    
    
    def test_refusal_branch_has_all_required_fields(self, client, mock_session):
        """
        CRITICAL TEST: Refusal path must return complete schema.
        """
        from backend.db.mongo import db
        db["sessions"].insert_one(mock_session)
        
        with patch("backend.services.ai_tutor_production.detect_intent", return_value="refusal"):
            with patch("backend.services.ai_tutor_production.generate_lesson") as mock_lesson:
                mock_lesson.return_value = {
                    "success": True,
                    "response": "I understand. That's okay.",
                    "strategy_used": "empathy"
                }
                
                with patch("backend.services.emotion.detect_emotion", return_value="frustrated"):
                    response = client.post(
                        "/learning/learn",
                        json={
                            "text": "I don't want to continue",
                            "user_id": "test-user-123",
                            "session_id": "test-session-123"
                        }
                    )
        
        assert response.status_code == 200
        body = response.json()
        
        # Validate schema
        required_fields = [
            "response", "text", "intent", "concept_index", "concepts_total",
            "advance_curriculum", "emotion", "cognitive_load",
            "cognitive_load_score", "session_id", "concept", "status",
            "stable_teaching_level", "evaluation"
        ]
        
        for field in required_fields:
            assert field in body, f"❌ Refusal: Missing field '{field}'"
        
        # Refusal-specific validations
        assert body["intent"] == "refusal"
        assert body["advance_curriculum"] is False
        assert body["concept_index"] in [0, 1, 2, 3, 4]  # Valid range
        
        print(f"✅ Refusal branch passed: {body['intent']}")
    
    
    def test_repair_intent_has_all_required_fields(self, client, mock_session):
        """
        CRITICAL TEST: Repair intent path must return complete schema.
        """
        from backend.db.mongo import db
        db["sessions"].insert_one(mock_session)
        
        with patch("backend.services.ai_tutor_production.detect_intent", return_value="repair"):
            with patch("backend.services.ai_tutor_production.generate_lesson") as mock_lesson:
                mock_lesson.return_value = {
                    "success": True,
                    "response": "Let me clarify that for you.",
                    "strategy_used": "definition"
                }
                
                with patch("backend.services.emotion.detect_emotion", return_value="confused"):
                    response = client.post(
                        "/learning/learn",
                        json={
                            "text": "I'm confused about that",
                            "user_id": "test-user-123",
                            "session_id": "test-session-123"
                        }
                    )
        
        assert response.status_code == 200
        body = response.json()
        
        # All required fields must be present
        assert "concept_index" in body, "❌ Missing concept_index"
        assert isinstance(body["concept_index"], int), "concept_index must be int"
        assert body["intent"] == "repair"
        assert body["advance_curriculum"] is False
        
        print(f"✅ Repair intent passed: {body['intent']}")
    
    
    def test_answer_correct_advances_with_valid_schema(self, client, mock_session):
        """
        PROGRESSION TEST: Correct answer should advance concept_index.
        """
        from backend.db.mongo import db
        db["sessions"].insert_one(mock_session)
        
        with patch("backend.services.ai_tutor_production.detect_intent", return_value="answer"):
            with patch("backend.services.ai_tutor_production.evaluate_answer", return_value="correct"):
                with patch("backend.services.ai_tutor_production.generate_lesson") as mock_lesson:
                    mock_lesson.return_value = {
                        "success": True,
                        "response": "Excellent! Let's move to the next concept.",
                        "strategy_used": "definition"
                    }
                    
                    with patch("backend.services.emotion.detect_emotion", return_value="engaged"):
                        response = client.post(
                            "/learning/learn",
                            json={
                                "text": "AI is about making computers learn",
                                "user_id": "test-user-123",
                                "session_id": "test-session-123"
                            }
                        )
        
        assert response.status_code == 200
        body = response.json()
        
        # Should have advanced
        assert body["concept_index"] == 1, f"concept_index should be 1, got {body['concept_index']}"
        assert body["advance_curriculum"] is True
        
        # Schema completeness
        assert "response" in body
        assert "emotion" in body
        assert "cognitive_load_score" in body
        
        print(f"✅ Answer progression passed: concept_index={body['concept_index']}")
    
    
    def test_missing_session_returns_404_not_500(self, client):
        """
        ERROR HANDLING: Missing session should return 404, not 500 KeyError.
        """
        response = client.post(
            "/learning/learn",
            json={
                "text": "Hello",
                "user_id": "test-user-123",
                "session_id": "nonexistent-session"
            }
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        assert "not found" in response.json()["detail"].lower()
        print(f"✅ 404 error handling works correctly")
    
    
    def test_chitchat_intent_returns_valid_schema(self, client, mock_session):
        """Test chitchat/off-topic intent has complete response schema."""
        from backend.db.mongo import db
        db["sessions"].insert_one(mock_session)
        
        with patch("backend.services.ai_tutor_production.detect_intent", return_value="chitchat"):
            with patch("backend.services.ai_tutor_production.generate_lesson") as mock_lesson:
                mock_lesson.return_value = {
                    "success": True,
                    "response": "That's interesting! Let's get back to learning.",
                    "strategy_used": "definition"
                }
                
                with patch("backend.services.emotion.detect_emotion", return_value="neutral"):
                    response = client.post(
                        "/learning/learn",
                        json={
                            "text": "Hey, how's your day?",
                            "user_id": "test-user-123",
                            "session_id": "test-session-123"
                        }
                    )
        
        assert response.status_code == 200
        body = response.json()
        
        assert body["intent"] == "chitchat"
        assert body["concept_index"] >= 0
        assert "advance_curriculum" in body
        assert "emotion" in body
        
        print(f"✅ Chitchat intent passed: {body['intent']}")
    
    
    def test_expand_intent_returns_valid_schema(self, client, mock_session):
        """Test expand intent has complete response schema."""
        from backend.db.mongo import db
        db["sessions"].insert_one(mock_session)
        
        with patch("backend.services.ai_tutor_production.detect_intent", return_value="expand"):
            with patch("backend.services.ai_tutor_production.generate_lesson") as mock_lesson:
                mock_lesson.return_value = {
                    "success": True,
                    "response": "Let me go deeper into this concept.",
                    "strategy_used": "definition"
                }
                
                with patch("backend.services.emotion.detect_emotion", return_value="engaged"):
                    response = client.post(
                        "/learning/learn",
                        json={
                            "text": "Tell me more about AI",
                            "user_id": "test-user-123",
                            "session_id": "test-session-123"
                        }
                    )
        
        assert response.status_code == 200
        body = response.json()
        
        assert body["intent"] == "expand"
        assert body["advance_curriculum"] is False  # Expand doesn't advance
        assert "concept_index" in body
        assert isinstance(body["concept_index"], int)
        
        print(f"✅ Expand intent passed: {body['intent']}")


class TestCurriculumProgression:
    """Test that curriculum progression freezes during repair/refusal."""
    
    def test_overwhelm_freezes_curriculum(self, client, mock_session):
        """Overwhelm should NOT advance curriculum."""
        from backend.db.mongo import db
        db["sessions"].insert_one(mock_session)
        
        with patch("backend.services.ai_tutor_production.is_overwhelmed", return_value=True):
            with patch("backend.services.ai_tutor_production.generate_lesson") as mock_lesson:
                mock_lesson.return_value = {
                    "success": True,
                    "response": "Let's simplify.",
                    "strategy_used": "ultra_simple"
                }
                
                response = client.post(
                    "/learning/learn",
                    json={
                        "text": "This is too much!",
                        "user_id": "test-user-123",
                        "session_id": "test-session-123"
                    }
                )
        
        body = response.json()
        assert body["advance_curriculum"] is False, "Overwhelm should freeze curriculum"
        print(f"✅ Overwhelm correctly freezes curriculum")
    
    
    def test_refusal_freezes_curriculum(self, client, mock_session):
        """Refusal should NOT advance curriculum."""
        from backend.db.mongo import db
        db["sessions"].insert_one(mock_session)
        
        with patch("backend.services.ai_tutor_production.detect_intent", return_value="refusal"):
            with patch("backend.services.ai_tutor_production.generate_lesson") as mock_lesson:
                mock_lesson.return_value = {
                    "success": True,
                    "response": "That's okay.",
                    "strategy_used": "empathy"
                }
                
                with patch("backend.services.emotion.detect_emotion", return_value="frustrated"):
                    response = client.post(
                        "/learning/learn",
                        json={
                            "text": "Stop teaching me",
                            "user_id": "test-user-123",
                            "session_id": "test-session-123"
                        }
                    )
        
        body = response.json()
        assert body["advance_curriculum"] is False, "Refusal should freeze curriculum"
        print(f"✅ Refusal correctly freezes curriculum")
