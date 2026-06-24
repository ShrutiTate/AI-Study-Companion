# backend/services/response_contract.py
"""
Guaranteed response schema for all learning endpoints.
Prevents KeyError exceptions and ensures consistent API contract.
"""

from typing import Optional

class LearningResponse:
    """
    Centralized response builder with validation.
    All /learning/learn endpoint responses MUST use this.
    """
    
    REQUIRED_FIELDS = [
        "response", "text", "intent", "concept_index", "concepts_total",
        "advance_curriculum", "emotion", "cognitive_load", "cognitive_load_score",
        "session_id", "concept", "status", "stable_teaching_level", "evaluation"
    ]
    
    @staticmethod
    def build(
        response: str,
        intent: str,
        concept_index: int,
        concepts_total: int,
        advance_curriculum: bool,
        emotion: str,
        cognitive_load_score: int,
        session_id: str,
        concept: str,
        status: str,
        stable_teaching_level: str,
        evaluation: Optional[str] = None
    ) -> dict:
        """
        Build a guaranteed response schema with type validation.
        
        All parameters are explicitly required to prevent missing fields.
        
        Args:
            response: The tutoring response text
            intent: Student intent (answer/question/repair/refusal/etc)
            concept_index: Current position in curriculum (0-based)
            concepts_total: Total concepts in curriculum
            advance_curriculum: Whether to advance after this response
            emotion: Detected emotion (neutral/confused/frustrated/engaged/etc)
            cognitive_load_score: 1-5 scale (1=low, 5=high/overwhelmed)
            session_id: Session identifier
            concept: Current concept name
            status: Session status (active/completed/paused)
            stable_teaching_level: Student level (beginner/intermediate/advanced)
            evaluation: Answer quality (correct/partial/incorrect/None)
        
        Returns:
            dict: Validated response matching LearningResponse schema
        
        Raises:
            ValueError: If any required field is missing or invalid
            TypeError: If types don't match expected
        """
        
        # Type validation
        try:
            payload = {
                "response": str(response).strip(),
                "text": str(response).strip(),  # Alias for response
                "intent": str(intent).strip(),
                "concept_index": int(concept_index),
                "concepts_total": int(concepts_total),
                "advance_curriculum": bool(advance_curriculum),
                "emotion": str(emotion).strip().lower(),
                "cognitive_load": int(cognitive_load_score),  # Alias
                "cognitive_load_score": int(cognitive_load_score),
                "session_id": str(session_id).strip(),
                "concept": str(concept).strip(),
                "status": str(status).strip().lower(),
                "stable_teaching_level": str(stable_teaching_level).strip().lower(),
                "evaluation": str(evaluation).strip() if evaluation else None
            }
        except (ValueError, TypeError) as e:
            raise TypeError(f"[SCHEMA] Type conversion error: {e}")
        
        # Post-conversion validation
        if payload["concept_index"] < 0:
            raise ValueError(f"[SCHEMA] concept_index cannot be negative: {concept_index}")
        
        if payload["concepts_total"] < 0:
            raise ValueError(f"[SCHEMA] concepts_total cannot be negative: {concepts_total}")
        
        if payload["concept_index"] > payload["concepts_total"]:
            raise ValueError(
                f"[SCHEMA] concept_index ({payload['concept_index']}) > "
                f"concepts_total ({payload['concepts_total']})"
            )
        
        if payload["cognitive_load_score"] not in range(1, 6):
            raise ValueError(
                f"[SCHEMA] cognitive_load_score must be 1-5, got {cognitive_load_score}"
            )
        
        valid_emotions = {"neutral", "confused", "frustrated", "very_frustrated", "engaged", "very_engaged", "overwhelmed"}
        if payload["emotion"] not in valid_emotions:
            print(f"[SCHEMA] Warning: Unusual emotion '{emotion}' — accepting anyway")
        
        valid_statuses = {"active", "completed", "paused", "idle"}
        if payload["status"] not in valid_statuses:
            print(f"[SCHEMA] Warning: Unusual status '{status}' — accepting anyway")
        
        valid_levels = {"beginner", "intermediate", "advanced"}
        if payload["stable_teaching_level"] not in valid_levels:
            print(f"[SCHEMA] Warning: Unusual level '{stable_teaching_level}' — accepting anyway")
        
        # Verify all required fields present and not None (except evaluation which can be None)
        for field in LearningResponse.REQUIRED_FIELDS:
            if field not in payload:
                raise KeyError(f"[SCHEMA] Missing required field: {field}")
            if payload[field] is None and field != "evaluation":
                raise ValueError(f"[SCHEMA] Required field '{field}' cannot be None")
        
        print(f"[SCHEMA] ✅ Response validated — intent={payload['intent']}, concept_index={payload['concept_index']}")
        return payload
    
    @staticmethod
    def validate(response_dict: dict) -> bool:
        """
        Validate an existing response dict has all required fields.
        
        Args:
            response_dict: The response to validate
        
        Returns:
            True if valid
        
        Raises:
            KeyError: If any required field is missing
        """
        missing = [f for f in LearningResponse.REQUIRED_FIELDS if f not in response_dict]
        if missing:
            raise KeyError(f"[SCHEMA] Response missing required fields: {missing}")
        
        # Type checks
        if not isinstance(response_dict.get("concept_index"), int):
            raise TypeError(f"[SCHEMA] concept_index must be int, got {type(response_dict.get('concept_index'))}")
        
        if not isinstance(response_dict.get("advance_curriculum"), bool):
            raise TypeError(f"[SCHEMA] advance_curriculum must be bool, got {type(response_dict.get('advance_curriculum'))}")
        
        return True
