"""ChatGPT export parser.

Format reference: the official "Export data" download from
chat.openai.com produces a ZIP containing ``conversations.json``. Each
top-level entry represents a conversation with a ``mapping`` that is a
DAG of message nodes keyed by UUID. The conversation tree is walked by
following ``current_node`` back to the root.

This parser yields one :class:`CanonicalEvent` per turn (user *or*
assistant). The conversation id, title and root timestamps are kept in
``metadata``.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from datetime import UTC, datetime
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
from lpm_kernel.connectors.llm_history._common import (
    extract_text_parts,
    load_export_json,
)
from lpm_kernel.connectors.registry import register_connector


class ChatGPTHistoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_handle: str = Field(
        default="me",
        description="Handle attached to user-authored turns (used for entity resolution).",
    )
    include_system_messages: bool = Field(
        default=False,
        description="Include the hidden 'system' role messages (rarely useful).",
    )


@register_connector
class ChatGPTHistoryConnector(BaseConnector):
    """Parses the ChatGPT export ZIP / ``conversations.json``."""

    type = "llm_history_chatgpt"
    config_schema = ChatGPTHistoryConfig

    def __init__(self, *, tenant_id: UUID, config: BaseModel, source: str | Path | bytes | io.IOBase | None = None) -> None:
        super().__init__(tenant_id=tenant_id, config=config)
        self._source = source

    # ─── BaseConnector ───────────────────────────────────────────────

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(healthy=self._source is not None, last_error=None if self._source else "no source loaded")

    def backfill(self, since: datetime | None = None) -> Iterator[CanonicalEvent]:
        if self._source is None:
            raise RuntimeError("ChatGPTHistoryConnector requires a `source` to backfill")
        conversations = load_export_json(self._source, member="conversations.json")
        if not isinstance(conversations, list):
            raise ValueError("conversations.json must be a top-level JSON array")
        for convo in conversations:
            yield from self._iter_convo(convo, since=since)

    def normalize(self, raw: dict[str, Any]) -> CanonicalEvent:  # pragma: no cover - covered by backfill
        return self._build_event(raw["convo"], raw["node"])

    # ─── internals ───────────────────────────────────────────────────

    def _iter_convo(self, convo: dict[str, Any], *, since: datetime | None) -> Iterator[CanonicalEvent]:
        mapping: dict[str, dict[str, Any]] = convo.get("mapping") or {}
        if not mapping:
            return
        ordered_nodes = sorted(
            (n for n in mapping.values() if n.get("message")),
            key=lambda n: (n.get("message") or {}).get("create_time") or 0,
        )
        for node in ordered_nodes:
            event = self._build_event(convo, node)
            if event is None:
                continue
            if since and event.occurred_at < since:
                continue
            yield event

    def _build_event(self, convo: dict[str, Any], node: dict[str, Any]) -> CanonicalEvent | None:
        msg = node.get("message") or {}
        author = (msg.get("author") or {}).get("role")
        if author == "system" and not self.config.include_system_messages:  # type: ignore[attr-defined]
            return None
        if author == "tool":
            return None
        content_obj = msg.get("content") or {}
        text = extract_text_parts(content_obj.get("parts"))
        if not text:
            return None

        ts = msg.get("create_time") or convo.get("create_time") or 0
        occurred = datetime.fromtimestamp(float(ts), tz=UTC) if ts else datetime.now(UTC)

        if author == "user":
            participants = [
                ParticipantRef(handle=self.config.user_handle, handle_type="free_text", role="sender"),  # type: ignore[attr-defined]
                ParticipantRef(handle="chatgpt", handle_type="free_text", role="recipient"),
            ]
        else:
            participants = [
                ParticipantRef(handle="chatgpt", handle_type="free_text", role="sender"),
                ParticipantRef(handle=self.config.user_handle, handle_type="free_text", role="recipient"),  # type: ignore[attr-defined]
            ]

        return CanonicalEvent(
            tenant_id=self.tenant_id,
            source_connector=self.type,
            source_id=f"{convo.get('conversation_id') or convo.get('id')}::{node.get('id') or msg.get('id')}",
            occurred_at=occurred,
            participants=participants,
            content=text,
            mime_type="text/plain",
            consent_level=ConsentLevel.IMPLICIT,
            metadata={
                "conversation_id": convo.get("conversation_id") or convo.get("id"),
                "conversation_title": convo.get("title"),
                "author_role": author,
                "model": (msg.get("metadata") or {}).get("model_slug"),
            },
        )
