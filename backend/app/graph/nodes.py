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
        intent = result if result in ["qa", "calculate", "quote"] else "qa"
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

# Node 4c: quote

QUOTE_SYSTEM_PROMPT = """Bạn là trợ lý tạo báo giá cho dịch vụ quảng cáo trên Báo và Phát thanh, Truyền hình Hải Phòng.

Khi người dùng yêu cầu xuất báo giá, bạn cần:

1. NẾU chưa có thông tin khách hàng:
   - Hỏi tên công ty/tổ chức và địa chỉ
   - Hỏi xem doanh nghiệp có trụ sở tại Hải Phòng không (để xác định bảng giá QĐ 415)

2. NẾU đã có thông tin khách hàng:
   - Trích xuất các dịch vụ đã được thảo luận từ ngữ cảnh cuộc hội thoại
   - Liệt kê các dịch vụ và hỏi xác nhận: "Bạn muốn báo giá cho những dịch vụ này đúng không?"
   - Nếu khách sửa, cập nhật lại danh sách

3. KHI ĐÃ CÓ ĐỦ THÔNG TIN:
   - Xác nhận: "Tôi sẽ tạo báo giá cho {tên khách} với {danh sách dịch vụ}"
   - Trả về JSON với action="generate_quote"

Định dạng trả về khi xác nhận tạo báo giá:
```json
{
  "action": "generate_quote",
  "customer_name": "Tên công ty",
  "customer_address": "Địa chỉ (nếu có)",
  "is_hp_business": true/false,
  "services": [
    {"service": "TVC", "frame": "HP8", "quantity": 50, "unit_price": 1000000, "total": 50000000}
  ]
}
```
"""


def _parse_customer_info_from_text(text: str, history: list) -> dict | None:
    """Parse customer info from user message using LLM."""
    import json
    llm = get_llm()

    prompt = f"""Trích xuất thông tin doanh nghiệp từ tin nhắn sau. Nếu có đủ tên công ty, trả về JSON:
{{"name": "...", "address": "...", "is_hp_business": true/false}}
Nếu không đủ thông tin, trả về: null

Tin nhắn: {text}

Trả về:"""

    try:
        response = llm.invoke([
            SystemMessage(content=prompt)
        ])
        result = str(response.content).strip()

        if result.startswith("{") and "null" not in result.lower():
            json_match = result if result.endswith("}") else result[:result.rfind("}")+1]
            data = json.loads(json_match)
            if data.get("name"):
                return data
    except:
        pass
    return None


