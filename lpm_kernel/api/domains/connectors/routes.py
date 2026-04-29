"""Connector HTTP endpoints."""

from __future__ import annotations

import logging
from dataclasses import asdict

from flask import Blueprint, jsonify, request

from lpm_kernel.api.common.responses import APIResponse
from lpm_kernel.api.domains.connectors.llm_history_service import (
    SUPPORTED_PROVIDERS,
    import_llm_history,
)

logger = logging.getLogger(__name__)

connectors_bp = Blueprint("connectors", __name__)


@connectors_bp.get("/api/connectors")
def list_connectors():
    """Return the static catalog of available connectors."""
    catalog = [
        {
            "type": "llm_history",
            "name": "LLM History",
            "description": "Import full history from ChatGPT, Claude or Gemini exports.",
            "providers": list(SUPPORTED_PROVIDERS),
            "ready": True,
            "category": "personal-data",
        },
        # Roadmap connectors — surfaced as cards but disabled.
        {"type": "gmail", "name": "Gmail", "description": "Email + threads via Gmail API.", "ready": False, "category": "communication"},
        {"type": "google_calendar", "name": "Google Calendar", "description": "Events + RSVP.", "ready": False, "category": "communication"},
        {"type": "google_drive", "name": "Google Drive", "description": "Documents + metadata.", "ready": False, "category": "files"},
        {"type": "dropbox", "name": "Dropbox", "description": "Files + change tracking.", "ready": False, "category": "files"},
        {"type": "beemeet", "name": "BeeMeet", "description": "Meeting transcripts + speakers.", "ready": False, "category": "voice"},
        {"type": "twilio", "name": "Twilio Voice", "description": "Call recordings + transcription.", "ready": False, "category": "voice"},
        {"type": "whatsapp", "name": "WhatsApp", "description": "Conversations via Evolution API.", "ready": False, "category": "communication"},
    ]
    return jsonify(APIResponse.success(data=catalog))


@connectors_bp.post("/api/connectors/llm-history/import")
def import_llm_history_endpoint():
    """Receive a ChatGPT/Claude/Gemini export and ingest it into L0.

    Multipart request:
      - ``provider``: 'chatgpt' | 'claude' | 'gemini'
      - ``user_handle`` (optional): handle used for the user-side participant
      - ``file``: the export ZIP or JSON
    """
    provider = (request.form.get("provider") or "").lower().strip()
    user_handle = request.form.get("user_handle") or "me"
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(APIResponse.error(code=400, message="missing file")), 400
    if provider not in SUPPORTED_PROVIDERS:
        return jsonify(APIResponse.error(code=400, message=f"unsupported provider; use one of {list(SUPPORTED_PROVIDERS)}")), 400

    try:
        summary = import_llm_history(
            provider=provider,
            payload=upload.read(),
            user_handle=user_handle,
        )
    except ValueError as exc:
        return jsonify(APIResponse.error(code=400, message=str(exc))), 400
    except Exception as exc:  # noqa: BLE001 — surface unexpected errors as 500
        logger.exception("LLM history import failed")
        return jsonify(APIResponse.error(code=500, message=f"import failed: {exc}")), 500

    return jsonify(APIResponse.success(data=asdict(summary)))
