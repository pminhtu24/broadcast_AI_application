import logging
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

_llm_instance = None

SUGGESTIONS_PATTERN = re.compile(r"<SUGGESTIONS>(.*?)</SUGGESTIONS>", re.DOTALL)


def parse_suggestions(text: str) -> tuple[str, list[str]]:
    """Parse suggestions from response text.
    
    Returns:
        tuple: (cleaned_text, list_of_suggestions)
    """
    match = SUGGESTIONS_PATTERN.search(text)
    if match:
        suggestions_text = match.group(1).strip()
        suggestions = [s.strip() for s in suggestions_text.split("|") if s.strip()]
        cleaned = SUGGESTIONS_PATTERN.sub("", text).strip()
        return cleaned, suggestions
    return text, []


def get_llm() -> ChatOpenAI:
    global _llm_instance
    if _llm_instance is None:
        settings = get_settings()
        logger.info(f"Initializing LLM with model: {settings.VIETTEL_MODEL}")
        _llm_instance = ChatOpenAI(
            base_url=settings.VIETTEL_BASE_URL,
            api_key=settings.VIETTEL_API_KEY.get_secret_value(),
            model=settings.VIETTEL_MODEL,
            temperature=0.3,
        )
    return _llm_instance


def classify_intent(question: str) -> str:
    """Classify user intent: 'qa' or 'calculate'"""
    llm = get_llm()
    from app.config.constants import INTENT_CLASSIFICATION_TEMPLATE

    response = llm.invoke(
        [
            SystemMessage(content=INTENT_CLASSIFICATION_TEMPLATE),
            HumanMessage(content=question),
        ]
    )
    result = str(response.content).strip().lower()
    logger.info(f"Intent classified: {result} for question: {question[:50]}...")
    return result if result in ["qa", "calculate"] else "qa"


def chat_with_context(question: str, context: str) -> str:
    """Generate response with context"""
    llm = get_llm()
    from app.config.constants import CHAT_SYSTEM_TEMPLATE

    template = CHAT_SYSTEM_TEMPLATE.replace("{context}", context)
    response = llm.invoke(
        [
            SystemMessage(content=template),
            HumanMessage(content=question),
        ]
    )
    return response.content


def calculate_with_context(question: str, context: str) -> str:
    """Generate calculation response with context"""
    llm = get_llm()
    from app.config.constants import CALCULATE_SYSTEM_TEMPLATE

    template = CALCULATE_SYSTEM_TEMPLATE.replace("{context}", context)
    response = llm.invoke(
        [
            SystemMessage(content=template),
            HumanMessage(content=question),
        ]
    )
    return response.content
