/**
 * Friend Chat Window Component - Example Implementation
 * 
 * This is a reference component showing how to use the FriendChatContext
 * to build a complete friend chat interface. Adapt this to match your design.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useFriendChat } from '../contexts';
import { useFriendSystem } from '../contexts/FriendSystemContext';
import '../styles/friend-chat.css'; // Create this file with your styles

const LOCALE_MAP = {
  'en': 'en-US',
  'es': 'es-ES',
  'hi': 'hi-IN',
  'fr': 'fr-FR',
  'de': 'de-DE',
  'zh': 'zh-CN',
  'ja': 'ja-JP',
  'ar': 'ar-SA',
  'pt': 'pt-PT',
  'ru': 'ru-RU',
  'ko': 'ko-KR',
  'it': 'it-IT',
  'nl': 'nl-NL',
  'tr': 'tr-TR',
  'pl': 'pl-PL',
  'bn': 'bn-IN',
  'ta': 'ta-IN',
  'te': 'te-IN',
  'mr': 'mr-IN',
  'gu': 'gu-IN',
  'kn': 'kn-IN',
  'ml': 'ml-IN',
  'pa': 'pa-IN',
  'ur': 'ur-IN',
  'or': 'or-IN',
  'as': 'as-IN',
  'ne': 'ne-NP',
  'sa': 'sa-IN',
  'sd': 'sd-IN',
};

// encapulated Message Bubble component to handle original vs translation toggle
const MessageBubble = ({ msg, userId }) => {
  const [showAlternate, setShowAlternate] = useState(false);
  
  const isMine = msg.sender_id === userId;
  
  // Robust field extraction supporting both camelCase and snake_case schemas
  const original = msg.originalText || msg.original_text || msg.text || '';
  const translated = msg.displayText || msg.translated_text || msg.translatedText || '';
  
  // For received messages: show translation by default (if available), original as alternate
  // For sent messages: show original by default, receiver's translation as alternate
  const primaryText = isMine 
    ? original                           // you always see what you typed
    : (translated || original);          // receiver sees translation, falls back to original
  const alternateText = isMine ? translated : original;
  const currentText = showAlternate ? alternateText : primaryText;
  
  const hasTranslation = msg.hasTranslation || (original && translated && original !== translated);

  const handleSpeak = () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(currentText);
      
      // If we're looking at the original text, speak the source language. If translation, speak target language.
      const isOriginal = isMine ? !showAlternate : showAlternate;
      const lang = isOriginal ? (msg.source_language || 'en') : (msg.target_language || 'en');
      const locale = LOCALE_MAP[lang.toLowerCase()] || lang;
      utterance.lang = locale;
      
      const voices = window.speechSynthesis.getVoices();
      const matchingVoice = voices.find(v => v.lang.toLowerCase().startsWith(lang.toLowerCase()) || v.lang.toLowerCase() === locale.toLowerCase());
      if (matchingVoice) {
        utterance.voice = matchingVoice;
      }
      
      window.speechSynthesis.speak(utterance);
    } else {
      alert("Text-to-speech is not supported in this browser.");
    }
  };

  return (
    <div className={`message ${isMine ? 'sent' : 'received'}`}>
      <div className="message-content">
        {/* Default view: show primary text (translation for received, original for sent). */}
        <p className="message-text">{currentText}</p>

        {/* Inline toggle: when a translation exists and the message is received, allow viewing original on click */}
        {hasTranslation && !isMine && (
          <button
            type="button"
            className="inline-toggle"
            onClick={() => setShowAlternate(!showAlternate)}
            aria-pressed={showAlternate}
            style={{
              marginTop: '8px',
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              padding: 0
            }}
          >
            {showAlternate ? 'Show translation' : 'Show original'}
          </button>
        )}

        {/* Language indicator and actions */}
        <div className="message-meta">
          {msg.sender_id === userId && (
            <span className={`read-status ${msg.read_status ? 'read' : ''}`}>
              {msg.read_status ? '✓✓' : '✓'}
            </span>
          )}
        </div>

        {/* Action buttons */}
        <div className="message-actions">
          {hasTranslation && isMine && (
            <button
              type="button"
              className="translation-toggle-btn"
              onClick={() => setShowAlternate(!showAlternate)}
              title={showAlternate ? "Show original" : "Show translation"}
            >
              {showAlternate ? "📄 Original" : "🌐 Translation"}
            </button>
          )}
          <button
            type="button"
            className="speech-btn"
            onClick={handleSpeak}
            title="Read Aloud"
          >
            🔊 Read
          </button>
        </div>
      </div>
    </div>
  );
};

