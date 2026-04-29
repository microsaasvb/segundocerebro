"""Claude export parser.

Format reference: anthropic.com → Settings → Account → Export Data.
The download is a ZIP containing ``conversations.json`` and
``users.json``. ``conversations.json`` is a list of objects with the
shape::

    {
        "uuid": "...",
        "name": "Conversation title",
        "created_at": "2025-04-29T...Z",
        "updated_at": "...",
        "chat_messages": [
            {
                "uuid": "...",
                "text": "(legacy)",
                "content": [{"type": "text", "text": "..."}],
                "sender": "human" | "assistant",
                "created_at": "...",
                "attachments": [...],
                "files": [...]
            },
            ...
        ]
    }

This parser yields one :class:`CanonicalEvent` per ``chat_messages``
entry.
"""

from __future__ import annotations

import io
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
from lpm_kernel.connectors.llm_history._common import load_export_json
from lpm_kernel.connectors.registry import register_connector


class ClaudeHistoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_handle: str = Field(default="me")


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value))
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _flatten_content(message: dict[str, Any]) -> str:
    blocks = message.get("content")
    if isinstance(blocks, list):
        out: list[str] = []
        for block in blocks:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text = block.get("text") or ""
                    if text.strip():
                        out.append(text)
        joined = "\n".join(out).strip()
        if joined:
            return joined
    text = message.get("text")
    return text.strip() if isinstance(text, str) else ""


@register_connector
class ClaudeHistoryConnector(BaseConnector):
    """Parses the Claude.ai export ZIP / ``conversations.json``."""

    type = "llm_history_claude"
    config_schema = ClaudeHistoryConfig

    def __init__(self, *, tenant_id: UUID, config: BaseModel, source: str | Path | bytes | io.IOBase | None = None) -> None:
        super().__init__(tenant_id=tenant_id, config=config)
        self._source = source

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(healthy=self._source is not None, last_error=None if self._source else "no source loaded")

    def backfill(self, since: datetime | None = None) -> Iterator[CanonicalEvent]:
        if self._source is None:
            raise RuntimeError("ClaudeHistoryConnector requires a `source` to backfill")
        conversations = load_export_json(self._source, member="conversations.json")
        if not isinstance(conversations, list):
            raise ValueError("conversations.json must be a top-level JSON array")
        for convo in conversations:
            yield from self._iter_convo(convo, since=since)

    def normalize(self, raw: dict[str, Any]) -> CanonicalEvent:  # pragma: no cover
        return self._build_event(raw["convo"], raw["message"])

    def _iter_convo(self, convo: dict[str, Any], *, since: datetime | None) -> Iterator[CanonicalEvent]:
        for message in convo.get("chat_messages") or []:
            event = self._build_event(convo, message)
            if event is None:
                continue
            if since and event.occurred_at < since:
                continue
            yield event

    def _build_event(self, convo: dict[str, Any], message: dict[str, Any]) -> CanonicalEvent | None:
        text = _flatten_content(message)
        if not text:
            return None
        sender = message.get("sender") or "human"
        occurred = _parse_iso(message.get("created_at")) or _parse_iso(convo.get("created_at"))
        if occurred is None:
            return None

        if sender == "human":
            participants = [
                ParticipantRef(handle=self.config.user_handle, handle_type="free_text", role="sender"),  # type: ignore[attr-defined]
                ParticipantRef(handle="claude", handle_type="free_text", role="recipient"),
            ]
        else:
            participants = [
                ParticipantRef(handle="claude", handle_type="free_text", role="sender"),
                ParticipantRef(handle=self.config.user_handle, handle_type="free_text", role="recipient"),  # type: ignore[attr-defined]
            ]

        return CanonicalEvent(
            tenant_id=self.tenant_id,
            source_connector=self.type,
            source_id=f"{convo.get('uuid')}::{message.get('uuid')}",
            occurred_at=occurred,
            participants=participants,
            content=text,
            mime_type="text/plain",
            consent_level=ConsentLevel.IMPLICIT,
            metadata={
                "conversation_id": convo.get("uuid"),
                "conversation_title": convo.get("name"),
                "author_role": "user" if sender == "human" else "assistant",
                "attachments": [a.get("file_name") for a in (message.get("attachments") or []) if isinstance(a, dict)],
            },
        )
