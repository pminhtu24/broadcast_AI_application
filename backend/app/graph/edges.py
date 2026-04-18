from typing import Literal
from app.graph.state import ChatState


def route_after_classify(state: ChatState) -> Literal["retrieve", "__end__"]:
    intent = state.get("intent")
    error = state.get("error")
    if error and not intent:
        return "__end__"

    return "retrieve"


def route_after_retrieve(state: ChatState) -> Literal["generate", "__end__"]:
    context = state.get("retrieved_context")
    if not context:
        return "__end__"
    return "generate"
