from datetime import datetime

from pydantic import BaseModel, Field

from calculator_service.core.entities.custom_calculation import CustomCalculation
from calculator_service.modules.calculations.dto.param_descriptor import ParamDescriptor


class CalculationResponse(BaseModel):
    name: str
    description: str
    script: str
    params: list[ParamDescriptor]
    review_status: str = Field(serialization_alias="reviewStatus")
    review_notes: dict | None = Field(default=None, serialization_alias="reviewNotes")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    @classmethod
    def from_entity(cls, entity: CustomCalculation) -> "CalculationResponse":
        return cls(
            name=entity.name,
            description=entity.description,
            script=entity.script,
            params=[ParamDescriptor(**p) for p in entity.params],
            review_status=entity.review_status,
            review_notes=entity.review_notes,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
