# backend/tests/conftest.py
"""
Pytest fixtures and configuration for EchoConnect tests.
Provides test client, mock sessions, and database cleanup.
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi.testclient import TestClient
from backend.main import app
from backend.db.mongo import db


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_session():
    """Standard test session with all required fields."""
    return {
        "session_id": "test-session-123",
        "user_id": "test-user-123",
        "status": "active",
        "current_concept": "What is AI",
        "concept_index": 0,
        "concepts": [
            "What is AI",
            "Machine Learning",
            "Neural Networks",
            "Deep Learning",
            "Practical Applications"
        ],
        "teaching_mode": "teach_basic",
        "emotion": "neutral",
        "cognitive_load_score": 1,
        "explained_concepts": [],
        "avoid_list": [],
        "attempt_count": 0,
        "depth_level": "intro",
        "lesson_stage": "introduction",
        "stable_teaching_level": "intermediate",
        "conversation_state": "active",
        "created_at": datetime.now(),
        "last_interaction": datetime.now()
    }


@pytest.fixture(autouse=True)
def cleanup_test_db():
    """
    Cleanup test data after each test.
    This fixture runs automatically after every test.
    """
    yield
    # Remove all test sessions
    db["sessions"].delete_many({"session_id": {"$regex": "^test-"}})


@pytest.fixture
def mock_groq_response():
    """Create a mock Groq API response."""
    def _create_response(text: str):
        mock = MagicMock()
        mock.choices = [MagicMock()]
        mock.choices[0].message.content = text
        return mock
    return _create_response
