from pydantic import BaseModel, Field

from calculator_service.modules.calculations.dto.param_descriptor import ParamDescriptor


class CreateCalculationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    script: str = Field(min_length=1, max_length=10000)
    params: list[ParamDescriptor] = Field(default_factory=list, max_length=10)


class UpdateCalculationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, min_length=1, max_length=1024)
    script: str | None = Field(default=None, min_length=1, max_length=10000)
    params: list[ParamDescriptor] | None = Field(default=None, max_length=10)


class ExecuteCalculationRequest(BaseModel):
    params: dict[str, float] = Field(default_factory=dict)
