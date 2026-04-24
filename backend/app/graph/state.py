from typing import TypedDict, Annotated, List, Optional, Literal
from langchain_core.messages import BaseMessage
from app.schemas.chat import CitationSource, ChatMessage


class QuoteItem(TypedDict):
    service: str
    frame: str
    quantity: int
    unit_price: float
    total: float
    price_list: Literal["414", "415", "413"]
    content: Optional[str]
    type: Optional[str]
    duration: Optional[str]


class CustomerInfo(TypedDict):
    name: str
    address: Optional[str]
    is_hp_business: bool


class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], "append_messages"]
    history: List[ChatMessage]

    intent: Optional[str]
    retrieved_context: Optional[str]
    citations: List[CitationSource]

    customer_info: Optional[CustomerInfo]
    quote_items: List[QuoteItem]
    quote_status: Optional[str]
    quote_file_path: Optional[str]

    session_id: str
    answer: Optional[str]
    error: Optional[str]
