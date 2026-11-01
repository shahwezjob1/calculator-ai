from pydantic import BaseModel, Field


class ParamDescriptor(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=255)
