from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from calculator_reviewer.core.config import settings


def build_review_model() -> BaseChatModel:
    return init_chat_model(settings.review_llm_model, model_provider=settings.review_llm_provider)
