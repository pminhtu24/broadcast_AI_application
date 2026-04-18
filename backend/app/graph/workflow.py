import logging
from langgraph.graph import StateGraph, END
from app.graph.state import ChatState
from app.graph.nodes import (
    classify_intent_node,
    retrieve_node,
    generate_node,
    format_response_node,
)
from app.graph.edges import route_after_classify, route_after_retrieve

logger = logging.getLogger(__name__)

compiled_graph = None


def build_graph() -> StateGraph:
    graph = StateGraph(ChatState)

    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("format_response", format_response_node)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "retrieve": "retrieve",
            "__end__": END,
        },
    )

    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "generate": "generate",
            "__end__": END,
        },
    )

    graph.add_edge("generate", "format_response")
    graph.add_edge("format_response", END)

    return graph


def get_compiled_graph():
    global compiled_graph
    if compiled_graph is None:
        logger.info("Building LangGraph workflow...")
        graph = build_graph()
        compiled_graph = graph.compile()
        logger.info("LangGraph workflow compiled successfully")
    return compiled_graph


def invoke_graph(state: dict) -> dict:
    graph = get_compiled_graph()
    return graph.invoke(state)
