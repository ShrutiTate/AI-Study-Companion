# AI Model Workflow

This document explains the workflows for the Artificial Intelligence layers powering EchoConnect. EchoConnect uses a hybrid approach, separating the fast, deterministic emotion classification from the slower, generative text responses.

## 1. Hybrid Emotion Classification Pipeline

Emotion detection occurs on *every* message sent by the student. Because API calls introduce latency, EchoConnect uses a waterfall approach:

### Tier 1: Local Rule-Based Regex (Zero Latency)
- **Logic**: The system checks the raw string against a predefined list of pedagogical keywords.
- **Triggers**: Words like "confused", "stuck", "I give up", "this is impossible", or sarcastic indicators ("yeah right").
- **Action**: If a match is found, the system instantly returns `confused` or `frustrated` without touching any models.

### Tier 2: Local Transformer (`DistilRoBERTa`)
- **Logic**: If no rules match, the text is passed to a locally loaded Hugging Face pipeline (`j-hartmann/emotion-english-distilroberta-base`).
- **Action**: The model outputs an array of emotions and confidence scores. The highest-scoring emotion is mapped to EchoConnect's internal states:
  - `joy/surprise` -> `engaged`
  - `anger` -> `frustrated`
  - `sadness/fear/disgust` -> `confused`
  - `neutral` -> `neutral`
- **Validation**: If the confidence score is $\le 0.60$, the system distrusts the local model and triggers Tier 3.

### Tier 3: LLM Fallback (Groq Llama-3.1)
- **Logic**: For ambiguous messages, the text is sent to Groq with a strict system prompt demanding a single-word emotional classification.
- **Action**: The LLM parses the nuance and returns the final emotion.

---

## 2. Procedural Tutoring Engine (Llama 3.1 8B)

The generative response generation utilizes the Groq API. EchoConnect does *not* use a conversational chain with memory arrays; instead, it uses a **state-machine driven flat prompt**.

### The Orchestration Loop
1. **Detect Intent**: Before generating a lesson, the system checks the student's *intent* (e.g., are they answering the question, asking for help, or making a random comment?).
2. **Context Assembly**: The `generate_lesson()` function fetches:
   - The `current_concept`
   - The detected `emotion`
   - The `cognitive_load_score` (1-5)
   - The `attempt_count`
3. **Prompt Injection**: These variables are injected into a highly structured system prompt. For example, if `emotion == "frustrated"`, the system prompt strictly forces the LLM to write shorter sentences and provide easier examples.
4. **Validation Check**: The output from Groq is verified by `TutorControl`. If the LLM generates a response that is too long or violates a rule, `TutorControl` blocks it and forces Groq to rewrite it immediately (Swift Regeneration).
