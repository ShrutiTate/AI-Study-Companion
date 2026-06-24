#rag.py
"""
Mini-RAG Service
Handles text chunking, content storage, and retrieval
Integrated with AI Tutor for intelligent explanations
"""

from backend.db.mongo import db
from typing import List, Optional
import uuid
from backend.services.ai_tutor import generate_ai_response

def chunk_text(text: str, size: int = 300) -> List[str]:
    """
    Split text into chunks of specified size.
    
    Args:
        text: Text to chunk
        size: Chunk size in characters (default 300)
    
    Returns:
        List of text chunks
    """
    chunks = []
    for i in range(0, len(text), size):
        chunks.append(text[i:i+size])
    return chunks


def save_content(user_id: str, topic: str, text: str) -> dict:
    """
    Save user content (study material) to database.
    Content is chunked and stored for later retrieval.
    Topic is normalized to lowercase for consistency.
    
    Args:
        user_id: User ID
        topic: Learning topic
        text: Study material content
    
    Returns:
        Success status and content_id
    """
    try:
        chunks = chunk_text(text)
        
        # Normalize topic to lowercase for consistency
        topic_normalized = topic.lower() if topic else "general"
        
        doc = {
            "content_id": str(uuid.uuid4()),
            "user_id": user_id,
            "topic": topic_normalized,
            "chunks": chunks,
            "original_text": text,
            "chunk_count": len(chunks)
        }
        
        result = db["content"].insert_one(doc)
        
        return {
            "success": True,
            "content_id": doc["content_id"],
            "chunk_count": len(chunks),
            "topic_normalized": topic_normalized
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_relevant_chunk(query: str, chunks: List[str]) -> str:
    """
    Find the most relevant chunk for a given query.
    Uses simple keyword matching.
    
    Args:
        query: User query/question
        chunks: List of text chunks to search
    
    Returns:
        Most relevant chunk or first chunk as fallback
    """
    if not chunks:
        return ""
    
    query_words = query.lower().split()
    
    # Score each chunk by matching words
    best_chunk = chunks[0]
    best_score = 0
    
    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(1 for word in query_words if word in chunk_lower)
        
        if score > best_score:
            best_score = score
            best_chunk = chunk
    
    return best_chunk


def get_user_content(user_id: str, topic: str) -> Optional[dict]:
    """
    Retrieve content document for user and topic.
    Uses case-insensitive topic matching.
    
    Args:
        user_id: User ID
        topic: Learning topic
    
    Returns:
        Content document or None if not found
    """
    try:
        # Normalize topic to lowercase for consistent matching
        topic_normalized = topic.lower() if topic else ""
        
        # Try to find content with case-insensitive topic match
        content = db["content"].find_one({
            "user_id": user_id,
            "topic": {"$regex": f"^{topic_normalized}$", "$options": "i"}
        })
        
        if content:
            return content
        
        # Fallback: exact case-sensitive match
        content = db["content"].find_one({
            "user_id": user_id,
            "topic": topic
        })
        
        return content
    except Exception as e:
        print(f"Error retrieving content: {e}")
        return None


def rag_pipeline(user_input: str, user_id: str, topic: str, emotion: str, teaching_mode: str = "adaptive", enhanced_context: str = "") -> dict:
    """
    Complete RAG pipeline with AI tutor integration:
    1. Detect emotion (already done before calling)
    2. Retrieve relevant content (case-insensitive)
    3. Get relevant chunk
    4. Transform chunk into intelligent explanation using Groq
    5. Return emotion + explanation + example + quick_check
    
    Args:
        user_input: User's question/statement
        user_id: User ID
        topic: Learning topic from session
        emotion: Pre-detected emotion
        teaching_mode: How to adapt explanation ("adaptive", "simplify", "teach_basic", "advanced")
        enhanced_context: Additional context to control response structure and style
    
    Returns:
        Dictionary with emotion, explanation, example, quick_check, and raw chunk
    """
    
    print(f"\n[RAG] Pipeline starting for topic: {topic}, emotion: {emotion}, mode: {teaching_mode}")
    
    # Normalize topic for safe retrieval
    topic_normalized = topic.lower() if topic else "general"
    
    # Try to find content for this user and topic (case-insensitive)
    content = get_user_content(user_id, topic_normalized)
    has_content = content is not None
    chunk_count = 0
    
    if has_content:
        print(f"[RAG] Content found! Chunks: {content.get('chunk_count', 0)}")
        chunk_count = content.get('chunk_count', 0)
        # Get relevant chunk from content
        chunk = get_relevant_chunk(user_input, content["chunks"])
        print(f"[RAG] Retrieved chunk, length: {len(chunk)}")
    else:
        print(f"[RAG] No content found for topic: {topic_normalized}. Using topic+question as context.")
        # Use topic and user input as the "chunk" for Groq to work with
        chunk = f"Topic: {topic}\n\nUser Question: {user_input}"
        print(f"[RAG] Using generated context, length: {len(chunk)}")
    
    # Generate AI-powered response using Groq
    print(f"[RAG] Calling Groq AI tutor...")
    ai_response = generate_ai_response(
        topic=topic_normalized,
        chunk=chunk,
        emotion=emotion,
        teaching_mode=teaching_mode,
        enhanced_context=enhanced_context
    )
    print(f"[RAG] Groq response received. Success: {ai_response.get('success')}")
    
    # Build the response
    if ai_response.get("success"):
        print(f"[RAG] Returning AI-powered response")
        return {
            "emotion": emotion,
            "explanation": ai_response.get("explanation", ""),
            "example": ai_response.get("example", ""),
            "quick_check": ai_response.get("quick_check", ""),
            "chunk": chunk,
            "chunk_count": chunk_count,
            "has_content": has_content,
            "message": None,
            "ai_powered": True
        }
    else:
        # Fallback if AI generation fails
        print(f"[RAG] AI failed, returning fallback. Error: {ai_response.get('error')}")
        return {
            "emotion": emotion,
            "chunk": chunk,
            "explanation": f"Here's a section to learn:\n{chunk}",
            "example": "Review the material above.",
            "quick_check": "What was the main point?",
            "chunk_count": chunk_count,
            "has_content": has_content,
            "message": None,
            "ai_powered": False,
            "error": ai_response.get("error", "")
        }