def quote_node(state: ChatState) -> dict[str, Any]:
    from langchain_core.messages import SystemMessage, AIMessage
    from app.services.quote_generator import generate_quote_docx

    messages = state.get("messages", [])
    user_message = get_last_user_message(messages)
    history = state.get("history", [])
    context = state.get("retrieved_context", "")
    customer_info = state.get("customer_info")
    quote_status = state.get("quote_status")
    quote_items = state.get("quote_items", [])
    session_id = state.get("session_id", "")

    if not user_message:
        return {"answer": "Xin lỗi, tôi không nhận được yêu cầu.", "error": "No user message"}

    try:
        if not customer_info:
            extracted = _parse_customer_info_from_text(user_message, history)
            if extracted:
                customer_info = extracted
                logger.info(f"[Quote] Extracted customer info: {customer_info}")

        llm = get_llm()
        system_prompt = QUOTE_SYSTEM_PROMPT
        if context:
            system_prompt += f"\n\nNgữ cảnh từ tài liệu (để trích xuất dịch vụ đã thảo luận):\n{context}"

        llm_messages = _build_messages_with_history(system_prompt, user_message, history)

        if customer_info:
            customer_context = f"\n\nThông tin khách hàng đã có: {customer_info['name']}"
            if customer_info.get("address"):
                customer_context += f", {customer_info['address']}"
            if customer_info.get("is_hp_business"):
                customer_context += " (doanh nghiệp Hải Phòng - áp dụng QĐ 415)"
            llm_messages.append(SystemMessage(content=customer_context))

        if quote_items:
            items_context = "\n\nDịch vụ đã trích xuất:"
            for item in quote_items:
                items_context += f"\n- {item['service']}: {item['frame']}, {item['quantity']} lần, {item['unit_price']:,}đ = {item['total']:,}đ"
            llm_messages.append(SystemMessage(content=items_context))

        response = llm.invoke(llm_messages)
        answer = str(response.content)

        import re
        import json

        json_str = None
        if "```json" in answer:
            json_match = re.search(r"```json\s*(.*?)\s*```", answer, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
        elif answer.strip().startswith("{"):
            json_str = answer.strip()

        if json_str:
            try:
                data = json.loads(json_str)
                if data.get("action") == "generate_quote":
                    services = data.get("services", [])
                    is_hp = data.get("is_hp_business", False)

                    new_items = []
                    for svc in services:
                        service_type = svc.get("service", "").lower()
                        if any(kw in service_type for kw in ["phóng sự", "tài liệu", "tọa đàm", "livestream", "đăng bài"]):
                            price_list = "413"
                        elif is_hp:
                            price_list = "415"
                        else:
                            price_list = "414"

                        new_items.append({
                            "service": svc.get("service", ""),
                            "frame": svc.get("frame", ""),
                            "quantity": svc.get("quantity", 0),
                            "unit_price": svc.get("unit_price", 0),
                            "total": svc.get("total", 0),
                            "price_list": price_list,
                        })

                    group_414 = [i for i in new_items if i["price_list"] in ["414", "415"]]
                    group_413 = [i for i in new_items if i["price_list"] == "413"]

                    file_paths = []
                    for group_items, price_list in [(group_414, "414" if not is_hp else "415"), (group_413, "413")]:
                        if not group_items:
                            continue

                        docx_items = []
                        for item in group_items:
                            if price_list == "413":
                                docx_items.append({
                                    "content": item.get("content", item.get("service", "")),
                                    "type": item.get("type", ""),
                                    "duration": item.get("duration", ""),
                                    "quantity": item["quantity"],
                                    "unit_price": item["unit_price"],
                                })
                            else:
                                docx_items.append({
                                    "frame": item.get("frame", item.get("service", "")),
                                    "quantity": item["quantity"],
                                    "unit_price": item["unit_price"],
                                    "total": item["total"],
                                })

                        filename = generate_quote_docx(
                            customer_name=data.get("customer_name", ""),
                            items=docx_items,
                            price_list=price_list,
                            customer_address=data.get("customer_address"),
                        )
                        file_paths.append(filename)

                    new_answer = f"Tôi đã tạo báo giá cho **{data.get('customer_name', '')}** với {len(services)} dịch vụ.\n\n"
                    new_answer += "📄 Các file báo giá đã được tạo:\n"
                    for fp in file_paths:
                        pl = "QĐ 415" if "415" in fp else ("QĐ 413" if "413" in fp else "QĐ 414")
                        new_answer += f"- {pl}: `{fp}`\n"
                    new_answer += "\nBạn có thể tải xuống file DOCX để xem và chỉnh sửa."

                    return {
                        "answer": new_answer,
                        "quote_status": "generated",
                        "quote_file_path": ",".join(file_paths),
                        "customer_info": {
                            "name": data.get("customer_name", ""),
                            "address": data.get("customer_address"),
                            "is_hp_business": is_hp,
                        },
                        "quote_items": new_items,
                    }
            except json.JSONDecodeError:
                logger.warning(f"[Quote] Failed to parse JSON: {json_str[:100]}")

        return {
            "answer": answer,
            "customer_info": customer_info,
            "quote_items": quote_items,
            "quote_status": quote_status or ("awaiting_info" if not customer_info else "awaiting_items"),
        }

    except Exception as e:
        logger.error(f"[Quote] Error: {e}", exc_info=True)
        return {"answer": None, "error": str(e)}


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
