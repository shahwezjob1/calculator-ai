from langchain_core.tools import tool

from calculator_agent.core.clients.constants_api_client import ConstantsApiClient
from calculator_agent.core.clients.errors import UpstreamServiceError


def build_constant_tools(constants_client: ConstantsApiClient):
    @tool
    async def set_constant(name: str, value: float) -> str:
        """Create or update a custom constant (name -> numeric value). Use when the
        user defines a named number, e.g. "X1 stands for 5.5". Names must be
        snake_case identifiers and must not collide with built-in functions/constants."""
        try:
            constant = await constants_client.upsert(name, value)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"
        return f"Constant '{constant['name']}' set."

    @tool
    async def delete_constant(name: str) -> str:
        """Delete a custom constant by name. The system asks the user to confirm."""
        try:
            deleted = await constants_client.delete(name)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"
        return f"Constant '{name}' deleted." if deleted else f"Error: constant '{name}' not found."

    @tool
    async def search_constants(queries: list[str]) -> str:
        """Search custom constants by one or more name fragments in a single call.
        Returns matching NAMES only (never values; evaluate a constant to see its
        value). An empty string or "*" matches all constants."""
        try:
            results = await constants_client.bulk_search(queries)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"
        lines = []
        for entry in results:
            matches = ", ".join(entry["matches"]) or "(none)"
            lines.append(f"'{entry['query']}': {matches} (total {entry['total']})")
        return "\n".join(lines)

    return [set_constant, delete_constant, search_constants]
