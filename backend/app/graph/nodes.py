import logging
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from app.graph.state import ChatState, CitationSource
from app.services.retriever import hybrid_retrieve, format_for_llm
from app.services.llm import get_llm

logger = logging.getLogger(__name__)

INTENT_CLASSIFICATION_TEMPLATE = """
Phân loại câu hỏi:
- qa: hỏi thông tin, tra cứu bảng giá, hỏi về dịch vụ
- calculate: cần tính toán chi phí, báo giá cụ thể

Chỉ trả về đúng 1 từ: qa hoặc calculate
"""

CHAT_SYSTEM_TEMPLATE = """
Bạn là trợ lý AI của Đài Phát thanh và Truyền hình Hải Phòng, hỗ trợ phòng Quảng cáo – Kinh doanh.

### Nguyên tắc trả lời:
1. Trả lời chính xác, ngắn gọn dựa trên ngữ cảnh được cung cấp.
2. Nếu không có thông tin, nói rõ: "Tôi không có thông tin về vấn đề này."
3. KHÔNG bịa đặt thông tin ngoài ngữ cảnh.
4. Cuối mỗi câu trả lời ghi rõ nguồn tài liệu đã dùng.

QUAN TRỌNG: CHỈ trả lời dựa trên ngữ cảnh bên dưới.
"""


def get_last_user_message(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def classify_intent_node(state: ChatState) -> dict[str, Any]:
    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)

    if not user_message:
        logger.warning("No user message found in classify_intent")
        return {"intent": None, "error": "No user message"}

    try:
        llm = get_llm()
        response = llm.invoke(
            [
                SystemMessage(content=INTENT_CLASSIFICATION_TEMPLATE),
                HumanMessage(content=user_message),
            ]
        )
        result = str(response.content).strip().lower()
        intent = result if result in ["qa", "calculate"] else "qa"
        logger.info(f"Intent classified: {intent} for: {user_message[:50]}...")
        return {"intent": intent}
    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        return {"intent": "qa", "error": str(e)}


def retrieve_node(state: ChatState) -> dict[str, Any]:
    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)

    if not user_message:
        return {
            "retrieved_context": None,
            "citations": [],
            "error": "No user message to retrieve",
        }

    try:
        chunks = hybrid_retrieve(user_message, top_k=5)

        if not chunks:
            logger.warning(f"No chunks retrieved for: {user_message[:50]}...")
            return {"retrieved_context": None, "citations": []}

        context, citations_data = format_for_llm(chunks)

        citations = [
            CitationSource(
                filename=c["filename"],
                excerpt=c["excerpt"],
                score=c["score"],
                search_type=c["search_type"],
            )
            for c in citations_data
        ]

        logger.info(f"Retrieved {len(chunks)} chunks")
        return {
            "retrieved_context": context,
            "citations": citations,
        }
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        return {"retrieved_context": None, "citations": [], "error": str(e)}


def generate_node(state: ChatState) -> dict[str, Any]:
    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)
    context = state.get("retrieved_context", "")
    intent = state.get("intent", "qa")

    if not user_message:
        return {
            "answer": "Xin lỗi, tôi không nhận được câu hỏi.",
            "error": "No user message",
        }

    if not context:
        return {
            "answer": "Xin lỗi, tôi không tìm thấy thông tin liên quan đến câu hỏi của bạn.",
            "error": "No context retrieved",
        }

    try:
        llm = get_llm()

        if intent == "calculate":
            template = (
                """Bạn là chuyên viên tính chi phí quảng cáo của Đài PT-TH Hải Phòng.
Tính chi phí dựa trên ngữ cảnh và câu hỏi.
Trình bày rõ: đơn giá → tổng → chiết khấu → kết quả cuối.
Nếu thiếu thông tin, hỏi lại khách hàng.

Ngữ cảnh:
"""
                + context
            )
        else:
            template = CHAT_SYSTEM_TEMPLATE + f"\n\nNgữ cảnh:\n{context}"

        response = llm.invoke(
            [
                SystemMessage(content=template),
                HumanMessage(content=user_message),
            ]
        )
        answer = str(response.content)
        logger.info(f"Generated answer ({len(answer)} chars)")
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Generation error: {e}")
        return {"answer": None, "error": str(e)}


def format_response_node(state: ChatState) -> dict[str, Any]:
    answer = state.get("answer")
    citations = state.get("citations", [])
    error = state.get("error")

    if error and not answer:
        answer = f"Đã xảy ra lỗi: {error}"

    return {
        "answer": answer,
        "citations": citations,
    }
