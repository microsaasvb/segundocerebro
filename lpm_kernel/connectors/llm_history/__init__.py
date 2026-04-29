"""LLM history connectors.

Parses the official export formats of ChatGPT, Claude and Gemini and
emits :class:`lpm_kernel.connectors.base.CanonicalEvent` records — one
per assistant turn — so years of conversations can be backfilled into
L0 in minutes.

Why this connector first? Highest ROI of the MVP:

* Zero legal risk (the user owns the export).
* Zero infra (just upload a ZIP).
* Captures cognitive context — *how the user thinks*, decisions,
  recurring topics — that no other source has.
"""

from lpm_kernel.connectors.llm_history.chatgpt import ChatGPTHistoryConnector
from lpm_kernel.connectors.llm_history.claude import ClaudeHistoryConnector
from lpm_kernel.connectors.llm_history.gemini import GeminiHistoryConnector

__all__ = [
    "ChatGPTHistoryConnector",
    "ClaudeHistoryConnector",
    "GeminiHistoryConnector",
]
