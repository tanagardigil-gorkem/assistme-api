from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.api.v1.deps import get_current_user
from app.db.models.integration import Integration, IntegrationStatus
from app.db.models.user import User
from app.db.session import get_async_session
from app.schemas.integration import (
    AvailableProviderResponse,
    ConnectRequest,
    ConnectResponse,
    ExecuteRequest,
    ExecuteResponse,
    IntegrationListResponse,
    IntegrationResponse,
)
from app.services.integrations.gmail import GmailService
from app.services.integrations.registry import (
    get_provider_service,
    list_available_providers,
)

if TYPE_CHECKING:
    pass

router = APIRouter()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


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
        )

        return ExecuteResponse(success=True, data=data)

    except Exception as e:
        return ExecuteResponse(success=False, error=str(e))
