from typing import Literal

from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    type: Literal["SAFETY", "CORRECTNESS", "QUALITY"]
    message: str


class ReviewResponse(BaseModel):
    verdict: Literal["SAFE", "UNSAFE"]
    issues: list[ReviewIssue] = Field(default_factory=list)
    suggested_name: str | None = Field(default=None, serialization_alias="suggestedName")
    suggested_description: str | None = Field(default=None, serialization_alias="suggestedDescription")
    suggested_fixes: list[str] = Field(default_factory=list, serialization_alias="suggestedFixes")
