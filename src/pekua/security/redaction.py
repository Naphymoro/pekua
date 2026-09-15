"""Fail-closed secret redaction for structured logs and error reporting."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"
_SECRET_KEY = re.compile(
    r"authorization|api[-_]?key|access[-_]?token|refresh[-_]?token|client[-_]?secret|password|cookie|set-cookie",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_INLINE = re.compile(r"\b(api[_-]?key|token|password|secret)\s*[=:]\s*([^\s,;]+)", re.IGNORECASE)


def _redact_text(value: str) -> str:
    value = _BEARER.sub(f"Bearer {REDACTED}", value)
    return _INLINE.sub(lambda match: f"{match.group(1)}={REDACTED}", value)


def redact(value: Any, _seen: set[int] | None = None) -> Any:
    """Return a redacted copy suitable for logs. Cycles are never traversed."""
    seen = _seen if _seen is not None else set()
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, bytes):
        return REDACTED
    if value is None or isinstance(value, (int, float, bool)):
        return value
    identity = id(value)
    if identity in seen:
        return "[CIRCULAR]"
    seen.add(identity)
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _SECRET_KEY.search(str(key)) else redact(item, seen)
            for key, item in value.items()
        }
    if isinstance(value, Sequence):
        return [redact(item, seen) for item in value]
    return _redact_text(str(value))
