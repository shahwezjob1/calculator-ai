from pydantic import BaseModel

from calculator_service.core.dto.error import Error


class Errors(BaseModel):
    errors: list[Error]
