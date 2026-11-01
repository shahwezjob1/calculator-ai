from pydantic import BaseModel, ConfigDict, Field

from calculator_reviewer.modules.review.dto.param_descriptor import ParamDescriptor


class AuthorRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str = Field(min_length=1, max_length=2000)
    name: str | None = Field(default=None, max_length=64)
    params_hint: list[ParamDescriptor] | None = Field(default=None, alias="paramsHint")
    max_iterations: int = Field(default=3, ge=1, le=5, alias="maxIterations")
