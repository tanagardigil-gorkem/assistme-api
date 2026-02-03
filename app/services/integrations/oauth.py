from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from httpx_oauth.oauth2 import OAuth2
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_token, encrypt_token
from app.db.models.integration import Integration, IntegrationStatus, ProviderType
from app.db.models.integration_token import IntegrationToken
from app.db.models.oauth_state import OAuthState

if TYPE_CHECKING:
    from app.db.models.user import User

_settings = get_settings()


class OAuthService:
    """Generic OAuth2 service for handling authorization flows."""

    def __init__(
        self,
        provider_type: str,
        client_id: str,
        client_secret: str,
        authorize_endpoint: str,
        access_token_endpoint: str,
        refresh_token_endpoint: str | None = None,
        scopes: list[str] | None = None,
    ):
        self.provider_type = provider_type
        self.scopes = scopes or []
        self.oauth_client = OAuth2(
            client_id=client_id,
            client_secret=client_secret,
            authorize_endpoint=authorize_endpoint,
            access_token_endpoint=access_token_endpoint,
            refresh_token_endpoint=refresh_token_endpoint,
        )

    async def get_authorization_url(
        self,
        session: AsyncSession,
        user: "User",
        redirect_uri: str,
        callback_url: str,
    ) -> str:
        """Generate OAuth authorization URL and store state."""
        import secrets

        # Generate random state
        state = secrets.token_urlsafe(32)

        # Store state in database (overwrites any existing state for this user/provider)
        oauth_state = OAuthState(
            state=state,
            user_id=user.id,
            provider_type=self.provider_type,
            redirect_uri=redirect_uri,
        )

        # Delete any existing state for this user/provider
        await session.execute(
            delete(OAuthState).where(
                OAuthState.user_id == user.id,
                OAuthState.provider_type == self.provider_type,
            )
        )

        session.add(oauth_state)
        await session.commit()

        # Generate authorization URL
        authorization_url = await self.oauth_client.get_authorization_url(
            redirect_uri=callback_url,
            scope=self.scopes,
            state=state,
        )

        return authorization_url

    async def handle_callback(
        self,
        session: AsyncSession,
        code: str,
        state: str,
        callback_url: str,
    ) -> tuple[Integration, str]:
        """Handle OAuth callback, exchange code for tokens, create integration."""
        # Verify state exists and is not expired
        result = await session.execute(select(OAuthState).where(OAuthState.state == state))
        oauth_state = result.scalar_one_or_none()

        if not oauth_state:
            raise ValueError("Invalid state parameter")

        if oauth_state.expires_at < datetime.utcnow():
            # Clean up expired state
            await session.execute(delete(OAuthState).where(OAuthState.state == state))
            await session.commit()
            raise ValueError("State has expired")

        # Exchange code for access token
        token_data = await self.oauth_client.get_access_token(code, callback_url)

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        # Calculate expiration time
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Create or update integration
        result = await session.execute(
            select(Integration).where(
                Integration.user_id == oauth_state.user_id,
                Integration.provider_type == ProviderType(self.provider_type),
            )
        )
        integration = result.scalar_one_or_none()

        if not integration:
            integration = Integration(
                user_id=oauth_state.user_id,
                provider_type=ProviderType(self.provider_type),
                status=IntegrationStatus.ACTIVE,
            )
            session.add(integration)
            await session.flush()  # Get integration.id

        # Encrypt tokens
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None

        # Store or update tokens
        result = await session.execute(
            select(IntegrationToken).where(
                IntegrationToken.integration_id == integration.id
            )
        )
        token_record = result.scalar_one_or_none()

        if token_record:
            token_record.access_token = encrypted_access
            token_record.refresh_token = encrypted_refresh
            token_record.expires_at = expires_at
        else:
            token_record = IntegrationToken(
                integration_id=integration.id,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                expires_at=expires_at,
            )
            session.add(token_record)

        # Clean up used state
        await session.execute(delete(OAuthState).where(OAuthState.state == state))
        await session.commit()

        return integration, oauth_state.redirect_uri

    async def get_valid_access_token(
        self,
        session: AsyncSession,
        integration_id: uuid.UUID,
    ) -> str:
        """Get valid access token, refreshing if necessary."""
        result = await session.execute(
            select(IntegrationToken).where(
                IntegrationToken.integration_id == integration_id
            )
        )
        token_record = result.scalar_one_or_none()

        if not token_record:
            raise ValueError("No tokens found for integration")

        # Check if token is expired or about to expire (5 min buffer)
        if token_record.expires_at and token_record.expires_at < datetime.utcnow() + timedelta(
            minutes=5
        ):
            if token_record.refresh_token:
                # Refresh the token
                new_token_data = await self.oauth_client.refresh_token(
                    decrypt_token(token_record.refresh_token)
                )

                # Update stored tokens
                token_record.access_token = encrypt_token(new_token_data["access_token"])
                if "refresh_token" in new_token_data:
                    token_record.refresh_token = encrypt_token(
                        new_token_data["refresh_token"]
                    )
                if "expires_in" in new_token_data:
                    token_record.expires_at = datetime.utcnow() + timedelta(
                        seconds=new_token_data["expires_in"]
                    )

                await session.commit()
            else:
                raise ValueError("Token expired and no refresh token available")

        return decrypt_token(token_record.access_token)
