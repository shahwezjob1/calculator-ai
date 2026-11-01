from pydantic import BaseModel

from calculator_reviewer.core.dto.error import Error


class Errors(BaseModel):
    errors: list[Error]
