import logging

import httpx

from calculator_service.core.constants import REVIEWER_UNAVAILABLE_ERROR_CODE
from calculator_service.core.exceptions.service_unavailable_exception import ServiceUnavailableException


class ReviewerApiClient:
    logger = logging.getLogger(__name__)

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def review(self, name: str, description: str, script: str, params: list[dict]) -> dict:
        self.logger.debug("Requesting review: name=%s", name)
        try:
            response = await self._client.post(
                "/api/v1/review",
                json={"name": name, "description": description, "script": script, "params": params},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ServiceUnavailableException(
                REVIEWER_UNAVAILABLE_ERROR_CODE,
                "Reviewer service call failed; calculation writes require a reachable reviewer",
            ) from exc
        return response.json()
