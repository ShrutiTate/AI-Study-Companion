# Database Schema

EchoConnect relies on MongoDB Atlas for flexible, document-based persistence. 

## Collections Overview

### 1. `users`
Stores authentication details and profiles.
- `user_id` (String): Unique identifier. Indexed.
- `username` (String)
- `email` (String)
- `password_hash` (String): Hashed via PBKDF2.

### 2. `sessions`
The most complex collection, storing the state machine variables for the AI tutor.
- `session_id` (String): Unique identifier. Indexed.
- `user_id` (String): Foreign key to the user.
- `topic` (String): The master topic (e.g., "Python Basics").
- `current_concept` (String): The sub-topic currently being taught.
- `concept_index` (Integer): Position in the curriculum array.
- `emotion` (String): The current dominant emotion.
- `cognitive_load_score` (Integer): Ranges from 1 (easy) to 5 (overwhelmed).
- `messages` (Array): Embedded sub-documents containing the chat history `[{role: "student", content: "...", timestamp: ...}]`.

### 3. `friend_messages`
Stores the real-time chat data between peers. It is heavily indexed for fast chronological retrieval.
- `sender_id` (String)
- `receiver_id` (String)
- `original_text` (String): The raw message.
- `translated_text` (String): The output from Google Translate.
- `original_lang` (String): Language code (e.g., "en").
- `target_lang` (String): Language code (e.g., "es").
- `timestamp` (Date): Indexed (-1) for quick sorting.
- `read_status` (Boolean): For unread badges.

### 4. `friend_requests`
Manages the peer network graph.
- `sender_id` (String)
- `receiver_id` (String)
- `status` (String): e.g., "pending", "accepted", "rejected".

### 5. `friends_list`
Maps users to their accepted peers.
- `user_id` (String)
- `friends` (Array of Strings): The `user_id`s of accepted peers.

## Offline Mock Layer
In the event MongoDB Atlas goes down or the cluster is paused, `backend/db/mongo.py` intercepts the failure and instantiates a `MockDatabase` class. This class implements in-memory dictionary arrays with methods matching the `pymongo` API (e.g., `find()`, `insert_one()`), allowing the FastAPI endpoints to function without crashing, albeit without persistence.
