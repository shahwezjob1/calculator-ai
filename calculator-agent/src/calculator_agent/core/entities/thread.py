from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Thread:
    id: UUID
    thread_id: UUID
    thread_name: str
    created_at: datetime
