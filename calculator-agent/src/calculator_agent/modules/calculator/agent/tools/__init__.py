from calculator_agent.core.clients import lazy
from calculator_agent.core.clients.calculations_api_client import CalculationsApiClient
from calculator_agent.core.clients.constants_api_client import ConstantsApiClient
from calculator_agent.core.clients.reviewer_api_client import ReviewerApiClient
from calculator_agent.modules.calculator.agent.tools.calculations import build_calculation_tools
from calculator_agent.modules.calculator.agent.tools.constants import build_constant_tools
from calculator_agent.modules.calculator.agent.tools.expression import build_expression_tools
from calculator_agent.modules.calculator.agent.tools.memory import build_memory_tools


def get_tools(
    constants_client: ConstantsApiClient | None = None,
    calculations_client: CalculationsApiClient | None = None,
    reviewer_client: ReviewerApiClient | None = None,
) -> list:
    # Outside the FastAPI lifespan (langgraph dev), clients are built lazily from .env.
    constants_client = constants_client or lazy.default_constants_client()
    calculations_client = calculations_client or lazy.default_calculations_client()
    reviewer_client = reviewer_client or lazy.default_reviewer_client()
    return [
        *build_expression_tools(constants_client),
        *build_memory_tools(),
        *build_constant_tools(constants_client),
        *build_calculation_tools(calculations_client, reviewer_client),
    ]
