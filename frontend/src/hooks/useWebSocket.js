import { useEffect, useRef, useCallback, useState } from 'react';

/**
 * useWebSocket - React hook for managing WebSocket connections to friend chat
 * 
 * Features:
 * - Automatic reconnection on disconnect
 * - Message queueing while disconnected
 * - Event callbacks for different message types
 * - Typing indicators
 * - Online/offline status tracking
 */
export const useWebSocket = (userId, onMessage, options = {}) => {
  const {
    url = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//localhost:8000/friend-chat/ws/${userId}`,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // disconnected, connecting, connected
  const [onlineUsers, setOnlineUsers] = useState(new Set());
  const wsRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const messageQueueRef = useRef([]);
  const reconnectTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    console.log(`[WebSocket] Connecting to ${url}`);
    setConnectionStatus('connecting');

    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        console.log('[WebSocket] Connected');
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;

        // Flush message queue
        if (messageQueueRef.current.length > 0) {
          console.log(`[WebSocket] Flushing ${messageQueueRef.current.length} queued messages`);
          messageQueueRef.current.forEach((msg) => {
            wsRef.current?.send(JSON.stringify(msg));
          });
          messageQueueRef.current = [];
        }

        // Start heartbeat to detect stale connections
        startHeartbeat();
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[WebSocket] Received:', data.type, data);

          // Update online status if presence event
          if (data.type === 'presence_list') {
            setOnlineUsers(new Set(data.users));
          } else if (data.type === 'presence') {
            if (data.status === 'online') {
              setOnlineUsers((prev) => new Set([...prev, data.user_id]));
            } else {
              setOnlineUsers((prev) => {
                const updated = new Set(prev);
                updated.delete(data.user_id);
                return updated;
              });
            }
          }

          // Call user callback
          if (onMessage) {
            onMessage(data);
          }
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setConnectionStatus('disconnected');
      };

      wsRef.current.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setConnectionStatus('disconnected');
        stopHeartbeat();

        // Attempt reconnection
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          console.log(
            `[WebSocket] Reconnecting (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts}) in ${reconnectInterval}ms`
          );
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        } else {
          console.error('[WebSocket] Max reconnection attempts reached');
        }
      };
    } catch (err) {
      console.error('[WebSocket] Connection failed:', err);
      setConnectionStatus('disconnected');
    }
  }, [url, reconnectInterval, maxReconnectAttempts, onMessage]);

  // Disconnect and cleanup
  const disconnect = useCallback(() => {
    console.log('[WebSocket] Disconnecting');
    stopHeartbeat();
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnectionStatus('disconnected');
  }, []);

  // Send message
  const sendMessage = useCallback(
    (message) => {
      if (!message || typeof message !== 'object') {
        console.error('[WebSocket] Invalid message:', message);
        return false;
      }

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify(message));
          console.log('[WebSocket] Sent:', message.type, message);
          return true;
        } catch (err) {
          console.error('[WebSocket] Failed to send message:', err);
          return false;
        }
      } else {
        console.warn('[WebSocket] Connection not open, queueing message');
        messageQueueRef.current.push(message);
        return false;
      }
    },
    []
  );

  // Send chat message
  const sendChatMessage = useCallback(
    (receiverId, text) => {
      return sendMessage({
        type: 'message',
        receiver_id: receiverId,
        text,
      });
    },
    [sendMessage]
  );

  // Send typing indicator
  const sendTypingIndicator = useCallback(
    (receiverId, isTyping = true) => {
      return sendMessage({
        type: 'typing',
        receiver_id: receiverId,
        is_typing: isTyping,
      });
    },
    [sendMessage]
  );

  // Send read receipt
  const sendReadReceipt = useCallback(
    (messageId, senderId) => {
      return sendMessage({
        type: 'read',
        message_id: messageId,
        sender_id: senderId,
      });
    },
    [sendMessage]
  );

  // Heartbeat to detect stale connections
  const startHeartbeat = useCallback(() => {
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Every 30 seconds
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  // Initialize connection on mount, cleanup on unmount
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connectionStatus,
    onlineUsers,
    sendMessage,
    sendChatMessage,
    sendTypingIndicator,
    sendReadReceipt,
    disconnect,
    reconnect: () => {
      reconnectAttemptsRef.current = 0;
      connect();
    },
  };
};

export default useWebSocket;
