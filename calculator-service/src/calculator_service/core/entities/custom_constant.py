from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class CustomConstant:
    id: UUID
    name: str
    value: float
    created_at: datetime
    updated_at: datetime
