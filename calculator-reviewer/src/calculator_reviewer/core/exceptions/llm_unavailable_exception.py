from calculator_reviewer.core.constants import LLM_UNAVAILABLE_ERROR_CODE
from calculator_reviewer.core.exceptions.reviewer_exception import ReviewerException


class LlmUnavailableException(ReviewerException):
    def __init__(self, message: str, details: str | None = None):
        super().__init__(LLM_UNAVAILABLE_ERROR_CODE, message, details)
