# Echo Connect: An Intelligent Educational & Multilingual Collaboration Platform

Welcome to the Echo Connect source code repository. This project was developed as a comprehensive, dual-system platform designed to solve two major challenges in modern digital education: static, non-adaptive learning curves, and global language barriers between students.

##  Project Overview

Echo Connect is divided into two primary subsystems:

1. **The Adaptive AI Tutoring Engine:** 
   An intelligent agent that evaluates a student's prior knowledge, dynamically generates a customized curriculum, and tracks their mastery mathematically. It utilizes a **Hybrid Emotion Classifier** (Rules + DistilRoBERTa + Llama 3.1) to detect frustration and confusion. If a student struggles, the AI enters a "Recovery State," altering its pedagogical tone to prevent cognitive overload.
   
2. **The Multilingual Friend Chat:**
   A real-time WebSocket communication system. Students can chat peer-to-peer in their native languages (e.g., English, Spanish, Hindi, Japanese). The backend intercepts messages, performs asynchronous translation via the Google Translate API, and pushes the translated text instantly to the receiver.

##  Technology Stack

- **Frontend:** React.js (Vite), CSS Modules
- **Backend:** Python, FastAPI, WebSockets
- **Database:** MongoDB Atlas (with a custom Offline Mock Database failover)
- **AI / ML:** Groq API (Llama 3.1) for fast inference, HuggingFace (DistilRoBERTa) for sentiment analysis
- **External APIs:** Google Translate API

##  Project Structure

- `/frontend/` - React SPA containing the UI components and Context providers.
- `/backend/` - FastAPI server, WebSocket manager, AI state machines, and routing.
- `/documentation/` - Deep architectural diagrams, flowcharts, and schema descriptions.
- `/tests/` - Pytest suites verifying the AI state machine logic.

##  Essential Documentation

For examiners and evaluators reviewing this CD, please refer to the following documents:

1. **[INSTALLATION_GUIDE.md](./INSTALLATION_GUIDE.md)**: Step-by-step instructions on how to install dependencies and run the application locally.
2. **[PROJECT_SYNOPSIS.md](./PROJECT_SYNOPSIS.md)**: A high-level abstract and summary of the project's features and engineering highlights.
3. **[REPORT_EVIDENCE.md](./REPORT_EVIDENCE.md)**: A ledger pointing to exact lines of code proving the implementation of advanced features.

---

"# AI-Study-Companion" 
