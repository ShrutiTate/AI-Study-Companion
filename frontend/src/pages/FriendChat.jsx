import React, { useState, useEffect } from 'react';
import { FriendChatProvider, useFriendChat } from '../contexts/FriendChatContext';
import FriendChatWindow from '../components/FriendChatWindow';
import FriendSidebar from '../components/FriendSidebar';
import FriendChatService from '../services/friendChatService';
import { FriendSystemProvider } from '../contexts/FriendSystemContext';
import '../styles/friend-chat.css';

// Internal view wrapper that utilizes the useFriendChat hook within the provider
function FriendChatView() {
  const currentUserId = localStorage.getItem('user_id');
  const currentUserName = localStorage.getItem('name');
  
  const {
    messages,
    activeChat,
    setActiveChat,
    typingIndicators,
    connectionStatus,
    onlineUsers,
    supportedLanguages,
    preferences,
    updatePreferences,
  } = useFriendChat();

  return (
    <div className="friend-chat-page-container">
      {/* Sidebar - Friends List */}
      <div className="friend-chat-sidebar">
        <FriendSidebar onChatSelect={setActiveChat} />
      </div>

      {/* Main Chat Area */}
      <div className="friend-chat-main-area">
        {activeChat ? (
          <FriendChatWindow 
            userId={currentUserId}
            friendId={activeChat}
            onClose={() => setActiveChat(null)}
          />
        ) : (
          <div className="chat-welcome-placeholder">
            <div className="placeholder-icon">💬</div>
            <h2>EchoConnect Multilingual Friend Chat</h2>
            <p>Select a friend from the sidebar to start a real-time, auto-translated conversation.</p>
            <div className="multilingual-badge-row">
              <span className="badge">English</span>
              <span className="badge">Español</span>
              <span className="badge">日本語</span>
              <span className="badge">Français</span>
              <span className="badge">हिन्दी</span>
              <span className="badge">தமிழ்</span>
              <span className="badge">বাংলা</span>
              <span className="badge">తెలుగు</span>
              <span className="badge">मराठी</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Exported page wrapper that mounts the Context Provider dynamically
export default function FriendChatPage() {
  const userId = localStorage.getItem('user_id');

  if (!userId) {
    return (
      <div className="friend-chat-auth-warning">
        <h3>Please log in to access Friend Chat.</h3>
      </div>
    );
  }

  return (
    <FriendChatView />
  );
}
