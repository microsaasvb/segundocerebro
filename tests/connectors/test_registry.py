"""Registry behavior + that all 3 LLM-history connectors register."""

from __future__ import annotations

from lpm_kernel.connectors.registry import autodiscover, list_types


def test_llm_history_connectors_are_discovered() -> None:
    autodiscover()
    types = set(list_types())
    assert {
        "llm_history_chatgpt",
        "llm_history_claude",
        "llm_history_gemini",
    }.issubset(types)
