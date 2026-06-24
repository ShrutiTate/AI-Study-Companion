"""
Quiz Generation Service

Generates adaptive, session-based quizzes that reflect:
- Concepts taught in the session
- Student weak areas
- Student strong areas
- Session difficulty
- Emotional struggle points
"""

from typing import Dict, List, Any
from backend.db.mongo import sessions_collection
import json
import re
from groq import Groq
import os
from dotenv import load_dotenv

# Initialize Groq client
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")
groq_client = Groq(api_key=GROQ_API_KEY)

class QuizEngine:
    @staticmethod
    def get_session_data(session_id: str) -> Dict:
        """Fetch all session data including messages and feedback"""
        try:
            session = sessions_collection.find_one({"session_id": session_id})
            if not session:
                return None
            
            return {
                "messages": session.get("messages", []),
                "topic": session.get("topic", ""),
                "emotion_journey": QuizEngine._analyze_emotions(session.get("messages", []))
            }
        except Exception as e:
            print(f"[QUIZ] Error fetching session data: {e}")
            return None

    @staticmethod
    def _analyze_emotions(messages: List[Dict]) -> Dict:
        """Analyze emotional journey from messages"""
        emotions = {"engaged": 0, "neutral": 0, "confused": 0, "frustrated": 0}
        
        for msg in messages:
            if msg.get("role") == "assistant":
                emotion = msg.get("emotion", "neutral").lower()
                if emotion in emotions:
                    emotions[emotion] += 1
        
        return emotions

    @staticmethod
    def _extract_concepts(messages: List[Dict]) -> Dict:
        """Extract concepts and their difficulty levels from session"""
        concepts = {
            "all": [],
            "weak": [],
            "strong": []
        }
        
        try:
            # Analyze feedback to identify weak vs strong concepts
            weak_concepts = []
            strong_concepts = []
            seen_concepts = set()
            
            # Parse assistant messages for concept mentions
            for msg in messages:
                if msg.get("role") == "assistant":
                    content = msg.get("content", "").lower()
                    # Simple extraction: look for capitalized words (concepts)
                    words = content.split()
                    for i, word in enumerate(words):
                        if word[0].isupper() if word else False:
                            concept = word.rstrip(".,;:!?)")
                            if len(concept) > 3 and concept not in seen_concepts:
                                concepts["all"].append(concept)
                                seen_concepts.add(concept)
            
            # Remove duplicates
            concepts["all"] = list(set(concepts["all"]))[:15]  # Max 15 concepts
            
            return concepts
        except Exception as e:
            print(f"[QUIZ] Error extracting concepts: {e}")
            return concepts

    @staticmethod
    def _determine_difficulty(emotions: Dict, attempts: int) -> str:
        """Determine session difficulty based on emotions and attempts"""
        frustrated_ratio = emotions.get("frustrated", 0) / max(sum(emotions.values()), 1)
        confused_ratio = emotions.get("confused", 0) / max(sum(emotions.values()), 1)
        
        if frustrated_ratio > 0.3:
            return "easy"
        elif confused_ratio > 0.4:
            return "medium"
        else:
            return "medium"

    @staticmethod
    def generate_quiz(session_id: str, num_questions: int = 9) -> Dict:
        """
        Generate an adaptive quiz for the session
        
        Returns:
        {
            "success": bool,
            "questions": [
                {
                    "question": str,
                    "options": [str],
                    "answer": str,
                    "difficulty": str,
                    "concept": str
                }
            ],
            "metadata": {
                "total_questions": int,
                "difficulty_distribution": {"easy": int, "medium": int, "hard": int}
            }
        }
        """
        try:
            # Fetch session data
            session_data = QuizEngine.get_session_data(session_id)
            if not session_data:
                print(f"[QUIZ] Session {session_id} not found, returning mock quiz")
                return QuizEngine._generate_mock_quiz(num_questions)
            
            # Extract session info
            topic = session_data.get("topic", "Learning")
            messages = session_data.get("messages", [])
            
            # If session has no messages, return mock quiz
            if not messages:
                print(f"[QUIZ] Session {session_id} has no messages, returning mock quiz")
                return QuizEngine._generate_mock_quiz(num_questions, topic)
            
            emotions = session_data.get("emotion_journey", {})
            
            # Extract concepts
            concepts_data = QuizEngine._extract_concepts(messages)
            all_concepts = concepts_data.get("all", [])
            
            if not all_concepts:
                # Fallback: use topic as concept
                all_concepts = [topic]
            
            # Determine difficulty
            difficulty = QuizEngine._determine_difficulty(emotions, len(messages))
            
            # Generate quiz using AI
            print(f"[QUIZ] Generating quiz for session {session_id} with {len(all_concepts)} concepts")
            quiz_prompt = QuizEngine._build_quiz_prompt(
                topic=topic,
                concepts=all_concepts,
                emotions=emotions,
                difficulty=difficulty,
                num_questions=num_questions
            )
            
            # Call AI to generate quiz
            quiz_json = QuizEngine._call_ai_for_quiz(quiz_prompt)
            
            if quiz_json:
                return {
                    "success": True,
                    "questions": quiz_json,
                    "metadata": {
                        "total_questions": len(quiz_json),
                        "difficulty": difficulty,
                        "topic": topic,
                        "concepts_covered": all_concepts[:5]
                    }
                }
            else:
                # If AI generation fails, return mock
                print(f"[QUIZ] AI generation failed, returning mock quiz")
                return QuizEngine._generate_mock_quiz(num_questions, topic)
                
        except Exception as e:
            print(f"[QUIZ] Error generating quiz: {e}")
            import traceback
            traceback.print_exc()
            # Return mock quiz on error
            return QuizEngine._generate_mock_quiz(num_questions)
    
    @staticmethod
    def _generate_mock_quiz(num_questions: int = 9, topic: str = "Learning") -> Dict:
        """Generate a mock quiz for testing/fallback"""
        questions = []
        
        mock_questions_pool = [
            {
                "question": f"What is an important concept in {topic}?",
                "options": ["Concept A", "Concept B", "Concept C", "Concept D"],
                "answer": "Concept A",
                "difficulty": "easy",
                "concept": topic
            },
            {
                "question": f"How would you apply {topic} in practice?",
                "options": ["Practice 1", "Practice 2", "Practice 3", "Practice 4"],
                "answer": "Practice 1",
                "difficulty": "medium",
                "concept": topic
            },
            {
                "question": f"What is the relationship between X and Y in {topic}?",
                "options": ["Relationship 1", "Relationship 2", "Relationship 3", "Relationship 4"],
                "answer": "Relationship 1",
                "difficulty": "medium",
                "concept": topic
            },
            {
                "question": f"Which statement about {topic} is most accurate?",
                "options": ["Statement 1", "Statement 2", "Statement 3", "Statement 4"],
                "answer": "Statement 1",
                "difficulty": "hard",
                "concept": topic
            },
            {
                "question": f"What would happen if {topic} was applied differently?",
                "options": ["Outcome 1", "Outcome 2", "Outcome 3", "Outcome 4"],
                "answer": "Outcome 1",
                "difficulty": "hard",
                "concept": topic
            }
        ]
        
        # Create quiz with distribution: 30% easy, 50% medium, 20% hard
        easy_count = max(1, int(num_questions * 0.3))
        medium_count = max(2, int(num_questions * 0.5))
        hard_count = max(1, int(num_questions * 0.2))
        
        # Adjust to match num_questions
        total = easy_count + medium_count + hard_count
        if total > num_questions:
            hard_count -= (total - num_questions)
        elif total < num_questions:
            medium_count += (num_questions - total)
        
        for i in range(easy_count):
            q = mock_questions_pool[0].copy()
            q["question"] = f"Easy Question {i+1}: {q['question']}"
            questions.append(q)
        
        for i in range(medium_count):
            q = mock_questions_pool[min(i % len(mock_questions_pool), 2)].copy()
            q["question"] = f"Medium Question {i+1}: {q['question']}"
            questions.append(q)
        
        for i in range(hard_count):
            q = mock_questions_pool[min(3 + (i % 2), len(mock_questions_pool) - 1)].copy()
            q["question"] = f"Hard Question {i+1}: {q['question']}"
            questions.append(q)
        
        # Shuffle for randomness
        import random
        random.shuffle(questions)
        
        return {
            "success": True,
            "questions": questions[:num_questions],
            "metadata": {
                "total_questions": len(questions[:num_questions]),
                "difficulty": "mixed",
                "topic": topic,
                "concepts_covered": [topic],
                "note": "Mock quiz generated for testing"
            }
        }

    @staticmethod
    def _build_quiz_prompt(topic: str, concepts: List[str], emotions: Dict, difficulty: str, num_questions: int) -> str:
        """Build the prompt for AI quiz generation"""
        
        concepts_str = ", ".join(concepts[:8])
        emotions_str = json.dumps(emotions)
        
        prompt = f"""Generate a quiz with EXACTLY {num_questions} questions in JSON format.

TOPIC: {topic}
CONCEPTS COVERED: {concepts_str}
STUDENT EMOTIONS: {emotions_str}
DIFFICULTY LEVEL: {difficulty}

RULES:
1. Generate EXACTLY {num_questions} questions (no more, no less)
2. For {num_questions} questions, use this distribution:
   - {int(num_questions * 0.3)} easy questions
   - {int(num_questions * 0.5)} medium questions  
   - {int(num_questions * 0.2)} hard questions

3. Questions must be about {topic} and use concepts from: {concepts_str}

4. If student was frustrated, reduce difficulty and simplify wording

5. Question format: multiple choice (4 options)

6. Randomize option positions (correct answer not always in same spot)

7. Keep questions short and clear (Duolingo style)

8. No trick questions

9. Include conceptual understanding, simple application, and reasoning-based questions

RESPOND ONLY WITH VALID JSON:
[
  {{
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Correct option text",
    "difficulty": "easy/medium/hard",
    "concept": "Concept name"
  }}
]

NO MARKDOWN, NO EXPLANATIONS, ONLY JSON."""
        
        return prompt

    @staticmethod
    def _call_ai_for_quiz(prompt: str) -> List[Dict]:
        """Call Groq API to generate quiz and parse response"""
        try:
            print(f"[QUIZ] Calling Groq API for quiz generation...")
            
            # Call Groq directly for quiz generation with shorter timeout
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert quiz generator. Generate well-designed, educational quiz questions in JSON format. Respond ONLY with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.6,
                max_tokens=2000,
                timeout=15  # Reduced timeout to 15 seconds
            )
            
            response_text = response.choices[0].message.content
            print(f"[QUIZ] Groq response received: {len(response_text)} chars")
            
            if not response_text:
                return None
            
            # Extract JSON from response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            
            if json_match:
                quiz_data = json.loads(json_match.group())
                print(f"[QUIZ] Successfully parsed {len(quiz_data)} questions from JSON")
                
                # Validate and clean
                validated_questions = []
                for q in quiz_data:
                    if all(k in q for k in ['question', 'options', 'answer', 'difficulty', 'concept']):
                        # Ensure exactly 4 options
                        if len(q['options']) >= 4:
                            validated_questions.append({
                                "question": q['question'],
                                "options": q['options'][:4],
                                "answer": q['answer'],
                                "difficulty": q.get('difficulty', 'medium'),
                                "concept": q.get('concept', 'Unknown')
                            })
                
                print(f"[QUIZ] Validated {len(validated_questions)} questions out of {len(quiz_data)}")
                return validated_questions if validated_questions else None
            
            print("[QUIZ] No JSON found in response")
            return None
        except Exception as e:
            print(f"[QUIZ] Error parsing AI response: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback: return mock quiz for testing
            print("[QUIZ] Returning mock quiz due to error")
            return [
                {
                    "question": "What is a key concept from your learning?",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "answer": "Option A",
                    "difficulty": "medium",
                    "concept": "Concept"
                }
            ]
