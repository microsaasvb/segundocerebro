"""Persist LLM history exports as Documents.

Bridges the connector parsers (which yield ``CanonicalEvent``) into
the existing L0 schema (``documents`` table). One conversation becomes
one document; chunking/embedding is handled by the existing background
pipeline triggered when ``embedding_status = INITIALIZED``.

Single-user mode for now: every document is created without a
``user_id``/``tenant_id`` (those columns don't exist yet — Sprint 2 of
``docs/THIRD_BRAIN_PLAN.md`` adds them). When that lands, this service
will start passing ``g.tenant_id`` to ``DocumentService.create_document``.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from io import BytesIO
from typing import IO
from uuid import UUID, uuid5, NAMESPACE_DNS

from lpm_kernel.connectors.base import CanonicalEvent
from lpm_kernel.connectors.llm_history.chatgpt import ChatGPTHistoryConfig, ChatGPTHistoryConnector
from lpm_kernel.connectors.llm_history.claude import ClaudeHistoryConfig, ClaudeHistoryConnector
from lpm_kernel.connectors.llm_history.gemini import GeminiHistoryConfig, GeminiHistoryConnector
from lpm_kernel.file_data.document_dto import CreateDocumentRequest
from lpm_kernel.file_data.document_service import document_service
from lpm_kernel.file_data.process_status import ProcessStatus

logger = logging.getLogger(__name__)


SUPPORTED_PROVIDERS = ("chatgpt", "claude", "gemini")
PROVIDER_LABELS = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "gemini": "Gemini",
}

# Stable namespace so the same export uploaded twice yields the same
# synthetic tenant uuid (used as a placeholder until multi-tenant ships).
_SINGLE_TENANT_PLACEHOLDER = uuid5(NAMESPACE_DNS, "segundocerebro.single-tenant")


@dataclass
class ImportSummary:
    provider: str
    total_events: int = 0
    user_events: int = 0
    assistant_events: int = 0
    conversations: int = 0
    documents_created: int = 0
    earliest: str | None = None
    latest: str | None = None
    skipped_empty: int = 0
    document_ids: list[int] = field(default_factory=list)


# ─── public API ──────────────────────────────────────────────────────────────


def import_llm_history(*, provider: str, payload: bytes | IO[bytes], user_handle: str = "me") -> ImportSummary:
    """Parse an LLM history export and persist each conversation as a Document.

    Returns an :class:`ImportSummary` describing what was ingested.
    """
    provider_normalized = provider.lower().strip()
    if provider_normalized not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider {provider!r} (use one of {SUPPORTED_PROVIDERS})")

    raw = payload.read() if hasattr(payload, "read") else payload
    if not raw:
        raise ValueError("empty payload")

    events = list(_parse(provider_normalized, raw, user_handle))
    summary = _summarize(provider_normalized, events)
    summary.document_ids = _persist(provider_normalized, events)
    summary.documents_created = len(summary.document_ids)
    return summary


# ─── internals ───────────────────────────────────────────────────────────────


def _parse(provider: str, raw: bytes, user_handle: str) -> Iterable[CanonicalEvent]:
    if provider == "chatgpt":
        connector = ChatGPTHistoryConnector(
            tenant_id=_SINGLE_TENANT_PLACEHOLDER,
            config=ChatGPTHistoryConfig(user_handle=user_handle),
            source=raw,
        )
    elif provider == "claude":
        connector = ClaudeHistoryConnector(
            tenant_id=_SINGLE_TENANT_PLACEHOLDER,
            config=ClaudeHistoryConfig(user_handle=user_handle),
            source=raw,
        )
    else:
        connector = GeminiHistoryConnector(
            tenant_id=_SINGLE_TENANT_PLACEHOLDER,
            config=GeminiHistoryConfig(user_handle=user_handle),
            source=raw,
        )
    yield from connector.backfill()


def _summarize(provider: str, events: list[CanonicalEvent]) -> ImportSummary:
    summary = ImportSummary(provider=provider, total_events=len(events))
    convo_ids: set[str] = set()
    for ev in events:
        role = (ev.metadata or {}).get("author_role")
        if role == "user":
            summary.user_events += 1
        elif role == "assistant":
            summary.assistant_events += 1
        cid = (ev.metadata or {}).get("conversation_id")
        if cid:
            convo_ids.add(str(cid))
        ts = ev.occurred_at.isoformat() if ev.occurred_at else None
        if ts:
            if summary.earliest is None or ts < summary.earliest:
                summary.earliest = ts
            if summary.latest is None or ts > summary.latest:
                summary.latest = ts
    summary.conversations = len(convo_ids)
    return summary


def _persist(provider: str, events: list[CanonicalEvent]) -> list[int]:
    grouped: dict[str, list[CanonicalEvent]] = defaultdict(list)
    untitled: dict[str, str | None] = {}
    for ev in events:
        cid = (ev.metadata or {}).get("conversation_id") or "unknown"
        grouped[cid].append(ev)
        if cid not in untitled:
            untitled[cid] = (ev.metadata or {}).get("conversation_title")

    label = PROVIDER_LABELS[provider]
    created: list[int] = []
    for cid, convo_events in grouped.items():
        title = untitled.get(cid) or _guess_title(convo_events)
        markdown = _format_conversation(convo_events)
        if not markdown.strip():
            continue
        safe_name = _safe_filename(f"[{label}] {title or cid}.md")
        request = CreateDocumentRequest(
            user_description=f"Imported from {label} export",
            mime_type="text/markdown",
            document_size=len(markdown.encode("utf-8")),
            name=safe_name,
            title=title or cid,
            url="",
            raw_content=markdown,
            extract_status=ProcessStatus.SUCCESS,
            embedding_status=ProcessStatus.INITIALIZED,
            analyze_status=ProcessStatus.INITIALIZED,
        )
        try:
            doc = document_service.create_document(request)
        except Exception:  # noqa: BLE001 — keep going so a single bad convo doesn't kill the import
            logger.exception("failed to persist conversation %s from %s", cid, provider)
            continue
        if doc and doc.id is not None:
            created.append(doc.id)
    return created


def _format_conversation(events: list[CanonicalEvent]) -> str:
    lines: list[str] = []
    for ev in sorted(events, key=lambda e: e.occurred_at):
        role = (ev.metadata or {}).get("author_role") or "?"
        ts = ev.occurred_at.isoformat() if ev.occurred_at else ""
        speaker = "User" if role == "user" else ("Assistant" if role == "assistant" else role.title())
        lines.append(f"### {speaker} — {ts}\n\n{ev.content}\n")
    return "\n".join(lines)


def _guess_title(events: list[CanonicalEvent]) -> str | None:
    for ev in events:
        if (ev.metadata or {}).get("author_role") == "user" and ev.content:
            head = ev.content.strip().splitlines()[0]
            return head[:100]
    return None


_FILENAME_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _safe_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    cleaned = _FILENAME_FORBIDDEN.sub("_", normalized).strip()
    return cleaned[:255] or "import.md"
