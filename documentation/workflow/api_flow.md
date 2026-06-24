# API Flow

EchoConnect utilizes two distinct communication paradigms to serve its frontend: standard asynchronous REST APIs and full-duplex WebSockets.

## 1. REST API (Learning & Auth)

The REST API is used for heavy computational tasks, such as triggering the AI tutoring loop or authenticating users. It follows a stateless request-response model.

**Flow:**
1. **Client**: The React frontend sends a `POST /learning/learn` request containing the text, user ID, and session ID.
2. **Gateway**: FastAPI receives the JSON payload.
3. **Database**: FastAPI queries MongoDB to retrieve the session state.
4. **Inference**: FastAPI makes internal synchronous calls to the local emotion model and external asynchronous HTTPS calls to the Groq LLM.
5. **Response**: FastAPI serializes the updated state and the LLM's text into a JSON response.
6. **Client**: React receives the payload and updates the DOM.

## 2. WebSocket Flow (Peer Chat)

Because peer-to-peer chat requires instant updates without polling, EchoConnect uses a persistent WebSocket connection.

**Flow:**
1. **Handshake**: When a user navigates to `/friend-chat`, React opens a WebSocket connection to `ws://server/friend_chat/ws/{user_id}`.
2. **Connection Manager**: FastAPI's `WebSocketManager` adds the connection to a dictionary of active clients.
3. **Message Dispatch**:
   - User A types a message and sends a JSON payload over the socket.
   - FastAPI receives it, immediately saves `original_text` to MongoDB.
   - FastAPI spins up a background thread using `ThreadPoolExecutor` to call Google Translate.
4. **Broadcast**:
   - Once translation completes, FastAPI looks up User B in the active connections dictionary.
   - If User B is online, FastAPI pushes the `translated_text` directly through their WebSocket.
5. **Presence Events**: Typing indicators (`{"type": "typing"}`) are broadcasted instantly without database persistence.