export const FriendChatWindow = ({ userId, friendId, onClose }) => {
  const {
    messages,
    sendChat,
    sendTyping,
    sendReadReceipt,
    typingIndicators,
    connectionStatus,
    onlineUsers,
    loadChatHistory,
    preferences,
    supportedLanguages,
    updatePreferences,
    loading,
    error,
  } = useFriendChat();

  console.log("messages:", messages);

  const { friendsList } = useFriendSystem();
  
  // Find friend details for display name
  const friend = friendsList?.find(f => f.user_id === friendId);
  const friendName = friend ? friend.name : friendId;

  const [messageInput, setMessageInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showPreferences, setShowPreferences] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState(preferences?.preferred_language || 'en');
  const [autoTranslate, setAutoTranslate] = useState(preferences?.auto_translate !== false);
  const [autoReadAloud, setAutoReadAloud] = useState(preferences?.auto_read_aloud !== false);
  const messagesEndRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const recognitionRef = useRef(null);
  const [isListening, setIsListening] = useState(false);

  const startListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice input requires Chrome or Edge browser.");
      return;
    }

    if (recognitionRef.current) {
      recognitionRef.current.abort();
    }

    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;

    // ✅ Use sender's preferred language
    const senderLang = (preferences?.preferred_language || 'en').toLowerCase();
    const locale = LOCALE_MAP[senderLang] || 'en-US';

    console.log(`🎤 Listening in: ${senderLang} → ${locale}`);

    recognition.lang = locale;
    recognition.continuous = false;
    recognition.interimResults = true;  // ✅ shows text while speaking
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
      setMessageInput('');  // clear input before speaking
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      // ✅ Show text in real-time as user speaks
      setMessageInput(finalTranscript || interimTranscript);
    };

    recognition.onerror = (event) => {
      console.error("Speech error:", event.error);
      setIsListening(false);

      if (event.error === 'network') {
        alert("Network error. Check internet connection.");
      } else if (event.error === 'not-allowed') {
        alert("Microphone permission denied. Allow mic in browser settings.");
      } else if (event.error === 'no-speech') {
        alert("No speech detected. Try again.");
      }
    };

    recognition.onend = () => {
      setIsListening(false);
      // ✅ Text stays in input box — user reviews and clicks Send
    };

    recognition.start();
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }
  };

  const toggleListening = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const chatMessages = messages[friendId] || [];
  const isFriendOnline = onlineUsers.has(friendId);

  // Sync local state with loaded preferences
  useEffect(() => {
    if (preferences) {
      setSelectedLanguage(preferences.preferred_language || 'en');
      setAutoTranslate(preferences.auto_translate !== false);
      setAutoReadAloud(preferences.auto_read_aloud !== false);  // Default to true
    }
  }, [preferences]);

  // Load chat history when window opens or friend changes
  useEffect(() => {
    if (friendId) {
      loadChatHistory(friendId);
    }
  }, [friendId, loadChatHistory]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Send read receipts for unread incoming messages
  useEffect(() => {
    if (!friendId || !sendReadReceipt) return;
    const unreadReceived = chatMessages.filter(
      (m) => m.sender_id !== userId && m.read_status === false
    );
    unreadReceived.forEach((m) => {
      sendReadReceipt(m._id, m.sender_id);
    });
  }, [chatMessages, friendId, userId, sendReadReceipt]);

  // Handle automatic read aloud for incoming messages
  const lastReadMessageIdRef = useRef(null);
  
  useEffect(() => {
    if (chatMessages.length === 0 || !autoReadAloud) return;
    
    const lastMessage = chatMessages[chatMessages.length - 1];
    
    // Only read incoming messages from friend, not your own
    if (lastMessage.sender_id === userId) return;
    
    // Don't re-read same message
    if (lastMessage._id === lastReadMessageIdRef.current) return;
    
    lastReadMessageIdRef.current = lastMessage._id;
    
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      
      // Read the TRANSLATED text (what receiver sees)
      const textToSpeak = lastMessage.displayText || 
                          lastMessage.translated_text || 
                          lastMessage.original_text;
      
      // Use TARGET language for voice (receiver's preferred language)
      const lang = lastMessage.target_language || 
                   preferences?.preferred_language || 'en';
      const locale = LOCALE_MAP[lang.toLowerCase()] || lang;
      
      const utterance = new SpeechSynthesisUtterance(textToSpeak);
      utterance.lang = locale;
      utterance.rate = 0.9;   // Slightly slower = clearer
      utterance.pitch = 1;
      
      // Find best matching voice for this language
      const voices = window.speechSynthesis.getVoices();
      const matchingVoice = voices.find(v => 
        v.lang.toLowerCase().startsWith(lang.toLowerCase())
      );
      if (matchingVoice) {
        utterance.voice = matchingVoice;
      }
      
      window.speechSynthesis.speak(utterance);
    }
  }, [chatMessages, autoReadAloud, userId, preferences]);

  // Handle typing indicator
  const handleInputChange = (e) => {
    setMessageInput(e.target.value);

    if (!isTyping) {
      setIsTyping(true);
      sendTyping(friendId);
    }

    // Clear typing indicator after 2 seconds of no input
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    typingTimeoutRef.current = setTimeout(() => {
      setIsTyping(false);
      sendTyping(friendId, false);
    }, 2000);
  };

  // Handle sending message
  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!messageInput.trim()) return;

    sendChat(friendId, messageInput);
    setMessageInput('');
    setIsTyping(false);
  };

  // Handle preferences update
  const handlePreferencesUpdate = async () => {
    await updatePreferences({
      preferred_language: selectedLanguage,
      auto_translate: autoTranslate,
      auto_read_aloud: autoReadAloud,
    });
    setShowPreferences(false);
  };

  return (
    <div className="friend-chat-window">
      {/* Header */}
      <div className="friend-chat-header">
        <div className="friend-info">
          <h3>{friendName}</h3>
          <span className={`status-indicator ${isFriendOnline ? 'online' : 'offline'}`}>
            {isFriendOnline ? '🟢 Online' : '⚫ Offline'}
          </span>
        </div>

        <div className="header-actions">
          <button
            className="icon-button"
            title="Settings"
            onClick={() => setShowPreferences(!showPreferences)}
          >
            ⚙️
          </button>
          <button className="icon-button" title="Close" onClick={onClose}>
            ✕
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="error-banner">
          <p>⚠️ {error}</p>
        </div>
      )}

      {/* Connection Status */}
      <div className={`connection-status ${connectionStatus}`}>
        <span className="status-dot"></span>
        {connectionStatus === 'connected' && 'Connected'}
        {connectionStatus === 'connecting' && 'Connecting...'}
        {connectionStatus === 'disconnected' && 'Disconnected'}
      </div>

      {/* Preferences Panel */}
      {showPreferences && (
        <div className="preferences-panel">
          <h4>Chat Preferences</h4>

          <div className="preference-group">
            <label>Preferred Language:</label>
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
            >
              {Object.entries(supportedLanguages).map(([code, name]) => (
                <option key={code} value={code}>
                  {name} ({code})
                </option>
              ))}
            </select>
          </div>

          <div className="preference-group">
            <label>
              <input
                type="checkbox"
                checked={autoTranslate}
                onChange={(e) => setAutoTranslate(e.target.checked)}
              />
              Auto-translate incoming messages
            </label>
          </div>

          <div className="preference-group">
            <label>
              <input
                type="checkbox"
                checked={autoReadAloud}
                onChange={(e) => setAutoReadAloud(e.target.checked)}
              />
              Auto-read aloud incoming messages
            </label>
          </div>

          <button className="btn btn-primary" onClick={handlePreferencesUpdate} disabled={loading}>
            {loading ? 'Saving...' : 'Save Preferences'}
          </button>
        </div>
      )}

      {/* Messages Container */}
      <div className="messages-container">
        {chatMessages.length === 0 ? (
          <div className="empty-state">
            <p>No messages yet</p>
            <p className="text-muted">Start a conversation!</p>
          </div>
        ) : (
          <>
            <div className="start-divider">Start of conversation</div>
            {chatMessages.map((msg) => (
              <MessageBubble key={msg._id} msg={msg} userId={userId} />
            ))}
          </>
        )}

        {/* Real-time Typing Indicator */}
        {typingIndicators[friendId] && (
          <div className="message received typing">
            <div className="message-content typing-bubble">
              <span className="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </span>
            </div>
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <form className="message-input-form" onSubmit={handleSendMessage}>
        <input
          type="text"
          className="message-input"
          placeholder={isListening ? "Listening... Speak now..." : `Type a message${isFriendOnline ? '' : ' (offline - will deliver later)'}`}
          value={messageInput}
          onChange={handleInputChange}
          disabled={connectionStatus !== 'connected' && !messageInput}
          maxLength={2000}
        />

        <div className="input-actions">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              type="button"
              className={`btn-mic ${isListening ? 'active' : ''}`}
              onClick={toggleListening}
              title={isListening ? "Stop listening" : "Speak to type"}
            >
              🎤
            </button>
            <span className="char-count">{messageInput.length}/2000</span>
          </div>
          <button
            type="submit"
            className="btn btn-send"
            disabled={!messageInput.trim() || loading}
          >
            {loading ? '⏳' : '➤'}
          </button>
        </div>
      </form>
    </div>
  );
};

