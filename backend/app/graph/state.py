from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class CitationSource(BaseModel):
    filename: str
    excerpt: str
    score: float
    search_type: str


class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], "append_messages"]
    intent: Optional[str]
    retrieved_context: Optional[str]
    citations: List[CitationSource]
    session_id: str
    answer: Optional[str]
    error: Optional[str]
