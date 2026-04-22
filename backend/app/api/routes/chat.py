import json
import logging
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from app.schemas.chat import ChatRequest, ChatResponse, CitationSource
from app.graph.workflow import invoke_graph, prepare_for_stream
from app.graph.nodes import generate_stream_and_collect, generate_suggestions, get_last_user_message
from app.services import session as session_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint.
    Entire logic (load session, classify, retrieve, generate, save session)
    this route only prepares state and maps output.
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

# ---------------------------------------------------------------------------
# POST /api/chat/stream — SSE streaming endpoint
# ---------------------------------------------------------------------------
 
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming endpoint dùng Server-Sent Events (SSE).
 
    Protocol SSE — mỗi event có format:
        data: <json_string>\\n\\n
 
    Các loại event client nhận được theo thứ tự:
        1. {"type": "meta",   "intent": "qa", "session_id": "..."}
        2. {"type": "token",  "content": "từng token..."}   (nhiều lần)
        3. {"type": "citations", "data": [...]}
        4. {"type": "done"}
 
    Nếu có lỗi:
        {"type": "error", "message": "..."}
    """
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"[Stream] session={session_id[:8]} | q={request.message[:60]}")
 
    async def event_generator():
        full_answer = ""
 
        try:
            # -----------------------------------------------------------
            # Bước 1+2: load_session + classify + retrieve (parallel)
            # -----------------------------------------------------------
            state = await prepare_for_stream({
                "messages": [HumanMessage(content=request.message)],
                "session_id": session_id,
                "history": [],
                "intent": None,
                "retrieved_context": None,
                "citations": [],
                "answer": None,
                "error": None,
            })
 
            intent = state.get("intent") or "qa"
            context = state.get("retrieved_context")
            citations_raw = state.get("citations", [])
            history = state.get("history", [])
            user_message = get_last_user_message(state["messages"])
 
            # Gửi meta ngay — client biết intent và session_id trước khi token về
            yield _sse({"type": "meta", "intent": intent, "session_id": session_id})
 
            # -----------------------------------------------------------
            # Fallback nếu không tìm được context
            # -----------------------------------------------------------
            if not context:
                fallback = "Xin lỗi, tôi không tìm thấy thông tin liên quan đến câu hỏi của bạn."
                yield _sse({"type": "token", "content": fallback})
                yield _sse({"type": "citations", "data": []})
                yield _sse({"type": "done"})
                session_service.save_turn(session_id, user_message, fallback, intent)
                return
 
# -----------------------------------------------------------
            # Bước 3: stream tokens từ LLM (TRUE streaming - token về ngay)
            # đồng thời collect full answer để generate suggestions sau
            # -----------------------------------------------------------
            async for event_type, value in generate_stream_and_collect(
                user_message, context, intent, history
            ):
                if event_type == "token":
                    full_answer += value
                    yield _sse({"type": "token", "content": value})

            # -----------------------------------------------------------
            # Bước 4: generate suggestions sau khi stream xong
            # -----------------------------------------------------------
            logger.info(f"[Stream] Generating suggestions for session={session_id[:8]}")
            suggestions = await generate_suggestions(user_message, full_answer)
            if suggestions:
                yield _sse({"type": "suggestions", "data": suggestions})

            # -----------------------------------------------------------
            # Bước 6: gửi citations và done
            # -----------------------------------------------------------
            citations = [
                {
                    "filename":    c.filename if hasattr(c, "filename") else c["filename"],
                    "excerpt":     c.excerpt if hasattr(c, "excerpt") else c["excerpt"],
                    "score":       c.score if hasattr(c, "score") else c["score"],
                    "search_type": c.search_type if hasattr(c, "search_type") else c["search_type"],
                }
                for c in citations_raw
            ]
            yield _sse({"type": "citations", "data": citations})
            yield _sse({"type": "done"})
 
            # -----------------------------------------------------------
            # Bước 5: lưu session (sau khi stream xong)
            # -----------------------------------------------------------
            session_service.save_turn(session_id, user_message, full_answer, intent)
            logger.info(f"[Stream] Done | session={session_id[:8]} | intent={intent} | {len(full_answer)} chars")
 
        except Exception as e:
            logger.error(f"[Stream] Error: {e}", exc_info=True)
            yield _sse({"type": "error", "message": str(e)})
 
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # Tắt buffering để token về ngay, không bị gom batch
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.delete("/chat/{session_id}", status_code=204)
async def clear_session(session_id: str):
    """Delete conversation history — used for 'New chat' button in frontend."""
    session_service.delete_session(session_id)
    logger.info(f"[Chat] Session cleared: {session_id[:8]}")


@router.get("/chat/sessions")
async def get_sessions():
    """List all sessions."""
    sessions = session_service.list_sessions()
    return {"sessions": sessions}


@router.get("/chat/{session_id}/history")
async def get_session_history(session_id: str):
    """Get message history for a session."""
    messages = session_service.load_history(session_id)
    return {"messages": messages}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
 
def _sse(data: dict) -> str:
    """Format một SSE event đúng chuẩn."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"