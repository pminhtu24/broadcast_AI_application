from typing import Literal
from app.graph.state import ChatState


def route_after_classify(state: ChatState) -> Literal["retrieve", "__end__"]:
    intent = state.get("intent")
    error = state.get("error")
    if error and not intent:
        return "__end__"

    return "retrieve"


def route_after_retrieve(state: ChatState) -> Literal["generate", "calculate", "quote", "__end__"]:
    context = state.get("retrieved_context")
    intent = state.get("intent")
    if not context:
        return "__end__"
    if intent == "calculate":
        return "calculate"
    if intent == "quote":
        return "quote"
    return "generate"
