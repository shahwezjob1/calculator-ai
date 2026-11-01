from pydantic import BaseModel, Field


class BulkSearchRequest(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=10)
    size: int = Field(default=5, ge=1, le=20)


class ConstantSearchResult(BaseModel):
    query: str
    matches: list[str]
    total: int


class BulkSearchResponse(BaseModel):
    results: list[ConstantSearchResult]
