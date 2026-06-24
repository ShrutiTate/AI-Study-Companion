# End-to-End System Workflow

This narrative maps the complete user journey through the EchoConnect platform, showing how the frontend, backend, and external APIs collaborate.

## Phase 1: Authentication & Setup
1. The user visits the React SPA. They are unauthenticated, so React Router redirects them to the Login page.
2. The user submits their credentials. The FastAPI backend hashes the password, verifies it against MongoDB, and returns a JWT and user profile data.
3. React saves this data in `localStorage`. The global contexts (`FriendSystemContext`, `FriendChatContext`) immediately mount, opening a background WebSocket connection to listen for friend requests.

## Phase 2: Starting a Session
1. The user navigates to the Learning Dashboard and types a topic (e.g., "Photosynthesis").
2. React calls `POST /session/start-teaching`.
3. The backend queries the Groq API to generate a list of sub-concepts (e.g., ["Chloroplasts", "Light Reactions", "Calvin Cycle"]).
4. The backend initializes a new Session document in MongoDB, setting `concept_index = 0` and `emotion = neutral`.
5. The backend returns the first lesson and the React UI renders the Virtual Classroom.

## Phase 3: The Adaptive Learning Loop
1. The user reads the first lesson and replies, "I'm totally lost, this is too hard."
2. React sends `POST /learning/learn`.
3. The backend's **Hybrid Emotion Pipeline** intercepts the text. The rule-based engine catches "too hard" and immediately classifies the emotion as `frustrated`.
4. The backend updates the session's `cognitive_load_score` to a higher level.
5. The **Procedural Tutoring Engine** constructs a prompt for Groq: "The student is frustrated. You must simplify the concept and provide an analogy."
6. Groq generates the response. The backend validates it and saves the new state.
7. React receives the JSON. The UI updates the chatbot text and changes the interface accent color to red/orange to reflect the frustration detected.

## Phase 4: Peer Translation Chat
1. After the session, the user goes to the Friends tab.
2. They select a peer who speaks Spanish (while the user speaks English).
3. The user types "How was your session?" over the WebSocket.
4. The backend intercepts the socket payload, triggers Google Translate asynchronously, and saves both the English and Spanish strings to MongoDB.
5. The backend pushes the Spanish string (`"¿Cómo estuvo tu sesión?"`) via WebSocket to the peer, who sees it instantly.
