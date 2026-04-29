"""Connector Hub.

A connector is a plugin that ingests events from an external source
(WhatsApp, Gmail, Drive, ChatGPT export, …) and normalizes them into a
``CanonicalEvent`` for the Third Brain L0 layer.

To add a new connector, subclass :class:`BaseConnector`, register it in
:data:`CONNECTOR_REGISTRY` (or use the auto-discovery in
``connectors.registry``), declare a Pydantic ``config_schema``, and
implement at minimum :meth:`backfill` and :meth:`normalize`.
"""

from lpm_kernel.connectors.base import (
    BaseConnector,
    CanonicalEvent,
    ConnectorHealth,
    ConsentLevel,
    ParticipantRef,
)
from lpm_kernel.connectors.registry import CONNECTOR_REGISTRY, register_connector

__all__ = [
    "BaseConnector",
    "CanonicalEvent",
    "CONNECTOR_REGISTRY",
    "ConnectorHealth",
    "ConsentLevel",
    "ParticipantRef",
    "register_connector",
]
