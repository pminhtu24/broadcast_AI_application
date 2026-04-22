import logging
from datetime import datetime
from typing import List
from app.schemas.chat import ChatMessage
from app.services.retriever import get_graph_db

logger = logging.getLogger(__name__)

# Limit the number of messages to keep to avoid context window overflow
MAX_HISTORY_MESSAGES = 10


def _get_db():
    return get_graph_db()


def load_history(session_id: str) -> List[ChatMessage]:
    """
    Load conversation history from Neo4j.
    Return empty list if session does not exist.
    """
    db = _get_db()
    try:
        result = db.query(
            """
            MATCH (:ChatSession {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
            RETURN m.role AS role, m.content AS content
            ORDER BY m.timestamp ASC
            LIMIT $limit
            """,
            {"session_id": session_id, "limit": MAX_HISTORY_MESSAGES},
        )
        messages = [ChatMessage(role=r["role"], content=r["content"]) for r in result]
        logger.debug(f"[Session] Loaded {len(messages)} messages for {session_id[:8]}")
        return messages
    except Exception as e:
        logger.error(f"[Session] load_history error: {e}")
        return []


def save_turn(
    session_id: str, user_message: str, assistant_message: str, intent: str
) -> None:
    """
    Save a conversation turn (user + assistant) to Neo4j.
    Auto-create ChatSession if it doesn't exist (MERGE).
    """
    db = _get_db()
    now = datetime.utcnow().isoformat()
    try:
        db.query(
            """
            MERGE (s:ChatSession {session_id: $session_id})
            ON CREATE SET s.created_at = $now
            SET s.updated_at = $now

            CREATE (u:Message {
                role:      'user',
                content:   $user_content,
                timestamp: $now,
                intent:    $intent
            })
            CREATE (a:Message {
                role:      'assistant',
                content:   $assistant_content,
                timestamp: $now_a,
                intent:    $intent
            })

            CREATE (s)-[:HAS_MESSAGE]->(u)
            CREATE (s)-[:HAS_MESSAGE]->(a)
            """,
            {
                "session_id": session_id,
                "user_content": user_message,
                "assistant_content": assistant_message,
                "intent": intent,
                "now": now,
                # Offset nhỏ để assistant message luôn sau user message khi ORDER BY
                "now_a": datetime.utcnow().isoformat(),
            },
        )
        logger.debug(f"[Session] Saved turn for {session_id[:8]}")
    except Exception as e:
        # Don't raise — session save error should not break response
        logger.error(f"[Session] save_turn error: {e}")


def delete_session(session_id: str) -> None:
    """Delete entire session and messages — used for reset chat."""
    db = _get_db()
    try:
        db.query(
            """
            MATCH (s:ChatSession {session_id: $session_id})
            OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
            DETACH DELETE s, m
            """,
            {"session_id": session_id},
        )
        logger.info(f"[Session] Deleted session {session_id[:8]}")
    except Exception as e:
        logger.error(f"[Session] delete_session error: {e}")


def list_sessions() -> List[dict]:
    """List all sessions ordered by updated_at desc."""
    db = _get_db()
    try:
        result = db.query(
            """
            MATCH (s:ChatSession)
            RETURN s.session_id AS id, s.updated_at AS updatedAt, s.created_at AS createdAt
            ORDER BY s.updated_at DESC
            """,
        )
        return [
            {
                "id": r["id"],
                "updatedAt": r["updatedAt"],
                "createdAt": r["createdAt"],
            }
            for r in result
        ]
    except Exception as e:
        logger.error(f"[Session] list_sessions error: {e}")
        return []
