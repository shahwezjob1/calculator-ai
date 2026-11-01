import math
import re
import asyncio

from calculator_agent.core.clients.constants_api_client import ConstantsApiClient

MAX_EXPRESSION_LENGTH = 500
MAX_TOKENS = 50
EXPONENT_CAP = 10000
FACTORIAL_CAP = 170
EVALUATION_TIMEOUT_SECONDS = 0.5

NUMBER_RE = re.compile(r"^\d+(\.\d+)?([eE][+-]?\d+)?$")
OPERATORS = {"+", "-", "*", "/", "//", "%", "**"}
STRUCTURAL = {"(", ")", ","}
FUNCTIONS = {
    "sqrt": math.sqrt, "abs": abs, "round": round, "log": math.log, "log10": math.log10,
    "exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan, "factorial": math.factorial,
}
CONSTANTS = {"pi": math.pi, "e": math.e}

_OPERATOR_CHARS = set("+-*/%")
_OPERAND_CHARS = set("0123456789._abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


def lex(expression: str) -> list[str]:
    tokens: list[str] = []
    i, n, depth = 0, len(expression), 0
    while i < n:
        ch = expression[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "(),":
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    raise ValueError("Unbalanced parentheses in expression")
            tokens.append(ch)
            i += 1
            continue
        if ch in _OPERATOR_CHARS:
            # two-char operators: ** and //
            if ch in "*/" and i + 1 < n and expression[i + 1] == ch:
                tokens.append(ch * 2)
                i += 2
            else:
                tokens.append(ch)
                i += 1
            continue
        if ch in _OPERAND_CHARS:
            j = i
            while j < n:
                cj = expression[j]
                if cj in _OPERAND_CHARS:
                    j += 1
                    continue
                # scientific notation: sign directly after a trailing e/E of a number
                if cj in "+-" and j > i and expression[j - 1] in "eE" and expression[i].isdigit():
                    j += 1
                    continue
                break
            tokens.append(expression[i:j])
            i = j
            continue
        raise ValueError(f"Invalid token in expression: '{ch}'")
    if depth != 0:
        raise ValueError("Unbalanced parentheses in expression")
    return tokens


class ExpressionEvaluator:
    """The agent's single calculator. Safety is layered: the token whitelist means the
    joined string can only contain numbers, arithmetic operators, parens/commas, and
    exact whitelisted names; the controlled namespace means those names resolve only to
    injected functions and constant values; '.' is never a valid standalone token, so
    attribute access is impossible."""

    def __init__(self, constants_client: ConstantsApiClient | None):
        self._constants_client = constants_client

    async def evaluate(self, expression: str) -> float:
        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise ValueError(f"Expression too long (max {MAX_EXPRESSION_LENGTH} chars)")
        tokens = lex(expression)
        if not tokens:
            raise ValueError("Empty expression")
        if len(tokens) > MAX_TOKENS:
            raise ValueError(f"Too many tokens: {len(tokens)} (max {MAX_TOKENS})")

        # Custom constant values come fresh from the service at every evaluation.
        custom = await self._constants_client.values_map() if self._constants_client else {}

        for token in tokens:
            if token in OPERATORS or token in STRUCTURAL:
                continue
            if NUMBER_RE.match(token):
                continue
            if token in FUNCTIONS or token in CONSTANTS or token in custom:
                continue
            raise ValueError(f"Invalid token in expression: '{token}'")

        # Literal guards against runaway compute.
        for idx, token in enumerate(tokens):
            if token == "**" and idx + 1 < len(tokens):
                nxt = tokens[idx + 1]
                if NUMBER_RE.match(nxt) and float(nxt) > EXPONENT_CAP:
                    raise ValueError(f"Exponent too large (max {EXPONENT_CAP})")
            if token == "factorial" and idx + 2 < len(tokens):
                arg = tokens[idx + 2]
                if NUMBER_RE.match(arg) and float(arg) > FACTORIAL_CAP:
                    raise ValueError(f"factorial argument too large (max {FACTORIAL_CAP})")

        namespace = {**FUNCTIONS, **CONSTANTS, **custom}
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    eval,
                    " ".join(tokens),
                    {"__builtins__": {}},
                    namespace,
                ),
                timeout=EVALUATION_TIMEOUT_SECONDS,
            )  # noqa: S307 - safe by token whitelist
        except TimeoutError:
            raise ValueError("Evaluation timed out after 500 ms") from None
        except ZeroDivisionError:
            raise ValueError("Division by zero")
        except Exception as exc:
            raise ValueError(f"Evaluation failed: {type(exc).__name__}: {exc}")
        if isinstance(result, bool) or not isinstance(result, (int, float)):
            raise ValueError("Expression did not produce a number")
        result = float(result)
        if not math.isfinite(result):
            raise ValueError("Result is not a finite number")
        # Normalize float noise (0.30000000000000004 -> 0.3).
        return float(f"{result:.12g}")
