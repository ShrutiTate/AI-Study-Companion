"""
Analytics Engine - Active Learning Intelligence

Provides:
1. Emotion distribution tracking
2. Learning efficiency metrics (attempts per concept)
3. Drop-off point identification
4. Response effectiveness analysis
5. Adaptive teaching recommendations
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from backend.db.mongo import db
import logging
from cachetools import cached, TTLCache

logger = logging.getLogger(__name__)

session_metrics_cache = TTLCache(maxsize=100, ttl=300)
global_metrics_cache = TTLCache(maxsize=10, ttl=300)

class AnalyticsEngine:
    """Generates actionable learning analytics and adaptation signals"""
    
    @staticmethod
    @cached(cache=session_metrics_cache)
    def get_session_metrics(session_id: str) -> Dict:
        """
        Get comprehensive metrics for a session
        """
        try:
            session = db["sessions"].find_one({"session_id": session_id})
            if not session:
                return {}
            
            # Get messages array embedded in session
            messages = session.get("messages", [])
            
            if not messages:
                return {"concepts_covered": []}
            
            # Calculate emotion distribution
            emotion_counts = defaultdict(int)
            for msg in messages:
                if "emotion" in msg:
                    emotion_counts[msg["emotion"]] += 1
            
            total_emotions = sum(emotion_counts.values())
            emotion_distribution = {
                emotion: round((count / total_emotions * 100), 1)
                for emotion, count in emotion_counts.items()
            } if total_emotions > 0 else {}
            
            # Get concept mastery and current emotion from session
            concept_mastery = session.get("concept_mastery", {})
            current_emotion = session.get("emotion", "neutral")
            
            # Calculate response effectiveness based on concept mastery
            response_effectiveness = 0.0
            if concept_mastery:
                avg_score = sum(concept_mastery.values()) / len(concept_mastery)
                response_effectiveness = round(avg_score * 100, 1)
            elif current_emotion in ["engaged", "happy", "curious"]:
                response_effectiveness = 80.0
            elif current_emotion in ["frustrated", "confused"]:
                response_effectiveness = 30.0
            else:
                response_effectiveness = 50.0
            
            # Calculate learning efficiency per concept
            concept_attempts = defaultdict(int)
            for msg in messages:
                if msg.get("role") == "user" and msg.get("concept"):
                    concept_attempts[msg["concept"]] += 1
            
            learning_efficiency = 0.0
            if concept_attempts:
                learning_efficiency = round(
                    sum(concept_attempts.values()) / len(concept_attempts),
                    1
                )
            
            # Identify drop-off points (concepts with low mastery scores)
            drop_off_points = []
            high_confusion_topics = []
            for concept, score in concept_mastery.items():
                if score < 0.4:  # Equivalent to high confusion
                    drop_off_points.append(concept)
                    high_confusion_topics.append(concept)
                elif score < 0.6:  # Equivalent to needs attention
                    high_confusion_topics.append(concept)
            
            # Get concepts covered
            concepts_covered = session.get("explained_concepts", [])
            if not concepts_covered:
                concepts_covered = list(set([
                    msg.get("concept") for msg in messages 
                    if msg.get("concept") and msg.get("role") == "user"
                ]))
            
            # Calculate streak (just setting to 0 as feedback collection is gone)
            streak = 0
            
            # Calculate accuracy
            accuracy = response_effectiveness
            
            # Concepts mastered (concepts with >=70% mastery score)
            concepts_mastered = sum(
                1 for score in concept_mastery.values() if score >= 0.7
            )
            
            # Adaptation recommendations
            adaptation_recommendations = []
            if len(high_confusion_topics) > 0:
                adaptation_recommendations.append("simplify")
            # Consider both attempt_count (old) and turn_count/struggle_count (new)
            turn_count = session.get("turn_count", session.get("attempt_count", 0))
            if turn_count > 3 or learning_efficiency > 3:
                adaptation_recommendations.append("add_examples")
            if response_effectiveness < 50:
                adaptation_recommendations.append("break_down")
            if emotion_distribution.get("frustrated", 0) > 30 or current_emotion == "frustrated":
                adaptation_recommendations.append("encourage")
            
            return {
                "emotion_distribution": emotion_distribution,
                "learning_efficiency": learning_efficiency,
                "response_effectiveness": response_effectiveness,
                "drop_off_points": drop_off_points,
                "concepts_covered": concepts_covered,
                "high_confusion_topics": high_confusion_topics,
                "adaptation_recommendations": adaptation_recommendations,
                "streak": streak,
                "accuracy": accuracy,
                "concepts_mastered": concepts_mastered,
                "total_messages": len(messages),
                "total_feedback": 0,
                "session_id": session_id
            }
        
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return {}
    
    @staticmethod
    @cached(cache=global_metrics_cache)
    def get_global_analytics() -> Dict:
        """
        Get global analytics across all sessions
        
        Returns stats like:
        - Overall emotion distribution
        - Most confusing concepts
        - Response effectiveness trends
        - Teaching mode comparisons
        """
        try:
            all_sessions = list(db["sessions"].find())
            if not all_sessions:
                return {"error": "No sessions found"}
            
            emotion_global = defaultdict(int)
            concept_mastery_global = defaultdict(list)
            teaching_mode_stats = defaultdict(list)
            total_sessions = len(all_sessions)
            
            for session in all_sessions:
                # Emotion distribution from current session emotion
                emotion = session.get("emotion", "unknown")
                if emotion:
                    emotion_global[emotion] += 1
                
                # Concept effectiveness
                for concept, score in session.get("concept_mastery", {}).items():
                    concept_mastery_global[concept].append(score)
                
                # Teaching mode
                mode = session.get("teaching_mode", "standard")
                mastery = session.get("concept_mastery", {})
                if mastery:
                    avg_score = sum(mastery.values()) / len(mastery)
                    teaching_mode_stats[mode].append(avg_score)
            
            # Calculate percentages
            emotion_distribution = {
                emotion: round((count / total_sessions * 100), 1)
                for emotion, count in emotion_global.items()
            } if total_sessions > 0 else {}
            
            # Find most confusing concepts
            hardest_concepts = []
            for concept, scores in concept_mastery_global.items():
                if len(scores) > 0:
                    avg_score = sum(scores) / len(scores)
                    confusion_rate = (1.0 - avg_score) * 100
                    hardest_concepts.append({
                        "concept": concept,
                        "confusion_rate": round(confusion_rate, 1),
                        "avg_mastery": round(avg_score * 100, 1),
                        "occurrences": len(scores)
                    })
            
            hardest_concepts = sorted(hardest_concepts, key=lambda x: x["confusion_rate"], reverse=True)[:5]
            
            # Teaching mode effectiveness
            mode_effectiveness = {}
            for mode, scores in teaching_mode_stats.items():
                if scores:
                    effectiveness = round((sum(scores) / len(scores) * 100), 1)
                    mode_effectiveness[mode] = effectiveness
            
            # Overall stats
            overall_effectiveness = 0.0
            if concept_mastery_global:
                all_scores = [score for scores in concept_mastery_global.values() for score in scores]
                if all_scores:
                    overall_effectiveness = round((sum(all_scores) / len(all_scores) * 100), 1)
            
            return {
                "emotion_distribution": emotion_distribution,
                "hardest_concepts": hardest_concepts,
                "teaching_mode_effectiveness": mode_effectiveness,
                "overall_effectiveness": overall_effectiveness,
                "total_feedback": 0,
                "total_sessions": total_sessions,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error calculating global analytics: {e}")
            return {}
    
    @staticmethod
    def get_adaptation_signal(session_id: str) -> Dict:
        """
        Get real-time adaptation signal for active learning
        
        Returns what teaching parameters to adjust for this session
        """
        metrics = AnalyticsEngine.get_session_metrics(session_id)
        
        adaptation_signal = {
            "should_simplify": False,
            "should_add_examples": False,
            "should_break_down": False,
            "should_encourage": False,
            "teaching_mode": "standard",
            "max_response_length": 1000,
            "confidence_message": ""
        }
        
        # Determine teaching mode based on emotion
        emotion_dist = metrics.get("emotion_distribution", {})
        dominant_emotion = max(emotion_dist.items(), key=lambda x: x[1])[0] if emotion_dist else "neutral"
        
        if dominant_emotion == "frustrated":
            adaptation_signal["teaching_mode"] = "encouraging"
            adaptation_signal["should_encourage"] = True
            adaptation_signal["confidence_message"] = "⚡ Adjusting difficulty based on your responses..."
        
        elif dominant_emotion == "confused":
            adaptation_signal["teaching_mode"] = "simplified"
            adaptation_signal["should_simplify"] = True
            adaptation_signal["max_response_length"] = 500
            adaptation_signal["confidence_message"] = "⚡ Using simpler explanations..."
        
        elif dominant_emotion == "engaged":
            adaptation_signal["teaching_mode"] = "advanced"
            adaptation_signal["max_response_length"] = 1500
            adaptation_signal["confidence_message"] = "⚡ Advancing to more complex topics..."
        
        # Check confusion topics
        high_confusion = metrics.get("high_confusion_topics", [])
        if len(high_confusion) > 2:
            adaptation_signal["should_add_examples"] = True
            adaptation_signal["confidence_message"] = "⚡ Adding more examples to clarify..."
        
        # Check learning efficiency
        efficiency = metrics.get("learning_efficiency", 0)
        if efficiency > 3:  # Too many attempts
            adaptation_signal["should_break_down"] = True
            adaptation_signal["confidence_message"] = "⚡ Breaking down concepts into smaller steps..."
        
        return adaptation_signal

# Initialize analytics engine
analytics_engine = AnalyticsEngine()
