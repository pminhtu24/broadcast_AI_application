import logging
import os

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """Configure LangSmith tracing from backend settings.

    Tracing is intentionally opt-in so local development and deployments without
    a LangSmith key keep running exactly as before.
    """
    settings = get_settings()
    api_key = (
        settings.LANGSMITH_API_KEY.get_secret_value()
        if settings.LANGSMITH_API_KEY
        else ""
    )

    if not settings.LANGSMITH_TRACING:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        logger.info("LangSmith tracing disabled")
        return

    if not api_key:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        logger.warning("LangSmith tracing requested but LANGSMITH_API_KEY is empty")
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT

    logger.info("LangSmith tracing enabled | project=%s", settings.LANGSMITH_PROJECT)
