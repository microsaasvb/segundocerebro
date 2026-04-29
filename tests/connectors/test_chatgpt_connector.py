"""Tests for :mod:`lpm_kernel.connectors.llm_history.chatgpt`."""

from __future__ import annotations

from uuid import UUID

import pytest

from lpm_kernel.connectors.llm_history.chatgpt import (
    ChatGPTHistoryConfig,
    ChatGPTHistoryConnector,
)


def _connector(source: bytes, tenant_id: str, *, include_system: bool = False) -> ChatGPTHistoryConnector:
    return ChatGPTHistoryConnector(
        tenant_id=UUID(tenant_id),
        config=ChatGPTHistoryConfig(user_handle="mauricio", include_system_messages=include_system),
        source=source,
    )


def test_parses_user_and_assistant_turns(chatgpt_export_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(chatgpt_export_zip, tenant_id).backfill())
    assert len(events) == 2

    user, assistant = events
    assert user.metadata["author_role"] == "user"
    assert "Como devo arquitetar" in user.content
    assert user.participants[0].handle == "mauricio"
    assert user.participants[1].handle == "chatgpt"

    assert assistant.metadata["author_role"] == "assistant"
    assert assistant.metadata["model"] == "gpt-4o"
    assert assistant.participants[0].handle == "chatgpt"


def test_skips_system_messages_by_default(chatgpt_export_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(chatgpt_export_zip, tenant_id).backfill())
    assert all(e.metadata["author_role"] != "system" for e in events)


def test_includes_system_when_requested(chatgpt_export_zip: bytes, tenant_id: str) -> None:
    events = list(_connector(chatgpt_export_zip, tenant_id, include_system=True).backfill())
    assert any(e.metadata["author_role"] == "system" for e in events)


def test_works_with_raw_json_not_zip(chatgpt_export_json: bytes, tenant_id: str) -> None:
    events = list(_connector(chatgpt_export_json, tenant_id).backfill())
    assert len(events) == 2


def test_source_id_is_idempotent(chatgpt_export_zip: bytes, tenant_id: str) -> None:
    first = list(_connector(chatgpt_export_zip, tenant_id).backfill())
    second = list(_connector(chatgpt_export_zip, tenant_id).backfill())
    assert [e.source_id for e in first] == [e.source_id for e in second]
    # source_id encodes conversation_id + node id → safe dedup key
    assert all("::" in e.source_id for e in first)


def test_since_filter_drops_older_events(chatgpt_export_zip: bytes, tenant_id: str) -> None:
    from datetime import UTC, datetime

    cutoff = datetime(2030, 1, 1, tzinfo=UTC)
    events = list(_connector(chatgpt_export_zip, tenant_id).backfill(since=cutoff))
    assert events == []


def test_health_reports_no_source() -> None:
    connector = ChatGPTHistoryConnector(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        config=ChatGPTHistoryConfig(),
    )
    health = connector.health()
    assert health.healthy is False


def test_invalid_top_level_payload(tenant_id: str) -> None:
    bad = b'{"not": "a list"}'
    with pytest.raises(ValueError, match="must be a top-level JSON array"):
        list(_connector(bad, tenant_id).backfill())
