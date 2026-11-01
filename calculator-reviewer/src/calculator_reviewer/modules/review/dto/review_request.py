from pydantic import BaseModel, Field

from calculator_reviewer.modules.review.dto.param_descriptor import ParamDescriptor


class ReviewRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    script: str = Field(min_length=1, max_length=10000)
    params: list[ParamDescriptor] = Field(default_factory=list)
