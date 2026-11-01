from pydantic import BaseModel, Field


class CalculationBulkSearchRequest(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=10)
    size: int = Field(default=5, ge=1, le=20)


class CalculationSummary(BaseModel):
    name: str
    description: str


class CalculationSearchResult(BaseModel):
    query: str
    matches: list[CalculationSummary]
    total: int


class CalculationBulkSearchResponse(BaseModel):
    results: list[CalculationSearchResult]
