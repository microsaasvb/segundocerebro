"""Shared fixtures for connector tests."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tenant_id() -> str:
    return "00000000-0000-0000-0000-000000000001"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def chatgpt_export_json() -> bytes:
    return _read("chatgpt_conversations.json")


@pytest.fixture
def chatgpt_export_zip(chatgpt_export_json: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("conversations.json", chatgpt_export_json)
        zf.writestr("user.json", json.dumps({"name": "Test User"}))
    return buf.getvalue()


@pytest.fixture
def claude_export_json() -> bytes:
    return _read("claude_conversations.json")


@pytest.fixture
def claude_export_zip(claude_export_json: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("conversations.json", claude_export_json)
    return buf.getvalue()


@pytest.fixture
def gemini_takeout_zip() -> bytes:
    """Build a synthetic Takeout ZIP with a Gemini Apps MyActivity.json."""
    activity = json.loads(_read("gemini_my_activity.json"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "Takeout/My Activity/Gemini Apps/MyActivity.json",
            json.dumps(activity),
        )
    return buf.getvalue()
