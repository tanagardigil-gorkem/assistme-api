from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable

from sqlalchemy import select

from app.db.models.email_message import EmailMessage
from app.db.models.email_sync_state import EmailSyncState, EmailSyncStatus
from app.db.models.integration import Integration, IntegrationStatus
from app.db.session import async_session_maker
from app.schemas.email import EmailResponse
from app.services.integrations.gmail import GmailService
from app.services.llm.email_summary import summarize_email


SUMMARY_CONCURRENCY = 3


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip()
    if "<" in text and ">" in text:
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\s+", " ", text)
    return text.strip()


def _payload_hash(email: dict) -> str:
    payload = "|".join(
        [
            email.get("subject", "") or "",
            email.get("from", "") or "",
            email.get("to", "") or "",
            email.get("date", "") or "",
            email.get("snippet", "") or "",
            email.get("body", "") or "",
            ",".join(email.get("labels", []) or []),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_date(date_value: str | None) -> datetime | None:
    if not date_value:
        return None
    try:
        parsed = parsedate_to_datetime(date_value)
    except Exception:
        return None
    if parsed is None:
        return None
    if parsed.tzinfo:
        return parsed.astimezone(tz=None).replace(tzinfo=None)
    return parsed


async def enqueue_email_sync(integration_id: uuid.UUID) -> None:
    asyncio.create_task(sync_email_integration(integration_id))


async def sync_email_integration(integration_id: uuid.UUID) -> None:
    async with async_session_maker() as session:
        integration = await session.get(Integration, integration_id)
        if not integration:
            return
        if integration.status != IntegrationStatus.ACTIVE:
            return

        sync_state = await session.get(EmailSyncState, integration_id)
        if sync_state and sync_state.status == EmailSyncStatus.SYNCING:
            return
        if not sync_state:
            sync_state = EmailSyncState(integration_id=integration_id)
            session.add(sync_state)

        sync_state.status = EmailSyncStatus.SYNCING
        sync_state.error_message = None
        await session.commit()

        try:
            service = GmailService()
            config = integration.config or {}
            params = {}
            if config.get("query"):
                params["query"] = config.get("query")
            if config.get("label_ids"):
                params["label_ids"] = config.get("label_ids")
            params["max_results"] = config.get("max_results", 20)

            emails, next_page_token = await service.list_emails_paginated(
                session=session,
                integration_id=integration_id,
                params=params,
            )

            await _upsert_emails(session, integration_id, emails)

            sync_state.last_page_token = next_page_token
            sync_state.last_synced_at = datetime.utcnow()
            sync_state.status = EmailSyncStatus.IDLE
            await session.commit()

            await _generate_missing_summaries(integration_id)
        except ValueError as exc:
            message = str(exc).lower()
            if "no refresh token" in message or "token expired" in message:
                integration.status = IntegrationStatus.EXPIRED
            sync_state.status = EmailSyncStatus.ERROR
            sync_state.error_message = str(exc)[:500]
            await session.commit()
        except Exception as exc:
            sync_state.status = EmailSyncStatus.ERROR
            sync_state.error_message = str(exc)[:500]
            await session.commit()


async def _upsert_emails(
    session,
    integration_id: uuid.UUID,
    emails: Iterable[dict],
) -> None:
    email_list = list(emails)
    if not email_list:
        return

    message_ids = [email["id"] for email in email_list if email.get("id")]
    result = await session.execute(
        select(EmailMessage).where(
            EmailMessage.integration_id == integration_id,
            EmailMessage.provider_message_id.in_(message_ids),
        )
    )
    existing = {msg.provider_message_id: msg for msg in result.scalars().all()}

    for email in email_list:
        message_id = email.get("id")
        if not message_id:
            continue
        payload_hash = _payload_hash(email)
        existing_msg = existing.get(message_id)
        if not existing_msg:
            session.add(
                EmailMessage(
                    integration_id=integration_id,
                    provider_message_id=message_id,
                    thread_id=email.get("thread_id"),
                    from_address=email.get("from"),
                    to_address=email.get("to"),
                    subject=email.get("subject"),
                    date=email.get("date"),
                    date_ts=_parse_date(email.get("date")),
                    snippet=email.get("snippet"),
                    body=email.get("body"),
                    labels=email.get("labels") or [],
                    raw_payload_hash=payload_hash,
                )
            )
        else:
            existing_msg.thread_id = email.get("thread_id")
            existing_msg.from_address = email.get("from")
            existing_msg.to_address = email.get("to")
            existing_msg.subject = email.get("subject")
            existing_msg.date = email.get("date")
            existing_msg.date_ts = _parse_date(email.get("date"))
            existing_msg.snippet = email.get("snippet")
            existing_msg.body = email.get("body")
            existing_msg.labels = email.get("labels") or []
            if existing_msg.raw_payload_hash != payload_hash:
                existing_msg.raw_payload_hash = payload_hash
                existing_msg.summary = None
                existing_msg.summary_updated_at = None

    await session.commit()


async def _generate_missing_summaries(integration_id: uuid.UUID) -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(EmailMessage)
            .where(EmailMessage.integration_id == integration_id)
            .where(EmailMessage.summary.is_(None))
            .order_by(EmailMessage.date_ts.desc().nullslast(), EmailMessage.created_at.desc())
            .limit(50)
        )
        messages = result.scalars().all()
        if not messages:
            return

        semaphore = asyncio.Semaphore(SUMMARY_CONCURRENCY)

        async def summarize_and_update(message: EmailMessage) -> None:
            async with semaphore:
                email = EmailResponse(
                    id=message.provider_message_id,
                    thread_id=message.thread_id,
                    subject=message.subject,
                    from_=message.from_address,
                    to=message.to_address,
                    date=message.date,
                    snippet=_clean_text(message.snippet),
                    body=_clean_text(message.body),
                    labels=message.labels or [],
                )
                summary = await summarize_email(email)
                if summary:
                    message.summary = summary
                    message.summary_updated_at = datetime.utcnow()

        await asyncio.gather(*(summarize_and_update(msg) for msg in messages))
        await session.commit()
