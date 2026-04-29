"""Helpers shared by the three LLM-history parsers."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def open_export(source: str | Path | bytes | io.IOBase) -> bytes:
    """Return raw bytes for ``source``.

    ``source`` can be:

    * a :class:`pathlib.Path` or :class:`str` path on disk;
    * raw ``bytes`` (already-loaded export);
    * a binary file-like object.
    """
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    if isinstance(source, bytes):
        return source
    if hasattr(source, "read"):
        data = source.read()
        return data if isinstance(data, bytes) else data.encode()
    raise TypeError(f"unsupported source type: {type(source).__name__}")


def iter_zip_members(data: bytes, *, filename_endswith: str) -> Iterator[tuple[str, bytes]]:
    """Yield ``(name, contents)`` for every file in ``data`` (a ZIP)
    whose name ends with ``filename_endswith``.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if info.filename.endswith(filename_endswith):
                with zf.open(info) as fp:
                    yield info.filename, fp.read()


def load_export_json(source: str | Path | bytes | io.IOBase, *, member: str) -> Any:
    """Load a single JSON file by name from a ZIP, OR load the source as
    JSON directly if it isn't a ZIP.

    Most exports ship as a ZIP that contains ``conversations.json``.
    Some users hand us the unzipped JSON directly — handle both.
    """
    data = open_export(source)
    if not data.startswith(b"PK"):
        # Not a ZIP — try plain JSON.
        try:
            return json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    for _, contents in iter_zip_members(data, filename_endswith=member):
        return json.loads(contents)
    raise ValueError(f"could not find {member!r} in source")


def extract_text_parts(parts: Any) -> str:
    """Walk ChatGPT-style ``content.parts`` (list of strings + dicts)
    and concatenate the textual pieces, dropping empty/None entries.
    """
    if parts is None:
        return ""
    if isinstance(parts, str):
        return parts.strip()
    out: list[str] = []
    if isinstance(parts, list):
        for p in parts:
            if isinstance(p, str):
                if p.strip():
                    out.append(p)
            elif isinstance(p, dict):
                # Newer ChatGPT exports nest text under various keys
                # depending on the message type (text, multimodal, code).
                for key in ("text", "transcript", "content"):
                    val = p.get(key)
                    if isinstance(val, str) and val.strip():
                        out.append(val)
                        break
    return "\n".join(out).strip()
