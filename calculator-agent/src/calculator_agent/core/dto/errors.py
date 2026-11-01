from pydantic import BaseModel

from calculator_agent.core.dto.error import Error


class Errors(BaseModel):
    errors: list[Error]
