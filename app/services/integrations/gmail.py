from __future__ import annotations

import base64
import uuid
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.http import get_http_client
from app.db.models.integration import IntegrationStatus, ProviderType
from app.services.integrations.base import BaseIntegrationService
from app.services.integrations.oauth import OAuthService
from app.services.integrations.registry import register_provider

if TYPE_CHECKING:
    from app.db.models.user import User

_settings = get_settings()

# Gmail API base URL
GMAIL_API_BASE = "https://www.googleapis.com/gmail/v1"

# Gmail OAuth endpoints
GMAIL_OAUTH_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailService(BaseIntegrationService):
    """Gmail integration service."""

    provider_type = "gmail"

    def __init__(self):
        if not _settings.google_client_id or not _settings.google_client_secret:
            raise ValueError("Google OAuth credentials not configured")

        self.oauth_service = OAuthService(
            provider_type="gmail",
            client_id=_settings.google_client_id,
            client_secret=_settings.google_client_secret,
            authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
            access_token_endpoint="https://oauth2.googleapis.com/token",
            refresh_token_endpoint="https://oauth2.googleapis.com/token",
            scopes=GMAIL_OAUTH_SCOPES,
        )

    async def execute(self, session: AsyncSession, integration_id: uuid.UUID, action: str, params: dict) -> Any:
        """Execute a Gmail action."""
        access_token = await self.oauth_service.get_valid_access_token(session, integration_id)

        actions = {
            "list_emails": self._list_emails,
            "get_email": self._get_email,
            "search": self._search_emails,
            "get_threads": self._get_threads,
        }

        if action not in actions:
            raise ValueError(f"Unknown action: {action}")

        return await actions[action](access_token, params)

    async def refresh_token(self, session: AsyncSession, integration_id: uuid.UUID) -> bool:
        """Refresh the access token."""
        try:
            await self.oauth_service.get_valid_access_token(session, integration_id)
            return True
        except Exception:
            return False

    async def _list_emails(self, access_token: str, params: dict) -> list[dict]:
        """List recent emails."""
        max_results = params.get("max_results", 10)
        query = params.get("query", "")

        headers = {"Authorization": f"Bearer {access_token}"}
        http_client = get_http_client()

        request_params = {"maxResults": max_results}
        if query:
            request_params["q"] = query

        response = await http_client.get(
            f"{GMAIL_API_BASE}/users/me/messages",
            headers=headers,
            params=request_params,
        )
        response.raise_for_status()

        data = response.json()
        messages = data.get("messages", [])

        # Fetch full details for each message
        emails = []
        for msg in messages[:max_results]:
            email = await self._get_email_details(access_token, msg["id"])
            if email:
                emails.append(email)

        return emails

    async def _get_email(self, access_token: str, params: dict) -> dict:
        """Get a specific email by ID."""
        message_id = params.get("message_id")
        if not message_id:
            raise ValueError("message_id is required")

        return await self._get_email_details(access_token, message_id)

    async def _search_emails(self, access_token: str, params: dict) -> list[dict]:
        """Search emails with a query."""
        return await self._list_emails(access_token, params)

    async def _get_threads(self, access_token: str, params: dict) -> dict:
        """Get a thread by ID."""
        thread_id = params.get("thread_id")
        if not thread_id:
            raise ValueError("thread_id is required")

        headers = {"Authorization": f"Bearer {access_token}"}
        http_client = get_http_client()

        response = await http_client.get(
            f"{GMAIL_API_BASE}/users/me/threads/{thread_id}",
            headers=headers,
        )
        response.raise_for_status()

        return response.json()

    async def _get_email_details(self, access_token: str, message_id: str) -> dict:
        """Get full email details."""
        headers = {"Authorization": f"Bearer {access_token}"}
        http_client = get_http_client()

        response = await http_client.get(
            f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
            headers=headers,
            params={"format": "full"},
        )
        response.raise_for_status()

        data = response.json()

        # Parse headers
        headers_dict = {}
        for header in data.get("payload", {}).get("headers", []):
            headers_dict[header["name"].lower()] = header["value"]

        # Get body
        body = self._get_body(data.get("payload", {}))

        return {
            "id": data.get("id"),
            "thread_id": data.get("threadId"),
            "subject": headers_dict.get("subject", ""),
            "from": headers_dict.get("from", ""),
            "to": headers_dict.get("to", ""),
            "date": headers_dict.get("date", ""),
            "snippet": data.get("snippet", ""),
            "body": body,
            "labels": data.get("labelIds", []),
        }

    def _get_body(self, payload: dict) -> str:
        """Extract body from message payload."""
        body_data = None

        # Check if this part has body data
        if "body" in payload and payload["body"].get("data"):
            body_data = payload["body"]["data"]
        elif "parts" in payload:
            # Recursively find text/plain or text/html
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain" and part.get("body", {}).get("data"):
                    body_data = part["body"]["data"]
                    break
                elif mime_type == "text/html" and part.get("body", {}).get("data"):
                    body_data = part["body"]["data"]

                # Check nested parts
                if "parts" in part:
                    nested_body = self._get_body(part)
                    if nested_body:
                        return nested_body

        if body_data:
            # Base64 decode
            try:
                decoded = base64.urlsafe_b64decode(body_data).decode("utf-8")
                return decoded
            except Exception:
                return ""

        return ""


# Register the provider
@register_provider("gmail")
def get_gmail_service():
    return GmailService()
