from __future__ import annotations

import base64
from datetime import datetime, timedelta
import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.api.v1.deps import get_current_user
from app.db.models.email_message import EmailMessage
from app.db.models.email_sync_state import EmailSyncState
from app.db.models.integration import Integration, IntegrationStatus
from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.email import EmailListResponse, EmailResponse, EmailSyncStatus as EmailSyncStatusSchema
from app.schemas.integration import (
    AvailableProviderResponse,
    ConnectRequest,
    ConnectResponse,
    ExecuteRequest,
    ExecuteResponse,
    IntegrationUpdateRequest,
    IntegrationListResponse,
    IntegrationResponse,
)
from app.services.integrations.gmail import GMAIL_OAUTH_EXTRAS, GmailService
from app.services.integrations.registry import (
    get_provider_service,
    list_available_providers,
)
from app.services.email_sync import enqueue_email_sync
from app.core.config import get_settings

if TYPE_CHECKING:
    pass

router = APIRouter()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

EMAIL_PROVIDERS = {"gmail", "microsoft"}
EMAIL_FILTERS = {
    "all": "",
    "unread": "is:unread",
    "tasks": "label:tasks",
}


def _decode_page_token(token: str | None) -> int:
    if not token:
        return 0
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        return max(int(decoded), 0)
    except Exception:
        return 0


def _encode_page_token(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("utf-8")).decode("utf-8")


@router.get("/available", response_model=list[AvailableProviderResponse])
async def list_available():
    """List all available integration providers."""
    return list_available_providers()


