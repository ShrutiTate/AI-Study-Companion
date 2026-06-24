# Module Descriptions

This document breaks down the responsibilities of the core Python backend modules that drive the EchoConnect platform.

## 1. Routing Layer (`backend/routes/`)

### `learning_production.py`
The absolute core of the adaptive tutoring system. It exposes the `/learning/learn` endpoint, which coordinates the procedural engine. It intercepts messages, checks for extreme emotional states ("overwhelm"), and orchestrates the transition between onboarding and active learning phases.

### `session.py`
Manages the lifecycle of a learning topic. It exposes endpoints to start (`/session/start-teaching`), end, and retrieve history. It creates the initial complex JSON state object that tracks mastery, concepts, and cognitive load.

### `friend_chat.py`
Handles peer-to-peer communication API endpoints (getting messages, updating read status). While actual real-time push happens via WebSockets, this route handles the REST persistence.

### `auth.py`
Standard JWT authentication logic, integrating with the MongoDB `users` collection to issue stateless tokens.

---

## 2. Service Layer (`backend/services/`)

### `emotion.py`
Implements the crucial 3-tier hybrid emotion classifier:
1. **Rule-Based**: Checks text against explicit regex patterns for instantaneous matching.
2. **Local AI**: Loads a Hugging Face `DistilRoBERTa` sequence classification model in-memory.
3. **Groq API**: Acts as the ultimate fallback if the local model confidence is low.

### `tutor_control.py`
The "brakes" of the AI. Contains state machine logic and hard-coded response policies. It intercepts LLM outputs and validates them (e.g., ensuring responses don't exceed sentence limits or rely too heavily on analogies).

### `translation_service.py`
Wraps the `googletrans` API in a ThreadPoolExecutor. This allows the synchronous translation requests to be processed asynchronously without blocking the main event loop, ensuring fast message delivery.

### `websocket_manager.py`
Manages the dictionary of active connections mapped to `user_id`s. Responsible for broadcasting localized events like typing indicators and online status.

---

## 3. Database Layer (`backend/db/`)

### `mongo.py`
Initializes the MongoDB Atlas connection. Critically, it implements a `MockDatabase` fallback if the cluster is unreachable, allowing the FastAPI server to continue running and serving routes in memory without crashing.
