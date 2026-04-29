"""CLI for testing LLM history connectors locally.

Usage::

    python -m lpm_kernel.connectors.llm_history.cli summary \\
        --type chatgpt \\
        --file ~/Downloads/conversations.json \\
        --tenant-id 00000000-0000-0000-0000-000000000001

    python -m lpm_kernel.connectors.llm_history.cli dump \\
        --type claude \\
        --file ~/Downloads/data-claude.zip \\
        --tenant-id 00000000-0000-0000-0000-000000000001 \\
        --out events.jsonl

The CLI is intentionally dependency-light (stdlib + the connector
package) so it works before the rest of the SaaS plumbing is wired up.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import UUID

from lpm_kernel.connectors.llm_history.chatgpt import ChatGPTHistoryConfig, ChatGPTHistoryConnector
from lpm_kernel.connectors.llm_history.claude import ClaudeHistoryConfig, ClaudeHistoryConnector
from lpm_kernel.connectors.llm_history.gemini import GeminiHistoryConfig, GeminiHistoryConnector

CONNECTORS = {
    "chatgpt": (ChatGPTHistoryConnector, ChatGPTHistoryConfig),
    "claude": (ClaudeHistoryConnector, ClaudeHistoryConfig),
    "gemini": (GeminiHistoryConnector, GeminiHistoryConfig),
}


def _build(args: argparse.Namespace):
    connector_cls, config_cls = CONNECTORS[args.type]
    config = config_cls(user_handle=args.user_handle)
    return connector_cls(
        tenant_id=UUID(args.tenant_id),
        config=config,
        source=Path(args.file),
    )


def _summary(args: argparse.Namespace) -> int:
    connector = _build(args)
    by_role: Counter[str] = Counter()
    by_convo: Counter[str] = Counter()
    earliest: datetime | None = None
    latest: datetime | None = None
    char_total = 0
    n = 0
    for event in connector.backfill(since=None):
        n += 1
        char_total += len(event.content)
        role = (event.metadata or {}).get("author_role") or "?"
        by_role[role] += 1
        convo = (event.metadata or {}).get("conversation_id") or "?"
        by_convo[convo] += 1
        if earliest is None or event.occurred_at < earliest:
            earliest = event.occurred_at
        if latest is None or event.occurred_at > latest:
            latest = event.occurred_at

    print(f"events:        {n}")
    print(f"characters:    {char_total:,}")
    print(f"conversations: {len(by_convo)}")
    print(f"by role:       {dict(by_role)}")
    print(f"earliest:      {earliest.isoformat() if earliest else 'n/a'}")
    print(f"latest:        {latest.isoformat() if latest else 'n/a'}")
    return 0


def _dump(args: argparse.Namespace) -> int:
    connector = _build(args)
    out = Path(args.out)
    n = 0
    with out.open("w", encoding="utf-8") as fp:
        for event in connector.backfill(since=None):
            fp.write(event.model_dump_json())
            fp.write("\n")
            n += 1
    print(f"wrote {n} events to {out}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm_history")
    parser.add_argument("--type", choices=sorted(CONNECTORS.keys()), required=True)
    parser.add_argument("--file", required=True, help="Path to export ZIP or JSON")
    parser.add_argument("--tenant-id", required=True, help="UUID of the tenant ingesting the data")
    parser.add_argument("--user-handle", default="me", help="Handle attached to user-authored turns")

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("summary", help="Print stats without persisting")
    dump = sub.add_parser("dump", help="Write every event as JSONL to --out")
    dump.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "summary":
        return _summary(args)
    if args.cmd == "dump":
        return _dump(args)
    parser.error(f"unknown cmd: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
