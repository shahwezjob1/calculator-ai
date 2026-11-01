import httpx


class UpstreamServiceError(Exception):
    """A downstream REST call failed; message is safe to surface to the LLM as a tool result."""

    def __init__(self, message: str, error_code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


def raise_for_response(response: httpx.Response, context: str) -> None:
    if response.is_success:
        return
    error_code, message = None, f"{context} failed with HTTP {response.status_code}"
    try:
        body = response.json()
        first = body["errors"][0]
        error_code = first.get("errorCode")
        message = first.get("errorMessage", message)
        if first.get("details"):
            message = f"{message} ({first['details']})"
    except Exception:
        pass
    raise UpstreamServiceError(message, error_code=error_code, status_code=response.status_code)
