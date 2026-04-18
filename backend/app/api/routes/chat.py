import logging
import uuid
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from app.schemas.chat import ChatRequest, ChatResponse, CitationSource
from app.graph.workflow import invoke_graph
from app.services import session as session_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint.
    Entire logic (load session, classify, retrieve, generate, save session)
    in LangGraph workflow — this route only prepares state and maps output.
    """
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"[Chat] session={session_id[:8]} | q={request.message[:60]}")

    try:
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "session_id": session_id,
            "history": [],
            "intent": None,
            "retrieved_context": None,
            "citations": [],
            "answer": None,
            "error": None,
        }

        # Run entire workflow
        result = invoke_graph(initial_state)

        answer = result.get("answer") or "Xin lỗi, tôi không tìm thấy thông tin liên quan."
        citations_raw = result.get("citations", [])
        intent = result.get("intent") or "qa"

        # Map CitationSource from graph state to schema response
        citations = [
            CitationSource(
                filename=c.filename if hasattr(c, "filename") else c["filename"],
                excerpt=c.excerpt if hasattr(c, "excerpt") else c["excerpt"],
                score=c.score if hasattr(c, "score") else c["score"],
                search_type=c.search_type if hasattr(c, "search_type") else c["search_type"],
            )
            for c in citations_raw
        ]

        logger.info(f"[Chat] Done | session={session_id[:8]} | intent={intent} | citations={len(citations)}")

        return ChatResponse(
            answer=answer,
            citations=citations,
            intent=intent,
            session_id=session_id,
        )

    except Exception as e:
        logger.error(f"[Chat] Unhandled error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/{session_id}", status_code=204)
async def clear_session(session_id: str):
    """Delete conversation history — used for 'New chat' button in frontend."""
    session_service.delete_session(session_id)
    logger.info(f"[Chat] Session cleared: {session_id[:8]}")