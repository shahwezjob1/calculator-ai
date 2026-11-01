from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from calculator_agent.core.config import settings


def build_chat_model() -> BaseChatModel:
    return init_chat_model(settings.llm_model, model_provider=settings.llm_provider)


def build_title_model() -> BaseChatModel:
    # Plain chat model for 3-6 word thread titles; never given tools.
    return init_chat_model(settings.title_llm_model, model_provider=settings.title_llm_provider)
