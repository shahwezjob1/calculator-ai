from datetime import datetime

from pydantic import BaseModel, Field

from calculator_service.core.entities.custom_constant import CustomConstant


class ConstantResponse(BaseModel):
    name: str
    value: float
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    @classmethod
    def from_entity(cls, entity: CustomConstant) -> "ConstantResponse":
        return cls(name=entity.name, value=entity.value,
                   created_at=entity.created_at, updated_at=entity.updated_at)
