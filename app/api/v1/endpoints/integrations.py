from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.api.v1.deps import get_current_user
from app.db.models.integration import Integration, IntegrationStatus
from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.email import EmailListResponse, EmailResponse
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
from app.services.llm.email_summary import summarize_email

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
    summarize: bool = Query(default=True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List emails for an email integration with optional summaries."""
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

    config = integration.config or {}
    effective_query = config.get("query")
    if query is not None:
        effective_query = query
    effective_query = effective_query.strip() if isinstance(effective_query, str) else None
    if effective_query == "":
        effective_query = None

    effective_label_ids = config.get("label_ids")
    if label_ids is not None:
        effective_label_ids = label_ids or None

    effective_max_results = config.get("max_results")
    if max_results is not None:
        effective_max_results = max_results

    filter_key = filter_value or "all"
    filter_query = EMAIL_FILTERS.get(filter_key, "")
    query_parts = [part for part in [filter_query, effective_query] if part]
    combined_query = " ".join(query_parts) if query_parts else None

    params: dict = {}
    if combined_query:
        params["query"] = combined_query
    if effective_label_ids:
        params["label_ids"] = effective_label_ids
    if effective_max_results is not None:
        params["max_results"] = effective_max_results
    if page_token:
        params["page_token"] = page_token

    service = GmailService()
    try:
        emails, next_page_token = await service.list_emails_paginated(
            session=session,
            integration_id=integration_id,
            params=params,
        )
    except ValueError as exc:
        message = str(exc).lower()
        if "no refresh token" in message or "token expired" in message:
            integration.status = IntegrationStatus.EXPIRED
            await session.commit()
            raise HTTPException(
                status_code=400,
                detail="Integration expired. Please reconnect to refresh access.",
            ) from exc
        raise

    email_items = [EmailResponse.model_validate(email) for email in emails]

    if summarize:
        semaphore = asyncio.Semaphore(3)

        async def summarize_item(item: EmailResponse) -> EmailResponse:
            async with semaphore:
                summary = await summarize_email(item)
                return item.model_copy(update={"summary": summary})

        email_items = await asyncio.gather(
            *[summarize_item(item) for item in email_items]
        )

    return EmailListResponse(items=email_items, next_page_token=next_page_token)


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
