"""
Quiz API Routes

Endpoints for quiz generation and tracking
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from backend.services.quiz_engine import QuizEngine

router = APIRouter()

class QuizGenerateRequest(BaseModel):
    session_id: str
    num_questions: Optional[int] = 9

class QuizSubmitRequest(BaseModel):
    session_id: str
    quiz_id: str
    answers: List[dict]  # [{"question_index": int, "selected": str}]

@router.post("/generate")
async def generate_quiz(request: QuizGenerateRequest):
    """Generate an adaptive quiz for a session"""
    try:
        result = QuizEngine.generate_quiz(
            session_id=request.session_id,
            num_questions=request.num_questions
        )
        
        return {
            "success": result.get("success"),
            "data": result if result.get("success") else None,
            "error": result.get("error") if not result.get("success") else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
async def get_quiz_for_session(session_id: str):
    """Generate or retrieve quiz for a session"""
    try:
        result = QuizEngine.generate_quiz(session_id)
        return {
            "success": result.get("success"),
            "quiz": result if result.get("success") else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
