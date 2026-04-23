import logging
import json
from typing import Any, AsyncGenerator
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from app.graph.state import ChatState
from app.schemas.chat import CitationSource, ChatMessage
from app.services.retriever import hybrid_retrieve, format_for_llm
from app.services.llm import get_llm
from app.services import session as session_service
from app.services.tools import ALL_PRICING_TOOLS
from app.config.constants import CALCULATE_WITH_TOOLS_PROMPT

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

# Node 4: calculate

def calculate_node(state: ChatState) -> dict[str, Any]:
    """
    Node responsible for handling the 'calculate' intent using function calling.
    Instead of performing calculations directly, the LLM delegates computation
    to dedicated Python pricing tools to ensure accuracy.
    """
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
    from app.graph.nodes import get_last_user_message, _build_messages_with_history
 
    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)
    context = state.get("retrieved_context", "")
    history = state.get("history", [])
 
    if not user_message:
        return {"answer": "Xin lỗi, tôi không nhận được câu hỏi.", "error": "No user message"}
 
    try:
        llm = get_llm()
 
        # Bind tools into LLM — the LLM will know which tools can be called.
        llm_with_tools = llm.bind_tools(ALL_PRICING_TOOLS)
 
        system_prompt = CALCULATE_WITH_TOOLS_PROMPT
        if context:
            system_prompt += f"\n\nNgữ cảnh từ tài liệu (tham khảo thêm):\n{context}"
 
        # LLM decide which tool to call
        llm_messages = _build_messages_with_history(system_prompt, user_message, history)
        response = llm_with_tools.invoke(llm_messages)
 
        # Execute tool calls if applicable.
        tool_call_count = 0
        while response.tool_calls:
            tool_call_count += 1
            if tool_call_count > 10:
                # Tránh infinite loop
                logger.warning("[Calculate] Too many tool calls, stopping")
                break
 
            # Add LLM responses to messages.
            llm_messages.append(response)
 
            # Execute each tool call
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
 
                logger.info(f"[Calculate] Calling tool: {tool_name}({tool_args})")
 
                # Find and call the corresponding tool
                tool_fn = next(
                    (t for t in ALL_PRICING_TOOLS if t.name == tool_name),
                    None
                )
                if tool_fn is None:
                    tool_result = {"error": f"Tool '{tool_name}' không tồn tại"}
                else:
                    try:
                        tool_result = tool_fn.invoke(tool_args)
                    except Exception as e:
                        tool_result = {"error": str(e)}
 
                logger.info(f"[Calculate] Tool result: {tool_result}")
 
                # Return the tool's results to LLM.
                llm_messages.append(
                    ToolMessage(
                        content=json.dumps(tool_result, ensure_ascii=False),
                        tool_call_id=tool_id,
                    )
                )
 
            # LLM continues with tool results
            response = llm_with_tools.invoke(llm_messages)
 
        answer = str(response.content)
        logger.info(
            f"[Calculate] Done | {tool_call_count} tool calls | "
            f"{len(answer)} chars | history={len(history)} msgs"
        )
        return {"answer": answer}
 
    except Exception as e:
        logger.error(f"[Calculate] Error: {e}", exc_info=True)
        return {"answer": None, "error": str(e)}

# Node 5a: generate (sync — use for /api/chat)

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
        from app.config.constants import CHAT_SYSTEM_TEMPLATE

        llm = get_llm()
        system_prompt = CHAT_SYSTEM_TEMPLATE.replace("{context}", context)

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

# ---------------------------------------------------------------------------
# Node 5b: generate_stream (async generator — use for /api/chat/stream)
# called directly from route to yield token immediately when LLM returns,
# without waiting for completion.
# ---------------------------------------------------------------------------
 
async def generate_stream(
    user_message: str,
    context: str,
    intent: str,
    history: list[ChatMessage],
) -> AsyncGenerator[str, None]:
    from app.config.constants import CHAT_SYSTEM_TEMPLATE
    llm = get_llm()

    system_prompt = CHAT_SYSTEM_TEMPLATE.replace("{context}", context)

    llm_messages = _build_messages_with_history(system_prompt, user_message, history)

    try:
        async for chunk in llm.astream(llm_messages):
            token = chunk.content
            if token:
                yield token
    except Exception as e:
        logger.error(f"[GenerateStream] Error: {e}")
        yield f"\n\n[Lỗi khi tạo câu trả lời: {e}]"


async def generate_stream_and_collect(
    user_message: str,
    context: str,
    intent: str,
    history: list[ChatMessage],
):
    """True streaming: yields tokens immediately while collecting full response.
    
    Yields:
        str: token from LLM
    """
    from app.config.constants import CHAT_SYSTEM_TEMPLATE
    llm = get_llm()

    system_prompt = CHAT_SYSTEM_TEMPLATE.replace("{context}", context)

    llm_messages = _build_messages_with_history(system_prompt, user_message, history)

    try:
        async for chunk in llm.astream(llm_messages):
            token = chunk.content
            if token:
                yield ("token", token)
    except Exception as e:
        logger.error(f"[GenerateStream] Error: {e}")
        yield ("token", f"\n\n[Lỗi khi tạo câu trả lời: {e}]")
    except StopAsyncIteration:
        yield ("done", None)


async def generate_suggestions(
    user_message: str,
    answer: str,
) -> list[str]:
    """Generate follow-up question suggestions based on the answer."""
    from app.config.constants import SUGGESTIONS_TEMPLATE
    
    llm = get_llm()
    
    try:
        response = llm.invoke([
            SystemMessage(content=SUGGESTIONS_TEMPLATE),
            HumanMessage(content=f"Câu hỏi: {user_message}\n\nCâu trả lời:\n{answer}"),
        ])
        suggestions_text = str(response.content).strip()
        suggestions = [s.strip() for s in suggestions_text.split("|") if s.strip()]
        return suggestions[:3]
    except Exception as e:
        logger.error(f"[GenerateSuggestions] Error: {e}")
        return []

# Node 6: save_session
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


# Node 7: format_response

def format_response_node(state: ChatState) -> dict[str, Any]:
    answer = state.get("answer")
    citations = state.get("citations", [])
    error = state.get("error")

    if not answer:
        answer = f"Đã xảy ra lỗi: {error}" if error else "Xin lỗi, đã có lỗi xảy ra."

    return {"answer": answer, "citations": citations}
