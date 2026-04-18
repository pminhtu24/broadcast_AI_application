import logging
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from app.graph.state import ChatState, CitationSource
from app.services.retriever import hybrid_retrieve, format_for_llm
from app.services.llm import get_llm
from app.services import session as session_service
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)


# Helpers
def get_last_user_message(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _build_messages_with_history(
    system_prompt: str,
    question: str,
    history: list[ChatMessage],
) -> list:
    msgs: list = [SystemMessage(content=system_prompt)]
    for msg in history:
        if msg.role == "user":
            msgs.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            msgs.append(AIMessage(content=msg.content))
    msgs.append(HumanMessage(content=question))
    return msgs


# Node 1: load_session
# Load conversation history from Neo4j before starting the graph


def load_session_node(state: ChatState) -> dict[str, Any]:
    """
    Load history from Neo4j theo session_id.
    Nếu session mới → trả về list rỗng, không lỗi.
    """
    session_id = state.get("session_id", "")
    if not session_id:
        return {"history": []}

    history = session_service.load_history(session_id)
    logger.info(f"[LoadSession] {len(history)} messages | session={session_id[:8]}")
    return {"history": history}


# Node 2: classify_intent


def classify_intent_node(state: ChatState) -> dict[str, Any]:
    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)

    if not user_message:
        logger.warning("[ClassifyIntent] No user message found")
        return {"intent": None, "error": "No user message"}

    try:
        from app.config.constants import INTENT_CLASSIFICATION_TEMPLATE

        llm = get_llm()
        response = llm.invoke(
            [
                SystemMessage(content=INTENT_CLASSIFICATION_TEMPLATE),
                HumanMessage(content=user_message),
            ]
        )
        result = str(response.content).strip().lower()
        intent = result if result in ["qa", "calculate"] else "qa"
        logger.info(f"[ClassifyIntent] '{intent}' ← {user_message[:60]}")
        return {"intent": intent}
    except Exception as e:
        logger.error(f"[ClassifyIntent] Error: {e}")
        # Fallback về qa thay vì crash
        return {"intent": "qa", "error": str(e)}


# Node 3: retrieve


def retrieve_node(state: ChatState) -> dict[str, Any]:
    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)

    if not user_message:
        return {"retrieved_context": None, "citations": [], "error": "No user message"}

    try:
        chunks = hybrid_retrieve(user_message, top_k=5)

        if not chunks:
            logger.warning(f"[Retrieve] No chunks for: {user_message[:60]}")
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
        logger.info(f"[Retrieve] {len(chunks)} chunks retrieved")
        return {"retrieved_context": context, "citations": citations}
    except Exception as e:
        logger.error(f"[Retrieve] Error: {e}")
        return {"retrieved_context": None, "citations": [], "error": str(e)}


# Node 4: generate
# Use history to let LLM understand the previous conversation context


def generate_node(state: ChatState) -> dict[str, Any]:
    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)
    context = state.get("retrieved_context", "")
    intent = state.get("intent", "qa")
    history = state.get("history", [])

    if not user_message:
        return {
            "answer": "Xin lỗi, tôi không nhận được câu hỏi.",
            "error": "No user message",
        }

    if not context:
        return {
            "answer": "Xin lỗi, tôi không tìm thấy thông tin liên quan đến câu hỏi của bạn.",
            "error": "No context",
        }

    try:
        from app.config.constants import (
            CHAT_SYSTEM_TEMPLATE,
            CALCULATE_SYSTEM_TEMPLATE,
        )

        llm = get_llm()

        if intent == "calculate":
            system_prompt = CALCULATE_SYSTEM_TEMPLATE.replace("{context}", context)
        else:
            system_prompt = CHAT_SYSTEM_TEMPLATE.replace("{context}", context)

        # Key fix: truyền history vào đây
        llm_messages = _build_messages_with_history(
            system_prompt, user_message, history
        )
        response = llm.invoke(llm_messages)
        answer = str(response.content)
        logger.info(
            f"[Generate] {len(answer)} chars | intent={intent} | history={len(history)} msgs"
        )
        return {"answer": answer}
    except Exception as e:
        logger.error(f"[Generate] Error: {e}")
        return {"answer": None, "error": str(e)}


# Node 5: save_session
# Save new turn to Neo4j after generating the response


def save_session_node(state: ChatState) -> dict[str, Any]:
    """
    Save conversation turn to Neo4j.
    """
    session_id = state.get("session_id", "")
    answer = state.get("answer")
    intent = state.get("intent", "qa")
    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)

    if session_id and user_message and answer:
        session_service.save_turn(session_id, user_message, answer, intent)
        logger.info(f"[SaveSession] Saved turn | session={session_id[:8]}")

    return {}


# Node 6: format_response


def format_response_node(state: ChatState) -> dict[str, Any]:
    answer = state.get("answer")
    citations = state.get("citations", [])
    error = state.get("error")

    if not answer:
        answer = f"Đã xảy ra lỗi: {error}" if error else "Xin lỗi, đã có lỗi xảy ra."

    return {"answer": answer, "citations": citations}
