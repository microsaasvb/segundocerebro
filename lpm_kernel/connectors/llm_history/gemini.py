"""Gemini export parser (Google Takeout — "My Activity").

Format reference: takeout.google.com → "My Activity" → "Bard / Gemini
Apps" produces, for each conversation, a ``MyActivity.json`` file with
entries like::

    {
        "header": "Gemini Apps",
        "title": "Asked Gemini ...",
        "titleUrl": "https://gemini.google.com/...",
        "subtitles": [{"name": "...optional..."}],
        "details": [{"name": "From the Bard app"}],
        "time": "2025-04-29T13:21:11.117Z",
        "products": ["Gemini Apps"]
    }

Conversation reconstruction is messy — Takeout flattens user prompts
and Gemini responses into a single timeline. We yield one event per
entry; downstream L1 may group them into conversations using the
``titleUrl`` (which encodes the conversation id).

If the user hands us the raw Takeout ZIP, we recursively grab every
``MyActivity.json`` under any directory whose name contains "Gemini"
or "Bard".
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lpm_kernel.connectors.base import (
    BaseConnector,
    CanonicalEvent,
    ConnectorHealth,
    ConsentLevel,
    ParticipantRef,
)
from lpm_kernel.connectors.llm_history._common import iter_zip_members, open_export
from lpm_kernel.connectors.registry import register_connector

_USER_PREFIXES = (
    "Asked Gemini",
    "Asked Bard",
    "Used Gemini Apps",
    "Used Bard",
    "Used in Gemini Apps",
    "Pediu ao Gemini",  # pt-BR
    "Pediu ao Bard",
)


class GeminiHistoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_handle: str = Field(default="me")


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _strip_html(text: str) -> str:
    """Takeout titles for prompts are wrapped in HTML link tags. Drop them."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _convo_id_from_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    match = re.search(r"/app/([^/?#]+)", url)
    return match.group(1) if match else url


def _author_role(title: str) -> str:
    if any(title.startswith(p) for p in _USER_PREFIXES):
        return "user"
    return "assistant"


def _strip_prefix(title: str) -> str:
    for prefix in _USER_PREFIXES:
        if title.startswith(prefix):
            return title[len(prefix) :].lstrip(": ").strip()
    return title.strip()


@register_connector
class GeminiHistoryConnector(BaseConnector):
    """Parses Google Takeout's ``MyActivity.json`` for Gemini/Bard."""

    type = "llm_history_gemini"
    config_schema = GeminiHistoryConfig

    def __init__(self, *, tenant_id: UUID, config: BaseModel, source: str | Path | bytes | io.IOBase | None = None) -> None:
        super().__init__(tenant_id=tenant_id, config=config)
        self._source = source

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(healthy=self._source is not None, last_error=None if self._source else "no source loaded")

    def backfill(self, since: datetime | None = None) -> Iterator[CanonicalEvent]:
        if self._source is None:
            raise RuntimeError("GeminiHistoryConnector requires a `source` to backfill")
        for entry in self._iter_entries():
            event = self._build_event(entry)
            if event is None:
                continue
            if since and event.occurred_at < since:
                continue
            yield event

    def normalize(self, raw: dict[str, Any]) -> CanonicalEvent:  # pragma: no cover
        event = self._build_event(raw)
        if event is None:
            raise ValueError("entry produced no event (no text or unknown shape)")
        return event

    # ─── internals ───────────────────────────────────────────────────

    def _iter_entries(self) -> Iterator[dict[str, Any]]:
        import json

        data = open_export(self._source)  # type: ignore[arg-type]
        if not data.startswith(b"PK"):
            try:
                payload = json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = None
            if isinstance(payload, list):
                yield from payload
                return
        # ZIP — find every MyActivity.json under a Gemini/Bard folder.
        for name, contents in iter_zip_members(data, filename_endswith="MyActivity.json"):
            if not any(needle in name for needle in ("Gemini", "Bard")):
                continue
            try:
                inner = json.loads(contents)
            except json.JSONDecodeError:
                continue
            if isinstance(inner, list):
                yield from inner

    def _build_event(self, entry: dict[str, Any]) -> CanonicalEvent | None:
        title = entry.get("title") or ""
        if not title:
            return None
        text = _strip_html(_strip_prefix(title))
        if not text:
            return None

        occurred = _parse_iso(entry.get("time"))
        if occurred is None:
            return None

        role = _author_role(title)
        convo_id = _convo_id_from_url(entry.get("titleUrl")) or "unknown"

        if role == "user":
            participants = [
                ParticipantRef(handle=self.config.user_handle, handle_type="free_text", role="sender"),  # type: ignore[attr-defined]
                ParticipantRef(handle="gemini", handle_type="free_text", role="recipient"),
            ]
        else:
            participants = [
                ParticipantRef(handle="gemini", handle_type="free_text", role="sender"),
                ParticipantRef(handle=self.config.user_handle, handle_type="free_text", role="recipient"),  # type: ignore[attr-defined]
            ]

        return CanonicalEvent(
            tenant_id=self.tenant_id,
            source_connector=self.type,
            source_id=f"{convo_id}::{occurred.isoformat()}",
            occurred_at=occurred,
            participants=participants,
            content=text,
            mime_type="text/plain",
            consent_level=ConsentLevel.IMPLICIT,
            metadata={
                "conversation_id": convo_id,
                "title_url": entry.get("titleUrl"),
                "author_role": role,
                "products": entry.get("products") or [],
            },
        )
