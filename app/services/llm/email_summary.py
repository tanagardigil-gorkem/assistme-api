from __future__ import annotations

import inspect
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.schemas.email import EmailResponse


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    params = inspect.signature(ChatOpenAI.__init__).parameters
    kwargs: dict[str, object] = {"model": settings.openai_model}

    if "api_key" in params:
        kwargs["api_key"] = settings.openai_api_key
    elif "openai_api_key" in params:
        kwargs["openai_api_key"] = settings.openai_api_key

    if "timeout" in params:
        kwargs["timeout"] = settings.openai_timeout_s
    elif "request_timeout" in params:
        kwargs["request_timeout"] = settings.openai_timeout_s

    if "max_retries" in params:
        kwargs["max_retries"] = settings.openai_max_retries

    return ChatOpenAI(**kwargs)


async def summarize_email(email: EmailResponse) -> str | None:
    llm = get_llm()
    if llm is None:
        return None

    content = (email.body or "").strip() or (email.snippet or "").strip()
    if not content:
        return None

    system_prompt = (
        "You summarize emails into 1-2 concise sentences. "
        "Focus on the main request, decision, or next step. "
        "Do not include sensitive details or signatures."
    )
    human_prompt = (
        f"Subject: {email.subject or ''}\n"
        f"From: {email.from_ or ''}\n"
        f"To: {email.to or ''}\n"
        f"Date: {email.date or ''}\n\n"
        f"Email content:\n{content}"
    )

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ]
        )
    except Exception:
        return None

    summary = getattr(response, "content", None)
    if not summary:
        return None
    return str(summary).strip() or None
