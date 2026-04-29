"""Connector registry + auto-discovery."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from lpm_kernel.connectors.base import BaseConnector

CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {}


def register_connector(cls: type[BaseConnector]) -> type[BaseConnector]:
    """Decorator: register a connector subclass under its ``type``."""
    if not cls.type:
        raise ValueError(f"{cls.__name__} must define `type` to be registered")
    if cls.type in CONNECTOR_REGISTRY:
        raise ValueError(f"connector type already registered: {cls.type}")
    CONNECTOR_REGISTRY[cls.type] = cls
    return cls


def autodiscover() -> None:
    """Import every submodule under ``lpm_kernel.connectors`` so that
    ``@register_connector`` decorators run.
    """
    import lpm_kernel.connectors as pkg

    for module_info in pkgutil.iter_modules(pkg.__path__, prefix=f"{pkg.__name__}."):
        if module_info.name.endswith((".base", ".registry")):
            continue
        importlib.import_module(module_info.name)


def get_connector(type_: str) -> type[BaseConnector]:
    if type_ not in CONNECTOR_REGISTRY:
        autodiscover()
    if type_ not in CONNECTOR_REGISTRY:
        raise KeyError(f"unknown connector type: {type_}")
    return CONNECTOR_REGISTRY[type_]


def list_types() -> list[str]:
    autodiscover()
    return sorted(CONNECTOR_REGISTRY.keys())


def describe(type_: str) -> dict[str, Any]:
    cls = get_connector(type_)
    return {
        "type": cls.type,
        "config_schema": cls.config_schema.model_json_schema(),
        "doc": (cls.__doc__ or "").strip(),
    }
