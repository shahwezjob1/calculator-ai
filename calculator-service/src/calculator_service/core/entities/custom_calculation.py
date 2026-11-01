from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class CustomCalculation:
    id: UUID
    name: str
    description: str
    script: str
    params: list[dict]
    review_status: str
    review_notes: dict | None
    created_at: datetime
    updated_at: datetime
