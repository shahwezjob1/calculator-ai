import logging
from typing import NotRequired

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.config import get_store

from calculator_agent.core.clients.calculations_api_client import CalculationsApiClient
from calculator_agent.core.clients.constants_api_client import ConstantsApiClient
from calculator_agent.core.clients.reviewer_api_client import ReviewerApiClient
from calculator_agent.core.llm.factory import build_chat_model
from calculator_agent.modules.calculator.agent.prompts.v1_0 import SYSTEM_PROMPT
from calculator_agent.modules.calculator.agent.tools import get_tools

logger = logging.getLogger(__name__)

try:
    from langchain.agents import AgentState
except ImportError:  # fallback for layout differences across langchain 1.x releases
    from langgraph.prebuilt.chat_agent_executor import AgentState


class CalculatorAgentState(AgentState):
    calculation_draft: NotRequired[dict | None]


def _build_middleware() -> list:
    middleware: list = []

    try:
        from langchain.agents.middleware import ModelRequest, dynamic_prompt

        @dynamic_prompt
        async def calculator_system_prompt(request: ModelRequest) -> str:
            sections = [SYSTEM_PROMPT]
            try:
                store = get_store()
                items = await store.asearch(("memories",), limit=50)
                if items:
                    lines = [f"- [key={item.key}] {item.value.get('fact', '')}" for item in items]
                    sections.append("## Known facts about the user\n" + "\n".join(lines))
            except Exception:
                logger.debug("Memory injection skipped (no store or store error)")
            return "\n\n".join(sections)

        middleware.append(calculator_system_prompt)
    except ImportError:
        logger.warning("dynamic_prompt middleware unavailable; memories will not be injected")

    try:
        from langchain.agents.middleware import HumanInTheLoopMiddleware

        middleware.append(
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "delete_calculation": {
                        "allowed_decisions": ["approve","edit", "reject"],
                    },
                    "delete_constant": {
                        "allowed_decisions": ["approve","edit", "reject"],
                    },
                },
                interrupt_mode="batched",
            )
        )
    except ImportError:
        logger.warning("HumanInTheLoopMiddleware unavailable; deletes are ungated")

    return middleware


def build_agent(
    model: BaseChatModel | None = None,
    checkpointer=None,
    store=None,
    constants_client: ConstantsApiClient | None = None,
    calculations_client: CalculationsApiClient | None = None,
    reviewer_client: ReviewerApiClient | None = None,
):
    return create_agent(
        model=model or build_chat_model(),
        tools=get_tools(constants_client, calculations_client, reviewer_client),
        middleware=_build_middleware(),
        state_schema=CalculatorAgentState,
        checkpointer=checkpointer,
        store=store,
    )


def make_graph():
    # langgraph dev entrypoint: NO checkpointer/store (the platform injects its own
    # persistence); API clients are built lazily from .env URLs - no database needed.
    return build_agent()
