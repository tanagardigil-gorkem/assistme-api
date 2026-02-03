import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.deps import get_current_user
from app.db.models.integration import Integration, IntegrationStatus, ProviderType
from app.db.models.oauth_state import OAuthState
from app.db.models.user import User
from app.db.session import get_async_session
from app.main import create_app
from app.services.integrations.gmail import GMAIL_OAUTH_EXTRAS, GmailService


class _FakeResult:
    def __init__(self, record):
        self._record = record

    def scalar_one_or_none(self):
        return self._record

    def scalar_one(self):
        if self._record is None:
            raise ValueError("No rows returned")
        return self._record


class _FakeSession:
    def __init__(self, integration):
        self._integration = integration
        self.committed = False

    async def execute(self, *args, **kwargs):
        return _FakeResult(self._integration)

    async def commit(self):
        self.committed = True


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
async def test_list_emails_success_with_summary(monkeypatch):
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
    session = _FakeSession(integration)

    sample_email = {
        "id": "msg-1",
        "thread_id": "thread-1",
        "subject": "Hello",
        "from": "Sender <sender@example.com>",
        "to": "Me <me@example.com>",
        "date": "Wed, 3 Apr 2024 09:12:00 -0700",
        "snippet": "Quick update",
        "body": "Full body",
        "labels": ["INBOX"],
    }

    async def fake_list_emails(*args, **kwargs):
        return [sample_email], "next-token"

    async def fake_summarize(_email):
        return "Summary text"

    monkeypatch.setattr(GmailService, "list_emails_paginated", fake_list_emails)
    monkeypatch.setattr(
        "app.api.v1.endpoints.integrations.summarize_email",
        fake_summarize,
    )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/integrations/{integration.id}/emails")
        assert resp.status_code == 200
        body = resp.json()
        assert body["next_page_token"] == "next-token"
        assert body["items"][0]["summary"] == "Summary text"


@pytest.mark.asyncio
async def test_list_emails_summary_none(monkeypatch):
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
    session = _FakeSession(integration)

    async def fake_list_emails(*args, **kwargs):
        return [
            {
                "id": "msg-2",
                "thread_id": "thread-2",
                "subject": "Hello",
                "from": "Sender <sender@example.com>",
                "to": "Me <me@example.com>",
                "date": "Wed, 3 Apr 2024 09:12:00 -0700",
                "snippet": "Quick update",
                "body": "Full body",
                "labels": ["INBOX"],
            }
        ], None

    async def fake_summarize(_email):
        return None

    monkeypatch.setattr(GmailService, "list_emails_paginated", fake_list_emails)
    monkeypatch.setattr(
        "app.api.v1.endpoints.integrations.summarize_email",
        fake_summarize,
    )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/integrations/{integration.id}/emails")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"][0]["summary"] is None


@pytest.mark.asyncio
async def test_list_emails_provider_guard(monkeypatch):
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
    integration = _make_integration(ProviderType.NOTION, IntegrationStatus.ACTIVE, user.id)
    session = _FakeSession(integration)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/integrations/{integration.id}/emails")
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_emails_microsoft_not_implemented(monkeypatch):
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
    integration = _make_integration(ProviderType.MICROSOFT, IntegrationStatus.ACTIVE, user.id)
    session = _FakeSession(integration)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/integrations/{integration.id}/emails")
        assert resp.status_code == 501


@pytest.mark.asyncio
async def test_list_emails_filter_mapping(monkeypatch):
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
    session = _FakeSession(integration)
    captured = {}

    async def fake_list_emails(*args, **kwargs):
        captured["params"] = kwargs.get("params", {})
        return [], None

    monkeypatch.setattr(GmailService, "list_emails_paginated", fake_list_emails)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/integrations/{integration.id}/emails",
            params={
                "filter": "unread",
                "query": "from:test@example.com",
                "summarize": "false",
            },
        )
        assert resp.status_code == 200
        assert captured["params"]["query"] == "is:unread from:test@example.com"


@pytest.mark.asyncio
async def test_list_emails_expired_marks_status(monkeypatch):
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
    session = _FakeSession(integration)

    async def fake_list_emails(*args, **kwargs):
        raise ValueError("Token expired and no refresh token available")

    monkeypatch.setattr(GmailService, "list_emails_paginated", fake_list_emails)

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_async_session] = _override_session(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/integrations/{integration.id}/emails")
        assert resp.status_code == 400
        assert session.committed is True
        assert integration.status == IntegrationStatus.EXPIRED


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
