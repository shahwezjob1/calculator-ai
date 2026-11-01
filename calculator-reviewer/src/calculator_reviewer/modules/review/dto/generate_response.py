from pydantic import BaseModel, Field

from calculator_reviewer.modules.review.dto.param_descriptor import ParamDescriptor


class GenerateResponse(BaseModel):
    name: str
    description: str
    script: str
    params: list[ParamDescriptor] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