@router.get("/", response_model=IntegrationListResponse)
async def list_integrations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List all integrations for the current user."""
    result = await session.execute(
        select(Integration).where(Integration.user_id == user.id)
    )
    integrations = result.scalars().all()

    return IntegrationListResponse(
        items=[IntegrationResponse.model_validate(i) for i in integrations]
    )


@router.get("/{integration_id}/emails", response_model=EmailListResponse)
@limiter.limit("30/minute")
async def list_emails(
    request: Request,
    integration_id: uuid.UUID,
    query: str | None = Query(default=None, max_length=500),
    filter_value: str | None = Query(default=None, alias="filter"),
    label_ids: list[str] | None = Query(default=None),
    max_results: int | None = Query(default=None, ge=1, le=100),
    page_token: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    summaries: bool = Query(default=True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List cached emails for an email integration and optionally trigger refresh."""
    result = await session.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user.id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    if integration.status != IntegrationStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Integration is not active")

    provider = integration.provider_type.value
    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=400, detail="Provider is not an email integration")
    if provider == "microsoft":
        raise HTTPException(status_code=501, detail="Provider not implemented")

    if filter_value and filter_value not in EMAIL_FILTERS:
        raise HTTPException(status_code=400, detail="Unknown filter")

    if "summarize" in request.query_params and "summaries" not in request.query_params:
        summaries = request.query_params.get("summarize", "true").lower() == "true"

    config = integration.config or {}
    effective_query = query if query is not None else config.get("query")
    effective_query = effective_query.strip() if isinstance(effective_query, str) else None
    if effective_query == "":
        effective_query = None

    effective_label_ids = label_ids if label_ids is not None else config.get("label_ids")
    effective_max_results = max_results if max_results is not None else config.get("max_results", 20)

    filter_key = filter_value or "all"
    if filter_key not in EMAIL_FILTERS:
        raise HTTPException(status_code=400, detail="Unknown filter")

    stmt = select(EmailMessage).where(EmailMessage.integration_id == integration_id)

    labels_column = cast(EmailMessage.labels, JSONB)

    if filter_key == "unread":
        stmt = stmt.where(labels_column.contains(["UNREAD"]))
    elif filter_key == "tasks":
        stmt = stmt.where(
            or_(
                labels_column.contains(["TASKS"]),
                labels_column.contains(["tasks"]),
            )
        )

    if effective_label_ids:
        label_filters = [labels_column.contains([label]) for label in effective_label_ids]
        stmt = stmt.where(or_(*label_filters))

    if effective_query:
        pattern = f"%{effective_query}%"
        stmt = stmt.where(
            or_(
                EmailMessage.subject.ilike(pattern),
                EmailMessage.from_address.ilike(pattern),
                EmailMessage.to_address.ilike(pattern),
                EmailMessage.snippet.ilike(pattern),
                EmailMessage.body.ilike(pattern),
            )
        )

    offset = _decode_page_token(page_token)
    limit = effective_max_results or 20
    stmt = (
        stmt.order_by(EmailMessage.date_ts.desc().nullslast(), EmailMessage.created_at.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    result = await session.execute(stmt)
    messages = result.scalars().all()

    has_more = len(messages) > limit
    messages = messages[:limit]
    next_page_token = _encode_page_token(offset + limit) if has_more else None

    sync_state_result = await session.execute(
        select(EmailSyncState).where(EmailSyncState.integration_id == integration_id)
    )
    sync_state = sync_state_result.scalar_one_or_none()

    settings = get_settings()
    now = datetime.utcnow()
    is_stale = True
    last_synced_at = None
    sync_status = EmailSyncStatusSchema.IDLE
    if sync_state:
        last_synced_at = sync_state.last_synced_at
        sync_status = EmailSyncStatusSchema(sync_state.status.value)
        if last_synced_at:
            is_stale = now - last_synced_at > timedelta(seconds=settings.email_sync_ttl_seconds)

    if refresh or is_stale:
        await enqueue_email_sync(integration_id)
        if not sync_state:
            sync_status = EmailSyncStatusSchema.SYNCING

    email_items = [
        EmailResponse(
            id=message.provider_message_id,
            thread_id=message.thread_id,
            subject=message.subject,
            from_=message.from_address,
            to=message.to_address,
            date=message.date,
            snippet=message.snippet,
            body=message.body,
            labels=message.labels or [],
            summary=message.summary if summaries else None,
        )
        for message in messages
    ]

    return EmailListResponse(
        items=email_items,
        next_page_token=next_page_token,
        sync_status=sync_status,
        last_synced_at=last_synced_at,
    )


@router.post("/{integration_id}/emails/sync")
@limiter.limit("10/minute")
async def sync_emails(
    request: Request,
    integration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Trigger a background email sync."""
    result = await session.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user.id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    if integration.status != IntegrationStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Integration is not active")

    provider = integration.provider_type.value
    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=400, detail="Provider is not an email integration")
    if provider == "microsoft":
        raise HTTPException(status_code=501, detail="Provider not implemented")

    await enqueue_email_sync(integration_id)
    return {"status": "queued"}


@router.post("/{provider}/connect", response_model=ConnectResponse)
@limiter.limit("5/minute")
async def connect_integration(
    request: Request,
    provider: str,
    connect_req: ConnectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Initiate OAuth connection for a provider."""
    if provider == "gmail":
        service = GmailService()
        auth_url = await service.oauth_service.get_authorization_url(
            session=session,
            user=user,
            redirect_uri=connect_req.redirect_uri,
            callback_url=request.app.state.settings.oauth_callback_url,
            extras_params=GMAIL_OAUTH_EXTRAS,
        )

        # Get the state from the stored OAuthState
        from app.db.models.oauth_state import OAuthState

        result = await session.execute(
            select(OAuthState)
            .where(OAuthState.user_id == user.id)
            .where(OAuthState.provider_type == provider)
            .order_by(OAuthState.created_at.desc())
        )
        oauth_state = result.scalar_one()

        return ConnectResponse(authorization_url=auth_url, state=oauth_state.state)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_async_session),
):
    """Handle OAuth callback from provider."""
    try:
        # Get provider type from state
        from app.db.models.oauth_state import OAuthState

        result = await session.execute(
            select(OAuthState).where(OAuthState.state == state)
        )
        oauth_state = result.scalar_one_or_none()

        if not oauth_state:
            raise HTTPException(status_code=400, detail="Invalid state")

        provider = oauth_state.provider_type

        if provider == "gmail":
            service = GmailService()
            integration, redirect_uri = await service.oauth_service.handle_callback(
                session=session,
                code=code,
                state=state,
                callback_url=request.app.state.settings.oauth_callback_url,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

        # Redirect back to frontend
        return RedirectResponse(url=redirect_uri)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")


@router.delete("/{integration_id}")
async def disconnect_integration(
    integration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Disconnect an integration."""
    result = await session.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user.id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    await session.delete(integration)
    await session.commit()

    return {"success": True}


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: uuid.UUID,
    update_req: IntegrationUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Update integration status or config."""
    result = await session.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user.id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    if update_req.status is not None:
        if update_req.status.value not in {
            IntegrationStatus.ACTIVE.value,
            IntegrationStatus.DISCONNECTED.value,
        }:
            raise HTTPException(
                status_code=400,
                detail="Only active or disconnected status are supported",
            )
        integration.status = IntegrationStatus(update_req.status.value)

    if update_req.config is not None:
        config_update = update_req.config
        if hasattr(config_update, "model_dump"):
            config_update = config_update.model_dump(exclude_none=True)
        elif isinstance(config_update, dict):
            config_update = {k: v for k, v in config_update.items() if v is not None}
        else:
            config_update = {}

        if config_update:
            existing_config = integration.config or {}
            integration.config = {**existing_config, **config_update}

    await session.commit()

    return IntegrationResponse.model_validate(integration)


@router.post("/{integration_id}/execute", response_model=ExecuteResponse)
@limiter.limit("30/minute")
async def execute_action(
    request: Request,
    integration_id: uuid.UUID,
    execute_req: ExecuteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Execute an action on an integration."""
    result = await session.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user.id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    if integration.status != IntegrationStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Integration is not active")

    try:
        service_class = get_provider_service(integration.provider_type.value)
        if not service_class:
            raise HTTPException(status_code=400, detail="Unknown provider type")

        service = service_class()
        data = await service.execute(
            session=session,
            integration_id=integration_id,
            action=execute_req.action,
            params=execute_req.params,
            integration_config=integration.config,
        )

        return ExecuteResponse(success=True, data=data)

    except Exception as e:
        return ExecuteResponse(success=False, error=str(e))
