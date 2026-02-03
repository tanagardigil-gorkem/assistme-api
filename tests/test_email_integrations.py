import uuid
from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.deps import get_current_user
from app.db.models.integration import Integration, IntegrationStatus, ProviderType
from app.db.models.email_message import EmailMessage
from app.db.models.email_sync_state import EmailSyncState, EmailSyncStatus
from app.db.models.oauth_state import OAuthState
from app.db.models.user import User
from app.db.session import get_async_session
from app.main import create_app
from app.services.integrations.gmail import GMAIL_OAUTH_EXTRAS, GmailService


class _FakeResult:
    def __init__(self, record=None, items=None):
        self._record = record
        self._items = items or []

    def scalar_one_or_none(self):
        return self._record

    def scalar_one(self):
        if self._record is None:
            raise ValueError("No rows returned")
        return self._record

    def scalars(self):
        class _Scalars:
            def __init__(self, items):
                self._items = items

            def all(self):
                return list(self._items)

        return _Scalars(self._items)


class _FakeSession:
    def __init__(self, integration, sync_state, messages):
        self._integration = integration
        self._sync_state = sync_state
        self._messages = messages

    async def execute(self, stmt, *args, **kwargs):
        entity = stmt.column_descriptions[0].get("entity")
        if entity is Integration:
            return _FakeResult(record=self._integration)
        if entity is EmailSyncState:
            return _FakeResult(record=self._sync_state)
        if entity is EmailMessage:
            return _FakeResult(items=self._messages)
        return _FakeResult()

    async def commit(self):
        return None


def _make_integration(
    provider: ProviderType,
    status: IntegrationStatus,
    user_id: uuid.UUID,
) -> Integration:
    return Integration(
        id=uuid.uuid4(),
        user_id=user_id,
        provider_type=provider,
        status=status,
        config={},
    )


def _override_user(user: User):
    async def _override():
        return user

    return _override


def _override_session(session: _FakeSession):
    async def _override():
        yield session

    return _override


@pytest.mark.asyncio
async def test_cached_emails_response(monkeypatch):
    app = create_app()
    monkeypatch.setattr(GmailService, "__init__", lambda self: None)
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    integration = _make_integration(ProviderType.GMAIL, IntegrationStatus.ACTIVE, user.id)
    sync_state = EmailSyncState(
        integration_id=integration.id,
        status=EmailSyncStatus.IDLE,
        last_synced_at=datetime.utcnow(),
    )
    message = EmailMessage(
        integration_id=integration.id,
        provider_message_id="msg-1",
        thread_id="thread-1",
        from_address="Sender <sender@example.com>",
        to_address="Me <me@example.com>",
        subject="Hello",
        date="Wed, 3 Apr 2024 09:12:00 -0700",
        snippet="Quick update",
        body="Full body",
        labels=["INBOX"],
        summary="Summary text",
    )
    session = _FakeSession(integration, sync_state, [message])

    async def fake_enqueue(_integration_id):
        return None

    monkeypatch.setattr("app.api.v1.endpoints.integrations.enqueue_email_sync", fake_enqueue)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/integrations/{integration.id}/emails",
            params={"summaries": "true"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"][0]["summary"] == "Summary text"
        assert body["sync_status"] == "idle"

@pytest.mark.asyncio
async def test_refresh_triggers_sync(monkeypatch):
    app = create_app()
    monkeypatch.setattr(GmailService, "__init__", lambda self: None)
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    integration = _make_integration(ProviderType.GMAIL, IntegrationStatus.ACTIVE, user.id)
    sync_state = EmailSyncState(
        integration_id=integration.id,
        status=EmailSyncStatus.IDLE,
        last_synced_at=datetime.utcnow() - timedelta(minutes=10),
    )
    session = _FakeSession(integration, sync_state, [])
    called = {"value": False}

    async def fake_enqueue(_integration_id):
        called["value"] = True

    monkeypatch.setattr("app.api.v1.endpoints.integrations.enqueue_email_sync", fake_enqueue)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/integrations/{integration.id}/emails",
            params={"refresh": "true"},
        )
        assert resp.status_code == 200
        assert called["value"] is True


@pytest.mark.asyncio
async def test_connect_includes_oauth_extras(monkeypatch):
    app = create_app()
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    oauth_state = OAuthState(
        state="state-token",
        user_id=user.id,
        provider_type="gmail",
        redirect_uri="http://localhost:3000/email",
    )

    class _ConnectSession:
        async def execute(self, *args, **kwargs):
            return _FakeResult(oauth_state)

        async def commit(self):
            return None

    session = _ConnectSession()

    captured = {}

    class _FakeOAuth:
        async def get_authorization_url(self, **kwargs):
            captured.update(kwargs)
            return "https://example.com/oauth"

    class _FakeService:
        def __init__(self):
            self.oauth_service = _FakeOAuth()

    monkeypatch.setattr("app.api.v1.endpoints.integrations.GmailService", _FakeService)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/integrations/gmail/connect",
            json={"redirect_uri": "http://localhost:3000/email"},
        )
        assert resp.status_code == 200
        assert captured["extras_params"] == GMAIL_OAUTH_EXTRAS
