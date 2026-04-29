"""Tests for :mod:`lpm_kernel.connectors.llm_history.gemini`."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from lpm_kernel.connectors.llm_history.gemini import (
    GeminiHistoryConfig,
    GeminiHistoryConnector,
)


def _connector(source: bytes, tenant_id: str) -> GeminiHistoryConnector:
    return GeminiHistoryConnector(
        tenant_id=UUID(tenant_id),
        config=GeminiHistoryConfig(user_handle="mauricio"),
        source=source,
    )


def test_parses_my_activity_zip(gemini_takeout_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(gemini_takeout_zip, tenant_id).backfill())
    assert len(events) == 3


def test_distinguishes_user_vs_assistant(gemini_takeout_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(gemini_takeout_zip, tenant_id).backfill())
    by_role = {e.metadata["author_role"]: e for e in events if "embeddings" in e.content or "BGE" in e.content}
    assert "user" in by_role
    assert "assistant" in by_role
    assert "BGE" in by_role["assistant"].content


def test_strips_html_from_titles(gemini_takeout_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(gemini_takeout_zip, tenant_id).backfill())
    matches = [e for e in events if "inverter dict" in e.content]
    assert matches, "should have parsed the HTML-wrapped title"
    assert "<a" not in matches[0].content
    assert "href" not in matches[0].content


def test_groups_by_conversation_url(gemini_takeout_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(gemini_takeout_zip, tenant_id).backfill())
    convos = {e.metadata["conversation_id"] for e in events}
    assert convos == {"abc123", "xyz789"}


def test_since_filter(gemini_takeout_zip: bytes, tenant_id: str) -> None:
    events = list(
        _connector(gemini_takeout_zip, tenant_id).backfill(
            since=datetime(2026, 4, 30, tzinfo=UTC)
        )
    )
    assert all(e.occurred_at >= datetime(2026, 4, 30, tzinfo=UTC) for e in events)
    assert len(events) == 1
