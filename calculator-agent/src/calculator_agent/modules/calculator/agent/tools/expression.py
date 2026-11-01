import logging

from langchain_core.tools import tool

from calculator_agent.core.clients.constants_api_client import ConstantsApiClient
from calculator_agent.core.clients.errors import UpstreamServiceError
from calculator_agent.modules.calculator.agent.evaluator import ExpressionEvaluator

logger = logging.getLogger(__name__)


def build_expression_tools(constants_client: ConstantsApiClient):
    evaluator = ExpressionEvaluator(constants_client)

    @tool
    async def evaluate_expression(expression: str) -> str:
        """Evaluate exactly ONE mathematical expression and return its numeric result.

        Allowed: numbers, operators + - * / // % **, parentheses, the functions
        sqrt, abs, round, log, log10, exp, sin, cos, tan, factorial, the constants
        pi and e, and custom constants referred to by NAME (their values are
        resolved automatically; never substitute a constant's value yourself).
        Example: "( 3 + 4 ) ** 2 / 7" or "sqrt(X1 + 2)".
        """
        logger.info("Evaluating expression: %s", expression)
        try:
            result = await evaluator.evaluate(expression)
        except (ValueError, UpstreamServiceError) as exc:
            return f"Error: {exc}"
        return str(result)

    return [evaluate_expression]
