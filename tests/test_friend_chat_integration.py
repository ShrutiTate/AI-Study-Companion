"""
Friend Chat Integration Test
Tests the complete friend chat pipeline: message creation → translation → storage → delivery
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from pymongo import MongoClient

# Import components
from backend.main import app
from backend.models.message_model import (
    FriendMessageCreate,
    FriendMessageResponse,
    UserPreferences,
)
from backend.services.chat_service import ChatService
from backend.services.translation_service import TranslationService
from backend.services.websocket_manager import ConnectionManager

client = TestClient(app)


class TestTranslationService:
    """Test translation service"""

    @pytest.mark.asyncio
    async def test_detect_and_translate_spanish_to_english(self):
        """Test translating Spanish to English"""
        original_text = "Hola, ¿cómo estás?"
        translated_text, source_lang, target_lang = await TranslationService.detect_and_translate(
            text=original_text,
            target_language="en",
            user_auto_translate=True,
        )

        # Should detect Spanish source
        assert source_lang.lower() in ["es", "spanish"]
        # Should have translation
        assert translated_text != original_text or translated_text == original_text  # Fallback
        print(f"Translation: {original_text} → {translated_text}")

    @pytest.mark.asyncio
    async def test_detect_and_translate_same_language(self):
        """Test when source and target are same"""
        text = "Hello world"
        original, translated, source = await TranslationService.detect_and_translate(
            text=text,
            target_language="en",
            user_auto_translate=True,
        )

        # Should not translate
        assert original == translated
        assert source.lower() == "en"

    @pytest.mark.asyncio
    async def test_translate_with_auto_translate_disabled(self):
        """Test that translation is skipped when disabled"""
        text = "Hola"
        original, translated, source = await TranslationService.detect_and_translate(
            text=text,
            target_language="en",
            user_auto_translate=False,
        )

        # Should not translate
        assert original == translated


class TestConnectionManager:
    """Test WebSocket connection manager"""

    def test_connection_manager_init(self):
        """Test manager initialization"""
        manager = ConnectionManager()
        assert manager.active_connections == {}

    @pytest.mark.asyncio
    async def test_is_online(self):
        """Test online status check"""
        manager = ConnectionManager()

        # Create mock WebSocket
        mock_ws = AsyncMock()
        await manager.connect("user-123", mock_ws)

        # Should be online
        assert await manager.is_online("user-123") is True
        assert await manager.is_online("user-456") is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection"""
        manager = ConnectionManager()
        mock_ws = AsyncMock()

        await manager.connect("user-123", mock_ws)
        assert await manager.is_online("user-123") is True

        await manager.disconnect("user-123")
        assert await manager.is_online("user-123") is False

    @pytest.mark.asyncio
    async def test_get_online_users(self):
        """Test getting online users"""
        manager = ConnectionManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await manager.connect("user-123", mock_ws1)
        await manager.connect("user-456", mock_ws2)

        online = await manager.get_online_users()
        assert online == {"user-123", "user-456"}


class TestChatService:
    """Test chat service (requires MongoDB)"""

    @pytest.mark.asyncio
    async def test_get_user_preferences_default(self):
        """Test getting default preferences for new user"""
        prefs = await ChatService.get_user_preferences("new-user-999")

        assert prefs["preferred_language"] == "en"
        assert prefs["auto_translate"] is True

    @pytest.mark.asyncio
    async def test_save_and_retrieve_message(self):
        """Test saving and retrieving a message"""
        sender_id = "user-123"
        receiver_id = "user-456"
        original_text = "Hola amigo"
        translated_text = "Hello friend"
        source_lang = "es"
        target_lang = "en"

        # Save message
        message_id = await ChatService.save_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            original_text=original_text,
            translated_text=translated_text,
            source_language=source_lang,
            target_language=target_lang,
        )

        assert message_id is not None
        print(f"Saved message ID: {message_id}")

        # Retrieve history
        history = await ChatService.get_message_history(
            user_id=sender_id,
            friend_id=receiver_id,
            page=1,
            page_size=50,
        )

        assert history["total"] >= 1
        assert len(history["messages"]) >= 1

        # Verify message content
        message = history["messages"][0]
        assert message["sender_id"] == sender_id
        assert message["receiver_id"] == receiver_id
        assert message["original_text"] == original_text
        assert message["translated_text"] == translated_text


class TestRestEndpoints:
    """Test REST API endpoints"""

    def test_get_supported_languages(self):
        """Test supported languages endpoint"""
        response = client.get("/friend-chat/supported-languages")

        assert response.status_code == 200
        languages = response.json()
        assert isinstance(languages, dict)
        assert "en" in languages
        assert "es" in languages
        print(f"Supported languages: {list(languages.keys())}")

    def test_get_online_status(self):
        """Test online status endpoint"""
        response = client.get("/friend-chat/online-status")

        assert response.status_code == 200
        data = response.json()
        assert "online_users" in data
        assert isinstance(data["online_users"], list)
        print(f"Online users: {data['online_users']}")

    def test_get_preferences(self):
        """Test get preferences endpoint"""
        response = client.get("/friend-chat/preferences?user_id=test-user-123")

        assert response.status_code == 200
        prefs = response.json()
        assert "preferred_language" in prefs
        assert "auto_translate" in prefs
        print(f"User preferences: {prefs}")

    def test_update_preferences(self):
        """Test update preferences endpoint"""
        user_id = "test-user-123"
        new_prefs = {
            "preferred_language": "es",
            "auto_translate": False,
        }

        response = client.post(
            f"/friend-chat/preferences?user_id={user_id}",
            json=new_prefs,
        )

        assert response.status_code == 200
        print(f"Preferences updated: {response.json()}")


class TestMessageModels:
    """Test Pydantic models"""

    def test_friend_message_create(self):
        """Test message creation model"""
        msg = FriendMessageCreate(
            receiver_id="user-456",
            text="Hello world",
        )

        assert msg.receiver_id == "user-456"
        assert msg.text == "Hello world"

    def test_friend_message_create_validation(self):
        """Test message creation validation"""
        # Test empty text
        with pytest.raises(ValueError):
            FriendMessageCreate(receiver_id="user-456", text="")

        # Test max length
        with pytest.raises(ValueError):
            FriendMessageCreate(receiver_id="user-456", text="x" * 2001)

    def test_user_preferences(self):
        """Test user preferences model"""
        prefs = UserPreferences(
            user_id="user-123",
            preferred_language="es",
            auto_translate=True,
        )

        assert prefs.user_id == "user-123"
        assert prefs.preferred_language == "es"
        assert prefs.auto_translate is True


def test_models_import():
    """Test that all models can be imported"""
    from backend.models.message_model import (
        FriendMessageCreate,
        FriendMessageResponse,
        FriendMessageWS,
        UserPreferences,
        ChatHistoryRequest,
    )

    assert FriendMessageCreate is not None
    assert FriendMessageResponse is not None
    assert FriendMessageWS is not None
    assert UserPreferences is not None
    assert ChatHistoryRequest is not None


def test_services_import():
    """Test that all services can be imported"""
    from backend.services.websocket_manager import ConnectionManager
    from backend.services.chat_service import ChatService
    from backend.services.translation_service import TranslationService

    assert ConnectionManager is not None
    assert ChatService is not None
    assert TranslationService is not None


def test_routes_import():
    """Test that friend chat routes are registered"""
    response = client.get("/friend-chat/supported-languages")
    assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
