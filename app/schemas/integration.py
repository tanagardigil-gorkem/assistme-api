from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProviderType(str, Enum):
    GMAIL = "gmail"
    SLACK = "slack"
    NOTION = "notion"
    MICROSOFT = "microsoft"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class GmailConfig(BaseModel):
    query: str | None = Field(default=None, max_length=500)
    label_ids: list[str] | None = None
    max_results: int | None = Field(default=None, ge=1, le=100)


class IntegrationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IntegrationResponse(IntegrationBase):
    id: UUID
    provider_type: ProviderType
    status: IntegrationStatus
    config: dict | None
    created_at: datetime
    updated_at: datetime


class IntegrationListResponse(BaseModel):
    items: list[IntegrationResponse]


class AvailableProviderResponse(BaseModel):
    provider_type: str
    name: str
    description: str


class ConnectRequest(BaseModel):
    redirect_uri: str


class ConnectResponse(BaseModel):
    authorization_url: str
    state: str


class ExecuteRequest(BaseModel):
    action: str
    params: dict = Field(default_factory=dict)


class IntegrationUpdateRequest(BaseModel):
    status: IntegrationStatus | None = None
    config: GmailConfig | dict | None = None


class ExecuteResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None
