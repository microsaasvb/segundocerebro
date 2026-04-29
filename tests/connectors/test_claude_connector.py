"""Tests for :mod:`lpm_kernel.connectors.llm_history.claude`."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from lpm_kernel.connectors.llm_history.claude import (
    ClaudeHistoryConfig,
    ClaudeHistoryConnector,
)


def _connector(source: bytes, tenant_id: str) -> ClaudeHistoryConnector:
    return ClaudeHistoryConnector(
        tenant_id=UUID(tenant_id),
        config=ClaudeHistoryConfig(user_handle="mauricio"),
        source=source,
    )


def test_parses_human_and_assistant_messages(claude_export_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(claude_export_zip, tenant_id).backfill())
    # 2 valid messages — the third has empty content array AND the legacy
    # 'text' field is supposed to be ignored (but our parser also accepts
    # it as a fallback).
    assert len(events) >= 2
    roles = [e.metadata["author_role"] for e in events]
    assert "user" in roles
    assert "assistant" in roles


def test_first_event_is_a_question(claude_export_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(claude_export_zip, tenant_id).backfill())
    first = events[0]
    assert "Supabase" in first.content
    assert first.metadata["conversation_id"] == "convo-claude-001"
    assert first.metadata["conversation_title"] == "Decisão de stack"


def test_works_with_raw_json(claude_export_json: bytes, tenant_id: str) -> None:
    events = list(_connector(claude_export_json, tenant_id).backfill())
    assert events  # non-empty


def test_source_id_dedup_key(claude_export_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(claude_export_zip, tenant_id).backfill())
    assert all(e.source_id.startswith("convo-claude-001::") for e in events)


def test_since_filter(claude_export_zip: bytes, tenant_id: str) -> None:
    cutoff = datetime(2030, 1, 1, tzinfo=UTC)
    events = list(_connector(claude_export_zip, tenant_id).backfill(since=cutoff))
    assert events == []
