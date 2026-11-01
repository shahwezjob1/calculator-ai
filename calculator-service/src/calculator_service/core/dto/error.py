from pydantic import BaseModel, Field

from calculator_service.core.dto.info import Info


class Error(BaseModel):
    error_code: str = Field(serialization_alias="errorCode")
    error_message: str = Field(serialization_alias="errorMessage")
    details: str | None = None
    additional_info: list[Info] = Field(default_factory=list, serialization_alias="additionalInfo")
