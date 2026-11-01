from pydantic import BaseModel, Field


class ExecuteCalculationResponse(BaseModel):
    results: dict[str, float]
    duration_ms: float = Field(serialization_alias="durationMs")
