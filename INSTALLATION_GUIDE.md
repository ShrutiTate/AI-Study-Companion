# Installation & Execution Guide

This guide provides step-by-step instructions on how to run the Echo Connect platform from this submission CD. 

## Prerequisites
Before starting, ensure the target machine has the following installed:
- **Node.js** (v16 or higher)
- **Python** (v3.9 or higher)
- **Git Bash / Terminal / PowerShell**

---

## Step 1: Environment Setup

A `.env.example` file is included in the root directory. To run the application, you must rename it to `.env` and provide your API keys.

1. Navigate to the project root.
2. Rename `.env.example` to `.env`.
3. Open `.env` and fill in:
   - `GROQ_API_KEY` (Required for the AI Tutor)
   - `MONGO_URL` (Required for database persistence)

*Note: If the MongoDB connection fails (e.g., due to university firewall blocks), the backend will automatically fallback to an Offline Mock Database to keep the application running.*

---

## Step 2: Running the Backend (FastAPI)

Open a new terminal window and run the following commands:

1. **Navigate to the project root:**
   ```bash
   cd echo_connect
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the FastAPI Server:**
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
   *The backend should now be running at `http://localhost:8000`. You will see a startup log confirming the Database Status (Connected or Offline).*

---

## Step 3: Running the Frontend (React)

Open a **second** terminal window and run the following commands:

1. **Navigate to the frontend directory:**
   ```bash
   cd echo_connect/frontend
   ```

2. **Install Node modules:**
   ```bash
   npm install
   ```

3. **Start the Vite Development Server:**
   ```bash
   npm run dev
   ```
   *The frontend should now be running at `http://localhost:5173`.*

---

## Step 4: Testing the Application

1. Open a browser and go to `http://localhost:5173`.
2. Register a new user account (or use mock credentials if the database is in offline mode).
3. **To test the AI Tutor:** Navigate to the "Learning" tab, select a topic, and interact with the AI. Express confusion multiple times to trigger the "Recovery Mode".
4. **To test the Multilingual Chat:** Open the application in two different browsers (or an incognito window), log into two different accounts, and send messages to each other from the "Friend Chat" tab.
