import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import useWebSocket from '../hooks/useWebSocket';
import FriendChatService from '../services/friendChatService';

/**
 * Friend Chat Context
 * Manages global state for the friend chat system
 */
const FriendChatContext = createContext();

export const useFriendChat = () => {
  const context = useContext(FriendChatContext);
  if (!context) {
    throw new Error('useFriendChat must be used within FriendChatProvider');
  }
  return context;
};

export const FriendChatProvider = ({ userId, children }) => {
  // WebSocket state
  const [messages, setMessages] = useState({});
  const [activeChat, setActiveChat] = useState(null);
  const [typingIndicators, setTypingIndicators] = useState({});
  const [preferences, setPreferences] = useState(null);
  const [supportedLanguages, setSupportedLanguages] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastMessage, setLastMessage] = useState(null);
  const messageCounterRef = React.useRef(0);

  // Initialize WebSocket connection with memoized parameters to prevent connection teardowns
  const wsUrl = React.useMemo(() => {
    const wsHost = `${window.location.hostname}:8000`;
    return `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${wsHost}/friend-chat/ws/${userId}`;
  }, [userId]);

  const wsOptions = React.useMemo(() => ({
    url: wsUrl,
  }), [wsUrl]);

  // Handle incoming WebSocket messages (memoized to keep hook dependencies stable)
  const handleWebSocketMessage = useCallback((data) => {
    const { type, sender_id, receiver_id } = data;
    
    // Store the raw message for other contexts to react to
    // Wrap with a unique _seq to guarantee React sees a new object every time
    messageCounterRef.current += 1;
    setLastMessage({ ...data, _seq: messageCounterRef.current });
    console.log('[FriendChatContext] lastMessage set:', data.type, 'seq:', messageCounterRef.current);

    switch (type) {
      case 'message':
        // Add message to appropriate chat thread
        const chatKey = sender_id === userId ? receiver_id : sender_id;
        setMessages((prev) => ({
          ...prev,
          [chatKey]: [...(prev[chatKey] || []), FriendChatService.formatMessage(data)],
        }));
        break;

      case 'read':
        // Update read_status of the specific message
        if (data.message_id && data.reader_id) {
          const threadKey = data.reader_id; // the friend who read it
          setMessages((prev) => {
            const thread = prev[threadKey] || [];
            return {
              ...prev,
              [threadKey]: thread.map((msg) =>
                msg._id === data.message_id ? { ...msg, read_status: true } : msg
              ),
            };
          });
        }
        break;

      case 'message_sent':
        // Confirmation that message was sent
        console.log('[FriendChatContext] Message sent confirmation:', data.message_id);
        break;

      case 'typing':
        // Update typing indicator based on is_typing status sent from peer
        setTypingIndicators((prev) => ({
          ...prev,
          [sender_id]: data.is_typing !== false,
        }));
        break;

      case 'presence':
        // Online/offline status - handled by useWebSocket
        console.log('[FriendChatContext] Presence update:', data);
        break;

      case 'pong':
        // Heartbeat response - ignore silently
        break;

      case 'friend_request':
      case 'friend_accepted':
      case 'friend_request_cancelled':
        // Handled by FriendSystemContext via lastMessage state
        break;

      default:
        console.warn('[FriendChatContext] Unknown message type:', type);
    }
  }, [userId]);

  const { connectionStatus, onlineUsers, sendMessage, sendChatMessage, sendTypingIndicator, sendReadReceipt } =
    useWebSocket(userId, handleWebSocketMessage, wsOptions);

  // Load user preferences on mount
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        setLoading(true);
        const prefs = await FriendChatService.getPreferences(userId);
        setPreferences(prefs);
      } catch (err) {
        console.error('Failed to load preferences:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    const loadLanguages = async () => {
      try {
        const langs = await FriendChatService.getSupportedLanguages();
        setSupportedLanguages(langs);
      } catch (err) {
        console.error('Failed to load languages:', err);
      }
    };

    loadPreferences();
    loadLanguages();
  }, [userId]);

  // Load chat history when switching active chat
  const loadChatHistory = useCallback(
    async (friendId, page = 1) => {
      try {
        setLoading(true);
        const history = await FriendChatService.getMessageHistory(userId, friendId, page);
        setMessages((prev) => ({
          ...prev,
          [friendId]: FriendChatService.formatMessages([...history.messages].reverse()),
        }));
        return history;
      } catch (err) {
        console.error('Failed to load chat history:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [userId]
  );

  // Send chat message
  const sendChat = useCallback(
    (receiverId, text) => {
      if (!text.trim()) return;

      const success = sendChatMessage(receiverId, text);
      if (success) {
        setActiveChat(receiverId);
      }
      return success;
    },
    [sendChatMessage]
  );

  // Send typing indicator
  const sendTyping = useCallback(
    (receiverId, isTyping = true) => {
      return sendTypingIndicator(receiverId, isTyping);
    },
    [sendTypingIndicator]
  );

  // Update preferences
  const updatePreferences = useCallback(
    async (newPreferences) => {
      try {
        setLoading(true);
        await FriendChatService.updatePreferences(userId, newPreferences);
        setPreferences(newPreferences);
      } catch (err) {
        console.error('Failed to update preferences:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [userId]
  );

  const value = {
    // State
    userId,
    messages,
    activeChat,
    typingIndicators,
    preferences,
    supportedLanguages,
    connectionStatus,
    onlineUsers,
    loading,
    error,
    lastMessage,

    // Actions
    setActiveChat,
    loadChatHistory,
    sendChat,
    sendTyping,
    sendReadReceipt,
    updatePreferences,
  };

  return (
    <FriendChatContext.Provider value={value}>
      {children}
    </FriendChatContext.Provider>
  );
};

export default FriendChatContext;
