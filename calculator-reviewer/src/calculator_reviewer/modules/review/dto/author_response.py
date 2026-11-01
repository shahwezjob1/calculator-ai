from pydantic import BaseModel, Field

from calculator_reviewer.modules.review.dto.param_descriptor import ParamDescriptor
from calculator_reviewer.modules.review.dto.review_response import ReviewResponse


class AuthorResponse(BaseModel):
    name: str
    description: str
    script: str
    params: list[ParamDescriptor] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    review: ReviewResponse
    iterations: int
