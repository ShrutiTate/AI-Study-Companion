from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import production learning router (clean tutoring loop)
from backend.routes.learning_production import router as learning_router
from backend.routes.chat import router as chat_router
from backend.routes.auth import router as auth_router
from backend.routes.session import router as session_router
from backend.routes.feedback import router as feedback_router
from backend.routes.analytics import router as analytics_router
from backend.routes.quiz import router as quiz_router
from backend.routes.friend_chat import router as friend_chat_router
from backend.routes.preferences import router as preferences_router
from backend.routes.friends import router as friends_router

# Import emotion detection from services
from backend.services.emotion import detect_emotion

# Initialize database
print("[APP] Initializing EchoConnect backend...")
from backend.db.mongo import get_status, get_db

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="EchoConnect API",
    description="Educational learning assistance platform with emotion detection and translation",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - FIXED with explicit configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:5000", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
    expose_headers=["*"],
)

# Include routers
app.include_router(learning_router, prefix="/learning", tags=["learning"])      
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(session_router, prefix="/session", tags=["session", "chat"])
app.include_router(feedback_router, prefix="/feedback", tags=["feedback"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
app.include_router(quiz_router, prefix="/quiz", tags=["quiz"])
app.include_router(friend_chat_router)
app.include_router(preferences_router)
app.include_router(friends_router)

# Pre-load emotion detection model on startup to eliminate cold-start penalty
# Now uses lazy loading - model loads on first request, not at startup
# This prevents startup from hanging while waiting for model download/init
@app.on_event("startup")
def startup_event():
    """Server startup event"""
    print("[STARTUP] ✅ EchoConnect backend initialized")

# Root endpoint
@app.get("/")
def root():
    return {
        "message": "EchoConnect API running",
        "status": "healthy",
        "database": get_status(),
        "docs": "http://localhost:8000/docs",
        "features": {
            "learning": "POST /learning/learn - Emotion detection with RAG pipeline",
            "upload_content": "POST /learning/upload-content - Upload study material for topics",
            "analysis": "POST /learning/analyze - Detailed emotion analysis",
            "learning_history": "GET /learning/history/{user_id} - User's learning history",
            "translation": "POST /chat/translate - Multilingual translation",   
            "chat_history": "GET /chat/history/{user_id} - User's chat history",
            "session": "POST /session/start - Start learning session, POST /session/end - End session"
        }
    }

# ================================
# NEW: Adaptive Analysis Endpoint
# ================================

class UserInput(BaseModel):
    text: str
    topic: str


@app.post("/analyze")
def analyze(input: UserInput):
    """
    Analyze user input for emotion detection.

    Returns: emotion and status
    """
    try:
        emotion = detect_emotion(input.text)

        return {
            "emotion": emotion,
            "success": True
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "emotion": "neutral"
        }

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "EchoConnect API",
        "database": get_status()
    }

if __name__ == "__main__":
    import uvicorn
    print(f"[APP] Starting EchoConnect API (Database: {get_status()})")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
