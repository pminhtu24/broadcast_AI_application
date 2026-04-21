import logging
from langgraph.graph import StateGraph, END
from app.graph.state import ChatState
from app.graph.nodes import (
    load_session_node,
    classify_intent_node,
    retrieve_node,
    generate_node,
    save_session_node,
    format_response_node,
)
from app.graph.edges import route_after_classify, route_after_retrieve

logger = logging.getLogger(__name__)

compiled_graph = None


def build_graph() -> StateGraph:
    graph = StateGraph(ChatState)
    graph.add_node("load_session", load_session_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("save_session", save_session_node)
    graph.add_node("format_response", format_response_node)
    graph.set_entry_point("load_session")

    # load_session -> classify_intent and retrieve run in parallel
    graph.add_edge("load_session", "classify_intent")
    graph.add_edge("load_session", "retrieve")

    # classify_intent -> retrieve (fan-in) -> generate
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

    # generate -> save_session -> format_response -> END
    graph.add_edge("generate", "save_session")
    graph.add_edge("save_session", "format_response")
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
    """Use for /api/chat — sync, return full response."""
    graph = get_compiled_graph()
    return graph.invoke(state)

async def prepare_for_stream(state: dict) -> dict:
    """
    Use for /api/chat/stream — run graph until BEFORE generate:
      load_session -> classify_intent + retrieve (parallel)
 
    Return state with:
      - history   (from Neo4j)
      - intent    (qa / calculate)
      - retrieved_context + citations
      - error     (if any)
 
    Route then call generate_stream() with this data to stream token.
    """
    import asyncio
    from app.graph.nodes import (
        load_session_node,
        classify_intent_node,
        retrieve_node,
    )
 
    # load session (sync)
    state = {**state, **load_session_node(state)}
 
    # classify + retrieve parallel
    loop = asyncio.get_event_loop()
    classify_task = loop.run_in_executor(None, classify_intent_node, state)
    retrieve_task  = loop.run_in_executor(None, retrieve_node, state)
 
    classify_result, retrieve_result = await asyncio.gather(
        classify_task, retrieve_task
    )
 
    state = {**state, **classify_result, **retrieve_result}
    return state