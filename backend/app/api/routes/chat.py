import logging
import uuid
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse, CitationSource
from app.services import retriever, llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - xử lý user message và trả về response với citations
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())

        logger.info(
            f"Processing chat request | session: {session_id[:8]} | message: {request.message[:50]}..."
        )

        intent = llm.classify_intent(request.message)
        logger.info(f"Detected intent: {intent}")

        chunks = retriever.hybrid_retrieve(request.message, top_k=5)

        if not chunks:
            return ChatResponse(
                answer="Xin lỗi, tôi không tìm thấy thông tin liên quan đến câu hỏi của bạn.",
                citations=[],
                intent=intent,
                session_id=session_id,
            )

        context, citations_data = retriever.format_for_llm(chunks)

        if intent == "calculate":
            answer = llm.calculate_with_context(request.message, context)
        else:
            answer = llm.chat_with_context(request.message, context)

        citations = [
            CitationSource(
                filename=c["filename"],
                excerpt=c["excerpt"],
                score=c["score"],
                search_type=c["search_type"],
            )
            for c in citations_data
        ]

        logger.info(
            f"Chat request completed | session: {session_id[:8]} | intent: {intent}"
        )

        return ChatResponse(
            answer=answer,
            citations=citations,
            intent=intent,
            session_id=session_id,
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
