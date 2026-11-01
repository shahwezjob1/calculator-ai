from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int
    size: int
    total_items: int = Field(serialization_alias="totalItems")
    total_pages: int = Field(serialization_alias="totalPages")
