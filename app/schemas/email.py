from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EmailSyncStatus(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"


class EmailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    thread_id: str | None = None
    subject: str | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    date: str | None = None
    snippet: str | None = None
    body: str | None = None
    labels: list[str] = Field(default_factory=list)
    summary: str | None = None


class EmailListResponse(BaseModel):
    items: list[EmailResponse]
    next_page_token: str | None = None
    sync_status: EmailSyncStatus | None = None
    last_synced_at: datetime | None = None
