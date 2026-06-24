import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useFriendChat } from './FriendChatContext';

const FriendSystemContext = createContext(null);

export const useFriendSystem = () => {
  const context = useContext(FriendSystemContext);
  if (!context) {
    throw new Error('useFriendSystem must be used within a FriendSystemProvider');
  }
  return context;
};

// Base API URL
const API_BASE_URL = 'http://localhost:8000';

export const FriendSystemProvider = ({ children, currentUserId }) => {
  const [friendsList, setFriendsList] = useState([]);
  const [pendingRequests, setPendingRequests] = useState([]);
  const [sentRequests, setSentRequests] = useState([]);
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // We need to listen to socket events from FriendChatContext
  const { lastMessage } = useFriendChat();

  const fetchFriendsList = useCallback(async () => {
    if (!currentUserId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/friends/list?user_id=${currentUserId}`);
      if (response.ok) {
        const data = await response.json();
        setFriendsList(data);
      }
    } catch (err) {
      console.error("Failed to fetch friends list:", err);
    }
  }, [currentUserId]);

  const fetchPendingRequests = useCallback(async () => {
    if (!currentUserId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/friends/requests/pending?user_id=${currentUserId}`);
      if (response.ok) {
        const data = await response.json();
        setPendingRequests(data);
      }
    } catch (err) {
      console.error("Failed to fetch pending requests:", err);
    }
  }, [currentUserId]);

  const fetchSentRequests = useCallback(async () => {
    if (!currentUserId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/friends/requests/sent?user_id=${currentUserId}`);
      if (response.ok) {
        const data = await response.json();
        setSentRequests(data);
      }
    } catch (err) {
      console.error("Failed to fetch sent requests:", err);
    }
  }, [currentUserId]);

  // Initial load
  useEffect(() => {
    if (currentUserId) {
      fetchFriendsList();
      fetchPendingRequests();
      fetchSentRequests();
    }
  }, [currentUserId, fetchFriendsList, fetchPendingRequests, fetchSentRequests]);

  // Handle incoming WebSocket events related to friends
  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === 'friend_request' || lastMessage.type === 'friend_request_cancelled') {
      // Refresh pending requests when a new one arrives or is cancelled
      fetchPendingRequests();
    } else if (lastMessage.type === 'friend_accepted') {
      // Refresh friends list when someone accepts our request
      fetchFriendsList();
      fetchPendingRequests();
      fetchSentRequests();
    }
  }, [lastMessage, fetchFriendsList, fetchPendingRequests, fetchSentRequests]);

  const searchUsers = async (query) => {
    if (!query || query.trim().length === 0) {
      setSearchResults([]);
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/users/search?query=${encodeURIComponent(query)}&user_id=${currentUserId}`
      );
      
      if (!response.ok) throw new Error('Failed to search users');
      
      const data = await response.json();
      setSearchResults(data);
    } catch (err) {
      setError(err.message);
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  };

  const sendFriendRequest = async (receiverId) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/friends/request?user_id=${currentUserId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ receiver_id: receiverId })
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to send request');
      }
      
      // Update local search results state to reflect pending status
      setSearchResults(prev => 
        prev.map(user => 
          user.user_id === receiverId ? { ...user, status: 'pending' } : user
        )
      );
      
      // Refresh sent requests list
      fetchSentRequests();
      
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const respondToRequest = async (requestId, action) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/friends/respond?user_id=${currentUserId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: requestId, action })
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to respond to request');
      }
      
      // Update local state
      setPendingRequests(prev => prev.filter(req => req._id !== requestId));
      
      if (action === 'accept') {
        fetchFriendsList(); // Refresh friends list
      }
      
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const removeFriend = async (friendId) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/friends/remove?user_id=${currentUserId}&friend_id=${friendId}`,
        { method: 'DELETE' }
      );
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to remove friend');
      }
      
      // Update local state
      setFriendsList(prev => prev.filter(f => f.user_id !== friendId));
      
      // Also reset status in search results if they are present
      setSearchResults(prev => 
        prev.map(user => 
          user.user_id === friendId ? { ...user, status: null } : user
        )
      );
      
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const cancelFriendRequest = async (receiverId) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/friends/request/cancel?user_id=${currentUserId}&receiver_id=${receiverId}`,
        { method: 'DELETE' }
      );
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to cancel request');
      }
      
      // Update local state
      setSentRequests(prev => prev.filter(r => r.receiver_id !== receiverId));
      
      // Also update search results if visible
      setSearchResults(prev => 
        prev.map(user => 
          user.user_id === receiverId ? { ...user, status: null } : user
        )
      );
      
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const value = {
    friendsList,
    pendingRequests,
    sentRequests,
    searchResults,
    loading,
    error,
    searchUsers,
    sendFriendRequest,
    cancelFriendRequest,
    respondToRequest,
    removeFriend,
    clearSearchResults: () => setSearchResults([])
  };

  return (
    <FriendSystemContext.Provider value={value}>
      {children}
    </FriendSystemContext.Provider>
  );
};
