from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from app.schemas.chat import ChatMessage


class CitationSource(BaseModel):
    filename: str
    excerpt: str
    score: float
    search_type: str


class ChatState(TypedDict):
    # LangGraph append-only message list
    messages: Annotated[List[BaseMessage], "append_messages"]

    # Conversation history from Neo4j — generate_node for LLM context
    history: List[ChatMessage]

    # Result from nodes
    intent: Optional[str]
    retrieved_context: Optional[str]
    citations: List[CitationSource]

    # Final Output
    session_id: str
    answer: Optional[str]
    error: Optional[str]
