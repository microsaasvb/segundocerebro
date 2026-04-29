"""Smoke tests for the CLI."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from lpm_kernel.connectors.llm_history import cli


def test_summary_prints_event_count(
    tmp_path: Path,
    chatgpt_export_zip: bytes,
    tenant_id: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    export = tmp_path / "export.zip"
    export.write_bytes(chatgpt_export_zip)
    rc = cli.main(
        [
            "--type",
            "chatgpt",
            "--file",
            str(export),
            "--tenant-id",
            tenant_id,
            "summary",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "events:        2" in out
    assert "by role:" in out


def test_dump_writes_jsonl(
    tmp_path: Path,
    claude_export_zip: bytes,
    tenant_id: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    export = tmp_path / "export.zip"
    export.write_bytes(claude_export_zip)
    out_file = tmp_path / "events.jsonl"
    rc = cli.main(
        [
            "--type",
            "claude",
            "--file",
            str(export),
            "--tenant-id",
            tenant_id,
            "dump",
            "--out",
            str(out_file),
        ]
    )
    assert rc == 0
    lines = out_file.read_text().strip().splitlines()
    assert lines, "expected at least one event"
    import json

    for line in lines:
        rec = json.loads(line)
        assert rec["source_connector"] == "llm_history_claude"
        assert rec["tenant_id"] == tenant_id
