from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")


class CitationSource(BaseModel):
    filename: str = Field(..., description="Source document filename")
    excerpt: str = Field(..., description="Relevant excerpt from source")
    score: float = Field(..., description="Relevance score")
    search_type: str = Field(..., description="Search method used")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message/question")
    session_id: Optional[str] = Field(
        None, description="Session ID for conversation history"
    )
    conversation_history: Optional[List[ChatMessage]] = Field(
        default_factory=list, description="Previous messages in conversation"
    )


class ChatResponse(BaseModel):
    answer: str = Field(..., description="AI response")
    citations: List[CitationSource] = Field(..., description="Source citations")
    intent: Literal["qa", "calculate"] = Field(..., description="Detected user intent")
    session_id: str = Field(..., description="Session ID for this conversation")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")
    services: dict = Field(..., description="Service health status")
