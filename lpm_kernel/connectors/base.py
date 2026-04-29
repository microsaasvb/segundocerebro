"""Connector contract.

Every connector implements :class:`BaseConnector` and produces
:class:`CanonicalEvent` records that flow into L0.

Design notes:

* ``backfill`` is a one-shot historical sweep, used the first time a
  connector is enabled or after a manual "resync" action.
* ``poll`` is a periodic pull (e.g. Gmail ``history.list``).
* ``stream`` is a long-running subscription (e.g. WhatsApp webhook
  consumer that yields as messages arrive).
* ``health`` returns connector status for the dashboard.

Connectors should be **idempotent**: running ``backfill`` twice must
not duplicate events. The ``source_id`` field on ``CanonicalEvent`` is
the dedup key.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConsentLevel(str, Enum):
    """How sure are we the data subjects consented to this capture?"""

    EXPLICIT = "explicit"            # user marked this contact/group as consenting
    IMPLICIT = "implicit"            # 1:1 chat with the user, sender is the user
    AMBIENT = "ambient"              # captured passively (e.g. group chat)
    THIRD_PARTY = "third_party"      # someone else's content the user received


class ParticipantRef(BaseModel):
    """Reference to a person involved in an event.

    Resolved into the L1 entity graph by the entity-resolution stage.
    """

    model_config = ConfigDict(extra="forbid")

    handle: str                          # email, phone, username, etc.
    handle_type: str                     # 'email' | 'phone' | 'whatsapp_jid' | 'free_text'
    display_name: str | None = None
    role: str = "participant"            # 'sender' | 'recipient' | 'cc' | 'participant'


class CanonicalEvent(BaseModel):
    """A single event in L0, normalized across all connectors."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    source_connector: str                # e.g. 'gmail', 'whatsapp', 'llm_history_chatgpt'
    source_id: str                       # idempotency key inside the source
    occurred_at: datetime
    participants: list[ParticipantRef] = Field(default_factory=list)
    content: str                         # plain text (extracted from PDFs, transcribed audio…)
    mime_type: str = "text/plain"
    language: str | None = None          # ISO 639-1 ('pt', 'en', …) — detected per chunk
    consent_level: ConsentLevel = ConsentLevel.IMPLICIT
    raw_payload_uri: str | None = None   # pointer to Supabase Storage / local FS / source URL
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectorHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    healthy: bool
    last_sync_at: datetime | None = None
    last_error: str | None = None
    backlog_count: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class BaseConnector(ABC):
    """Subclass this to add a new ingestion source.

    Subclasses MUST set:

    * ``type``: short stable identifier (matches ``connectors.type`` row)
    * ``config_schema``: Pydantic model describing per-tenant config

    Subclasses MUST implement :meth:`backfill`, :meth:`normalize`,
    :meth:`health`. They MAY implement :meth:`poll` and/or :meth:`stream`.
    """

    type: str = ""
    config_schema: type[BaseModel] = BaseModel

    def __init__(self, *, tenant_id: UUID, config: BaseModel) -> None:
        if not self.type:
            raise TypeError(f"{type(self).__name__} must define a non-empty `type`")
        self.tenant_id = tenant_id
        self.config = config

    # ─── required ────────────────────────────────────────────────────

    @abstractmethod
    def health(self) -> ConnectorHealth: ...

    @abstractmethod
    def backfill(self, since: datetime | None = None) -> Iterator[CanonicalEvent]: ...

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> CanonicalEvent: ...

    # ─── optional ────────────────────────────────────────────────────

    def poll(self) -> Iterator[CanonicalEvent]:  # pragma: no cover - default no-op
        return iter(())

    def stream(self) -> Iterator[CanonicalEvent]:  # pragma: no cover - default no-op
        return iter(())
