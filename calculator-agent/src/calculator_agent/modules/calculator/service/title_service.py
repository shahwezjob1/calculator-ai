import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

TITLE_PROMPT = (
    "Generate a concise 3-6 word title for a calculator conversation that starts with "
    "the user message below. Return ONLY the title, no quotes, no punctuation at the end."
)


class TitleService:
    logger = logging.getLogger(__name__)

    def __init__(self, title_model: BaseChatModel):
        self._title_model = title_model

    async def generate(self, first_message: str) -> str:
        try:
            response = await self._title_model.ainvoke(
                [SystemMessage(content=TITLE_PROMPT), HumanMessage(content=first_message)]
            )
            title = response.text() if callable(getattr(response, "text", None)) else str(response.content)
            title = " ".join(title.split()).strip().strip('"')
            if title:
                return title[:255]
        except Exception:
            self.logger.warning("Title generation failed; falling back to truncated prompt")
        # Fallback: first 255 chars of the user prompt (matches thread_name VARCHAR(255)).
        return first_message[:255]
