import API_BASE_URL from '../config';

const FRIEND_CHAT_BASE_URL = 'http://localhost:8000/friend-chat';

/**
 * Friend Chat API Service
 * Handles REST API calls for message history, preferences, and settings
 */

class FriendChatService {
  /**
   * Fetch message history with a friend
   * @param {string} userId - Current user ID
   * @param {string} friendId - Friend's user ID
   * @param {number} page - Page number (default: 1)
   * @param {number} pageSize - Messages per page (default: 50)
   * @returns {Promise} - History data with pagination info
   */
  static async getMessageHistory(userId, friendId, page = 1, pageSize = 50) {
    try {
      const response = await fetch(
        `${FRIEND_CHAT_BASE_URL}/history/${friendId}?user_id=${userId}&page=${page}&page_size=${pageSize}`
      );
      if (!response.ok) {
        throw new Error(`Failed to fetch history: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('[FriendChatService] Error fetching message history:', error);
      throw error;
    }
  }

  /**
   * Get user's translation preferences
   * @param {string} userId - User ID
   * @returns {Promise} - User preferences object
   */
  static async getPreferences(userId) {
    try {
      const response = await fetch(`${FRIEND_CHAT_BASE_URL}/preferences?user_id=${userId}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch preferences: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('[FriendChatService] Error fetching preferences:', error);
      throw error;
    }
  }

  /**
   * Update user's translation preferences
   * @param {string} userId - User ID
   * @param {Object} preferences - Preferences object
   * @param {string} preferences.preferred_language - Language code (e.g., 'en', 'es')
   * @param {boolean} preferences.auto_translate - Enable auto-translation
   * @returns {Promise} - Success response
   */
  static async updatePreferences(userId, preferences) {
    try {
      const response = await fetch(
        `${FRIEND_CHAT_BASE_URL}/preferences?user_id=${userId}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(preferences),
        }
      );
      if (!response.ok) {
        throw new Error(`Failed to update preferences: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('[FriendChatService] Error updating preferences:', error);
      throw error;
    }
  }

  /**
   * Get list of currently online users
   * @returns {Promise} - Array of online user IDs
   */
  static async getOnlineStatus() {
    try {
      const response = await fetch(`${FRIEND_CHAT_BASE_URL}/online-status`);
      if (!response.ok) {
        throw new Error(`Failed to fetch online status: ${response.statusText}`);
      }
      const data = await response.json();
      return data.online_users || [];
    } catch (error) {
      console.error('[FriendChatService] Error fetching online status:', error);
      throw error;
    }
  }

  /**
   * Get list of supported languages for translation
   * @returns {Promise} - Object mapping language codes to names
   */
  static async getSupportedLanguages() {
    try {
      const response = await fetch(`${FRIEND_CHAT_BASE_URL}/supported-languages`);
      if (!response.ok) {
        throw new Error(`Failed to fetch languages: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error('[FriendChatService] Error fetching supported languages:', error);
      throw error;
    }
  }

  /**
   * Format message for display
   * Shows translated text with original as fallback
   */
  static formatMessage(message) {
    return {
      ...message,
      displayText: message.translated_text || message.original_text,
      originalText: message.original_text,
      hasTranslation: message.translated_text && message.translated_text !== message.original_text,
    };
  }

  /**
   * Format batch of messages
   */
  static formatMessages(messages) {
    return messages.map((msg) => this.formatMessage(msg));
  }
}

export default FriendChatService;
