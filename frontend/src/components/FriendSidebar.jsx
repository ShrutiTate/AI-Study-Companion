import React, { useState } from 'react';
import { useFriendSystem } from '../contexts/FriendSystemContext';
import { useFriendChat } from '../contexts/FriendChatContext';

export const FriendSidebar = ({ onChatSelect }) => {
  const {
    friendsList,
    pendingRequests,
    sentRequests,
    searchResults,
    searchUsers,
    sendFriendRequest,
    cancelFriendRequest,
    respondToRequest,
    removeFriend,
    clearSearchResults,
    loading
  } = useFriendSystem();

  const { onlineUsers } = useFriendChat();
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e) => {
    e.preventDefault();
    searchUsers(searchQuery);
  };

  const handleClearSearch = () => {
    setSearchQuery('');
    clearSearchResults();
  };

  return (
    <div className="friend-sidebar">
      {/* Search Section */}
      <div className="sidebar-section">
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            placeholder="🔍 Search users..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
          />
          {searchQuery && (
            <button type="button" onClick={handleClearSearch} className="clear-search-btn">✕</button>
          )}
        </form>

        {searchResults.length > 0 && (
          <div className="search-results">
            <h4>Search Results</h4>
            <ul>
              {searchResults.map(user => (
                <li key={user.user_id} className="search-result-item">
                  <div className="user-info">
                    <span className="user-name">{user.name || user.user_id}</span>
                    {user.email && <span className="user-email">{user.email}</span>}
                  </div>
                  <div className="user-actions">
                    {user.status === 'friends' ? (
                      <span className="status-badge">Friends ✓</span>
                    ) : user.status === 'pending' ? (
                      <button 
                        onClick={() => cancelFriendRequest(user.user_id)}
                        disabled={loading}
                        className="btn-cancel"
                      >
                        Cancel ✕
                      </button>
                    ) : (
                      <button 
                        onClick={() => sendFriendRequest(user.user_id)}
                        disabled={loading}
                        className="btn-add-friend"
                      >
                        Add +
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Incoming Notifications Section */}
      {pendingRequests.length > 0 && (
        <div className="sidebar-section notifications-section">
          <h4>🔔 Notifications ({pendingRequests.length})</h4>
          <ul>
            {pendingRequests.map(req => (
              <li key={req._id} className="notification-item">
                <div className="notification-text">
                  <strong>{req.sender_name}</strong> sent you a friend request
                </div>
                <div className="notification-actions">
                  <button 
                    onClick={() => respondToRequest(req._id, 'accept')}
                    disabled={loading}
                    className="btn-accept"
                  >
                    Accept ✅
                  </button>
                  <button 
                    onClick={() => respondToRequest(req._id, 'reject')}
                    disabled={loading}
                    className="btn-reject"
                  >
                    Reject ❌
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sent Requests Section */}
      {sentRequests.length > 0 && (
        <div className="sidebar-section sent-requests-section">
          <h4>📤 Sent Requests ({sentRequests.length})</h4>
          <ul>
            {sentRequests.map(req => (
              <li key={req._id} className="notification-item">
                <div className="notification-text">
                  Sent to <strong>{req.receiver_name}</strong>
                </div>
                <div className="notification-actions">
                  <button 
                    onClick={() => cancelFriendRequest(req.receiver_id)}
                    disabled={loading}
                    className="btn-cancel"
                  >
                    Cancel ✕
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Friends List Section */}
      <div className="sidebar-section friends-list-section">
        <h4>👥 My Friends ({friendsList.length})</h4>
        {friendsList.length === 0 ? (
          <p className="empty-state">No friends yet. Search above to add some!</p>
        ) : (
          <ul>
            {friendsList.map(friend => {
              const isOnline = onlineUsers.has(friend.user_id);
              return (
                <li key={friend.user_id} className="friend-item">
                  <div className="friend-info">
                    <span className={`status-dot ${isOnline ? 'online' : 'offline'}`}></span>
                    <span className="friend-name">{friend.name || friend.user_id}</span>
                  </div>
                  <div className="friend-actions">
                    <button 
                      onClick={() => onChatSelect(friend.user_id)}
                      className="btn-chat"
                    >
                      Chat 💬
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};

export default FriendSidebar;