/**
 * Online Users List Component
 * Shows who's available for chat
 */
export const OnlineUsersList = ({ currentUserId }) => {
  const { onlineUsers, messages } = useFriendChat();
  const { friendsList } = useFriendSystem();

  const otherUsers = Array.from(onlineUsers).filter((id) => id !== currentUserId);

  const getFriend = (id) => friendsList?.find(f => f.user_id === id) || { name: id };

  return (
    <div className="online-users-list">
      <h4>Online Friends ({otherUsers.length})</h4>

      {otherUsers.length === 0 ? (
        <p className="text-muted">No friends online</p>
      ) : (
        <ul>
          {otherUsers.map((userId) => {
            const friend = getFriend(userId);
            const lastMsgList = messages?.[userId] || [];
            const lastMsg = lastMsgList.length ? lastMsgList[lastMsgList.length - 1] : null;
            const preview = lastMsg ? (lastMsg.displayText || lastMsg.translated_text || lastMsg.original_text || lastMsg.text || '').slice(0, 60) : 'Available';
            const initials = friend.name ? friend.name.split(' ').map(p=>p[0]).slice(0,2).join('').toUpperCase() : userId.slice(0,2).toUpperCase();

            return (
              <li key={userId} className="online-user-item" onClick={() => console.log('Open chat with', userId)}>
                <div className="avatar">{initials}</div>
                <div className="meta">
                  <div className="name">{friend.name}</div>
                  <div className="preview">{preview}</div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  );
};

/**
 * Language Selector Component
 */
export const LanguageSelector = () => {
  const { preferences, supportedLanguages, updatePreferences } = useFriendChat();
  const [selected, setSelected] = useState(preferences?.preferred_language || 'en');
  const [saving, setSaving] = useState(false);

  const handleChange = async (newLang) => {
    setSelected(newLang);
    setSaving(true);
    try {
      await updatePreferences({
        preferred_language: newLang,
        auto_translate: preferences?.auto_translate !== false,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="language-selector">
      <label htmlFor="lang-select">Language:</label>
      <select
        id="lang-select"
        value={selected}
        onChange={(e) => handleChange(e.target.value)}
        disabled={saving}
      >
        {Object.entries(supportedLanguages).map(([code, name]) => (
          <option key={code} value={code}>
            {name}
          </option>
        ))}
      </select>
    </div>
  );
};

export default FriendChatWindow;
