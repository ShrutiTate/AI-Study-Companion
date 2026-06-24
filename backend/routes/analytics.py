"""
Analytics Routes - Dashboard API Endpoints

Exposes learning analytics for frontend dashboard display
"""

from fastapi import APIRouter, HTTPException, Query
from backend.services.analytics_engine import analytics_engine
from backend.db.mongo import db
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/dashboard/{session_id}")
async def get_dashboard_metrics(session_id: str):
    """
    Get comprehensive dashboard metrics for a session
    
    This powers the live stats display with:
    - Emotion distribution
    - Learning efficiency
    - Response effectiveness
    - Drop-off points
    - Adaptation recommendations
    """
    try:
        metrics = analytics_engine.get_session_metrics(session_id)
        if not metrics:
            raise HTTPException(status_code=404, detail="Session not found or no data")
        
        return {
            "success": True,
            "metrics": metrics,
            "timestamp": metrics.get("session_id")
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {e}")
        return {"success": False, "error": str(e)}


@router.get("/global")
async def get_global_analytics():
    """
    Get global analytics across all sessions
    
    Shows:
    - Overall emotion distribution
    - Most confusing concepts
    - Teaching mode effectiveness
    - Response effectiveness trends
    """
    try:
        analytics = analytics_engine.get_global_analytics()
        return {
            "success": True,
            "analytics": analytics
        }
    except Exception as e:
        logger.error(f"Error fetching global analytics: {e}")
        return {"success": False, "error": str(e)}


@router.get("/adaptation/{session_id}")
async def get_adaptation_signal(session_id: str):
    """
    Get real-time adaptation signal for active learning
    
    Returns what teaching parameters to adjust based on performance
    Includes messages like "⚡ Adjusting difficulty..."
    """
    try:
        signal = analytics_engine.get_adaptation_signal(session_id)
        return {
            "success": True,
            "adaptation": signal
        }
    except Exception as e:
        logger.error(f"Error getting adaptation signal: {e}")
        return {"success": False, "error": str(e)}


@router.get("/concept/{concept_name}")
async def get_concept_analytics(concept_name: str):
    """
    Get analytics for a specific concept across all sessions
    """
    try:
        sessions = list(db["sessions"].find())
        events = []
        for s in sessions:
            events.extend(s.get("events", []))
            
        concept_events = [e for e in events if e.get("concept") == concept_name and e.get("event_type") == "EVENT_ANSWER_EVALUATED"]
        
        if not concept_events:
            taught = sum(1 for s in sessions if concept_name in s.get("explained_concepts", []))
            if taught == 0:
                raise HTTPException(status_code=404, detail="No analytics for this concept")
            return {
                "success": True,
                "concept": concept_name,
                "total_feedback": 0,
                "helpful": 0,
                "confusing": 0,
                "helpful_percentage": 0,
                "emotion_breakdown": {},
                "difficulty_rating": "unknown"
            }
            
        helpful_count = sum(1 for e in concept_events if e.get("metadata", {}).get("evaluation") == "correct")
        confusing_count = len(concept_events) - helpful_count
        
        emotion_breakdown = {}
        for e in concept_events:
            emotion = e.get("emotion", "unknown")
            is_helpful = e.get("metadata", {}).get("evaluation") == "correct"
            if emotion not in emotion_breakdown:
                emotion_breakdown[emotion] = {"helpful": 0, "confusing": 0}
            if is_helpful:
                emotion_breakdown[emotion]["helpful"] += 1
            else:
                emotion_breakdown[emotion]["confusing"] += 1
                
        difficulty_rating = "easy" if helpful_count / len(concept_events) > 0.8 else "medium" if helpful_count / len(concept_events) > 0.5 else "hard"
        
        return {
            "success": True,
            "concept": concept_name,
            "total_feedback": len(concept_events),
            "helpful": helpful_count,
            "confusing": confusing_count,
            "helpful_percentage": round((helpful_count / len(concept_events)) * 100, 1),
            "emotion_breakdown": emotion_breakdown,
            "difficulty_rating": difficulty_rating
        }
    except Exception as e:
        logger.error(f"Error getting concept analytics: {e}")
        return {"success": False, "error": str(e)}


@router.get("/emotion/{emotion}")
async def get_emotion_analytics(emotion: str):
    """
    Get analytics for responses in a specific emotion state
    """
    try:
        sessions = list(db["sessions"].find())
        events = []
        for s in sessions:
            events.extend(s.get("events", []))
            
        emotion_events = [e for e in events if e.get("emotion") == emotion and e.get("event_type") == "EVENT_ANSWER_EVALUATED"]
        if not emotion_events:
            raise HTTPException(status_code=404, detail="No analytics for this emotion")
            
        helpful_count = sum(1 for e in emotion_events if e.get("metadata", {}).get("evaluation") == "correct")
        
        concept_breakdown = {}
        for e in emotion_events:
            concept = e.get("concept", "unknown")
            is_helpful = e.get("metadata", {}).get("evaluation") == "correct"
            if concept not in concept_breakdown:
                concept_breakdown[concept] = {"helpful": 0, "confusing": 0}
            
            if is_helpful:
                concept_breakdown[concept]["helpful"] += 1
            else:
                concept_breakdown[concept]["confusing"] += 1
        
        return {
            "success": True,
            "emotion": emotion,
            "total_feedback": len(emotion_events),
            "helpful": helpful_count,
            "confusing": len(emotion_events) - helpful_count,
            "effectiveness": round((helpful_count / len(emotion_events)) * 100, 1),
            "concept_breakdown": concept_breakdown
        }
    except Exception as e:
        logger.error(f"Error getting emotion analytics: {e}")
        return {"success": False, "error": str(e)}


@router.get("/trends")
async def get_trends(
    time_window_days: int = Query(7, description="Number of days to look back")
):
    """
    Get learning trends over time
    """
    try:
        from datetime import datetime, timedelta, timezone
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_window_days)
        sessions = list(db["sessions"].find())
        events = []
        for s in sessions:
            for e in s.get("events", []):
                ts = e.get("timestamp")
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    except:
                        ts = None
                if ts and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts and ts >= cutoff_date and e.get("event_type") == "EVENT_ANSWER_EVALUATED":
                    events.append(e)
        
        if not events:
            raise HTTPException(status_code=404, detail="No data for this time period")
        
        daily_trends = {}
        for e in events:
            ts = e.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except:
                    ts = None
            day = ts.date().isoformat() if ts else datetime.now(timezone.utc).date().isoformat()
            
            if day not in daily_trends:
                daily_trends[day] = {"helpful": 0, "confusing": 0, "total": 0}
            
            daily_trends[day]["total"] += 1
            is_helpful = e.get("metadata", {}).get("evaluation") == "correct"
            if is_helpful:
                daily_trends[day]["helpful"] += 1
            else:
                daily_trends[day]["confusing"] += 1
        
        trends = []
        for day in sorted(daily_trends.keys()):
            stats = daily_trends[day]
            effectiveness = (stats["helpful"] / stats["total"] * 100) if stats["total"] > 0 else 0
            trends.append({
                "date": day,
                "helpful": stats["helpful"],
                "confusing": stats["confusing"],
                "effectiveness": round(effectiveness, 1)
            })
        
        return {
            "success": True,
            "time_window_days": time_window_days,
            "trends": trends,
            "overall_trend": "improving" if len(trends) > 1 and trends[-1]["effectiveness"] > trends[0]["effectiveness"] else "stable"
        }
    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        return {"success": False, "error": str(e)}
