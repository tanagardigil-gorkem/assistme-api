from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
