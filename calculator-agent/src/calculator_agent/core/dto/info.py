from pydantic import BaseModel


class Info(BaseModel):
    property: str
    reason: str
