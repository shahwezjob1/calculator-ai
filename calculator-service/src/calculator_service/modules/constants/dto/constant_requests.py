from pydantic import BaseModel


class UpsertConstantRequest(BaseModel):
    value: float
