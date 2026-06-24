"""
Event Tracking Service - Foundation for Clean Analytics

Instead of counting messages, track EVENTS.
Real analytics systems use event logs, not message counts.

Events:
- EVENT_SESSION_STARTED
- EVENT_CONCEPT_PRESENTED
- EVENT_EXAMPLE_REQUESTED
- EVENT_EXAMPLE_PROVIDED
- EVENT_STUDENT_ANSWERED
- EVENT_ANSWER_EVALUATED (correct|partial|incorrect)
- EVENT_CONCEPT_MASTERED
- EVENT_CONFUSION_SPIKE
- EVENT_ASKED_FOR_SIMPLIFICATION
- EVENT_STUDENT_REFUSAL
- EVENT_SESSION_COMPLETED
- EVENT_SHORT_ACK (low-value message - DO NOT count toward metrics)

Event Format:
{
    "event_type": "EVENT_ANSWER_EVALUATED",
    "session_id": "...",
    "user_id": "...",
    "timestamp": datetime,
    "concept": "...",
    "evaluation": "correct|partial|incorrect",
    "emotion": "...",
    "cognitive_load": 0-5,
    "metadata": {...}
}
"""

from datetime import datetime, timezone
from backend.db.mongo import db
from typing import Dict, Any, Optional


class EventTracker:
    """
    Track meaningful learning events instead of raw message counts.
    All analytics should be rebuilt from this event log.
    """
    
    @staticmethod
    def track_event(
        event_type: str,
        session_id: str,
        user_id: str,
        concept: Optional[str] = None,
        emotion: Optional[str] = None,
        cognitive_load: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log a learning event.
        
        Args:
            event_type: One of EVENT_* constants
            session_id: Session identifier
            user_id: User identifier
            concept: Current concept being learned
            emotion: Student's current emotion
            cognitive_load: Current cognitive load (0-5)
            metadata: Additional context-specific data
        
        Returns:
            The created event document
        """
        
        event = {
            "event_type": event_type,
            "session_id": session_id,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "concept": concept,
            "emotion": emotion,
            "cognitive_load": cognitive_load,
            "metadata": metadata or {}
        }
        
        try:
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$push": {"events": event}}
            )
            print(f"[EVENT] {event_type} logged for session {session_id} at concept {concept}")
            return event
        except Exception as e:
            print(f"[EVENT] Failed to log {event_type}: {e}")
            return event
    
    @staticmethod
    def track_session_started(session_id: str, user_id: str, topic: str = None):
        """Session initialized"""
        return EventTracker.track_event(
            "EVENT_SESSION_STARTED",
            session_id,
            user_id,
            metadata={"topic": topic}
        )
    
    @staticmethod
    def track_concept_presented(session_id: str, user_id: str, concept: str, depth: str = "intro"):
        """Tutor introduced a new concept"""
        return EventTracker.track_event(
            "EVENT_CONCEPT_PRESENTED",
            session_id,
            user_id,
            concept=concept,
            metadata={"depth_level": depth}
        )
    
    @staticmethod
    def track_example_requested(session_id: str, user_id: str, concept: str, emotion: str = None):
        """Student asked for example - meaningful intent signal"""
        return EventTracker.track_event(
            "EVENT_EXAMPLE_REQUESTED",
            session_id,
            user_id,
            concept=concept,
            emotion=emotion,
            metadata={"intent": "ask_example"}
        )
    
    @staticmethod
    def track_example_provided(session_id: str, user_id: str, concept: str, example_type: str = None):
        """Tutor provided example"""
        return EventTracker.track_event(
            "EVENT_EXAMPLE_PROVIDED",
            session_id,
            user_id,
            concept=concept,
            metadata={"example_type": example_type}
        )
    
    @staticmethod
    def track_student_answered(
        session_id: str,
        user_id: str,
        concept: str,
        answer_length: int = 0,
        emotion: str = None
    ):
        """Student attempted to answer question"""
        return EventTracker.track_event(
            "EVENT_STUDENT_ANSWERED",
            session_id,
            user_id,
            concept=concept,
            emotion=emotion,
            metadata={"answer_length": answer_length}
        )
    
    @staticmethod
    def track_answer_evaluated(
        session_id: str,
        user_id: str,
        concept: str,
        evaluation: str,  # correct|partial|incorrect
        emotion: str = None,
        cognitive_load: int = None,
        attempt_count: int = None
    ):
        """Answer was evaluated - this is a REAL learning event"""
        return EventTracker.track_event(
            "EVENT_ANSWER_EVALUATED",
            session_id,
            user_id,
            concept=concept,
            emotion=emotion,
            cognitive_load=cognitive_load,
            metadata={
                "evaluation": evaluation,
                "attempt_count": attempt_count
            }
        )
    
    @staticmethod
    def track_concept_mastered(session_id: str, user_id: str, concept: str, emotion: str = None):
        """Student mastered a concept - strong signal"""
        return EventTracker.track_event(
            "EVENT_CONCEPT_MASTERED",
            session_id,
            user_id,
            concept=concept,
            emotion=emotion
        )
    
    @staticmethod
    def track_confusion_spike(session_id: str, user_id: str, concept: str, emotion: str = "confused"):
        """Student became confused - important for adaptive teaching"""
        return EventTracker.track_event(
            "EVENT_CONFUSION_SPIKE",
            session_id,
            user_id,
            concept=concept,
            emotion=emotion,
            metadata={"requires_simplification": True}
        )
    
    @staticmethod
    def track_simplification_requested(session_id: str, user_id: str, concept: str, emotion: str = None):
        """Student asked to simplify - meaningful signal"""
        return EventTracker.track_event(
            "EVENT_ASKED_FOR_SIMPLIFICATION",
            session_id,
            user_id,
            concept=concept,
            emotion=emotion,
            metadata={"intent": "ask_simplify"}
        )
    
    @staticmethod
    def track_student_refusal(session_id: str, user_id: str, concept: str, emotion: str = None):
        """Student wants to stop learning - session boundary"""
        return EventTracker.track_event(
            "EVENT_STUDENT_REFUSAL",
            session_id,
            user_id,
            concept=concept,
            emotion=emotion
        )
    
    @staticmethod
    def track_session_completed(session_id: str, user_id: str, concepts_learned: int = 0, duration_minutes: float = 0):
        """Session ended normally - summary event"""
        return EventTracker.track_event(
            "EVENT_SESSION_COMPLETED",
            session_id,
            user_id,
            metadata={
                "concepts_learned": concepts_learned,
                "duration_minutes": duration_minutes
            }
        )
    
    @staticmethod
    def track_low_value_message(session_id: str, user_id: str, message: str, emotion: str = None):
        """LOW-VALUE MESSAGE - DO NOT COUNT TOWARD ANALYTICS"""
        return EventTracker.track_event(
            "EVENT_SHORT_ACK",
            session_id,
            user_id,
            emotion=emotion,
            metadata={
                "message": message,
                "note": "This is conversation noise, not learning"
            }
        )


# ============================================
# ANALYTICS QUERIES (Built from Events)
# ============================================

class EventAnalytics:
    """
    Rebuild analytics properly from event log.
    These queries ensure metrics are meaningful, not fake.
    """
    
    @staticmethod
    def get_session_metrics(session_id: str) -> Dict[str, Any]:
        """
        Build clean session metrics from events.
        Do NOT count SHORT_ACK events.
        """
        session = db["sessions"].find_one({"session_id": session_id})
        events = session.get("events", []) if session else []
        
        # Filter out low-value messages
        meaningful_events = [e for e in events if e["event_type"] != "EVENT_SHORT_ACK"]
        
        metrics = {
            "session_id": session_id,
            "total_meaningful_events": len(meaningful_events),
            "concepts_presented": len(set(e["concept"] for e in meaningful_events if e.get("concept"))),
            "answers_attempted": len([e for e in meaningful_events if e["event_type"] == "EVENT_STUDENT_ANSWERED"]),
            "answers_correct": len([e for e in meaningful_events 
                                   if e["event_type"] == "EVENT_ANSWER_EVALUATED" 
                                   and e.get("metadata", {}).get("evaluation") == "correct"]),
            "concepts_mastered": len([e for e in meaningful_events if e["event_type"] == "EVENT_CONCEPT_MASTERED"]),
            "confusion_spikes": len([e for e in meaningful_events if e["event_type"] == "EVENT_CONFUSION_SPIKE"]),
            "examples_requested": len([e for e in meaningful_events if e["event_type"] == "EVENT_EXAMPLE_REQUESTED"]),
            "low_value_messages": len([e for e in events if e["event_type"] == "EVENT_SHORT_ACK"])
        }
        
        return metrics
    
    @staticmethod
    def get_engagement_score(session_id: str) -> float:
        """
        Calculate engagement from MEANINGFUL events only.
        Formula: (concepts_mastered * 0.5) + (examples_requested * 0.3) + (answers_correct * 0.2)
        """
        metrics = EventAnalytics.get_session_metrics(session_id)
        
        engagement = (
            metrics["concepts_mastered"] * 0.5 +
            metrics["examples_requested"] * 0.3 +
            metrics["answers_correct"] * 0.2
        )
        
        # Cap at 100
        return min(engagement, 100.0)
    
    @staticmethod
    def get_study_time_minutes(session_id: str) -> float:
        """
        Calculate ACTIVE study time from meaningful events.
        Do NOT include long idle gaps between user interactions.
        """
        session = db["sessions"].find_one({"session_id": session_id})
        events = session.get("events", []) if session else []
        meaningful_events = sorted(
            [e for e in events if e.get("event_type") != "EVENT_SHORT_ACK"],
            key=lambda event: event["timestamp"]
        )

        if len(meaningful_events) < 2:
            return 0.0

        total_seconds = 0.0
        inactivity_timeout = 300.0  # 5 minutes

        for previous, current in zip(meaningful_events, meaningful_events[1:]):
            delta = (current["timestamp"] - previous["timestamp"]).total_seconds()
            if delta < 0:
                continue
            total_seconds += min(delta, inactivity_timeout)

        return total_seconds / 60.0  # Convert to minutes
    
    @staticmethod
    def should_count_toward_streak(session_id: str) -> bool:
        """
        Streak should only count if meaningful learning happened.
        
        Rules:
        - At least 10 meaningful events (not SHORT_ACK)
        - At least 1 concept mastered OR 3+ correct answers
        """
        metrics = EventAnalytics.get_session_metrics(session_id)
        
        has_min_events = metrics["total_meaningful_events"] >= 10
        has_learning = metrics["concepts_mastered"] >= 1 or metrics["answers_correct"] >= 3
        
        return has_min_events and has_learning
