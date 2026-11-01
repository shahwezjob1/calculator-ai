import logging

import httpx

from calculator_agent.core.clients.errors import UpstreamServiceError, raise_for_response


class ReviewerApiClient:
    logger = logging.getLogger(__name__)

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def author(self, prompt: str, name: str | None = None,
                     params_hint: list[dict] | None = None, max_iterations: int = 3) -> dict:
        body: dict = {"prompt": prompt, "maxIterations": max_iterations}
        if name:
            body["name"] = name
        if params_hint:
            body["paramsHint"] = params_hint
        try:
            response = await self._client.post("/api/v1/author", json=body)
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"calculator-reviewer is unreachable: {type(exc).__name__}") from exc
        raise_for_response(response, "Authoring calculation script")
        return response.json()
