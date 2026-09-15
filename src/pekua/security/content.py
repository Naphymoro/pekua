"""Treat retrieved documents as data, never agent instructions."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from enum import StrEnum


class InjectionRisk(StrEnum):
    NONE = "none"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class ContentAssessment:
    risk: InjectionRisk
    signals: tuple[str, ...]

    @property
    def safe_for_model_context(self) -> bool:
        return self.risk is InjectionRisk.NONE


_SIGNALS: tuple[tuple[str, re.Pattern[str], InjectionRisk], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|override)\b.{0,60}\b(instruction|system|policy|developer)\b",
            re.I | re.S,
        ),
        InjectionRisk.BLOCK,
    ),
    (
        "credential_request",
        re.compile(
            r"\b(reveal|send|print|exfiltrate|upload)\b.{0,70}"
            r"\b(secret|token|password|credential|api key)\b",
            re.I | re.S,
        ),
        InjectionRisk.BLOCK,
    ),
    (
        "tool_instruction",
        re.compile(
            r"\b(run|execute|call|invoke)\b.{0,40}\b(shell|command|tool|function|browser)\b",
            re.I | re.S,
        ),
        InjectionRisk.REVIEW,
    ),
    (
        "encoded_payload",
        re.compile(r"\b(base64|decode this|rot13|hidden instruction)\b", re.I),
        InjectionRisk.REVIEW,
    ),
)


def assess_untrusted_content(text: str) -> ContentAssessment:
    matches = [(name, risk) for name, pattern, risk in _SIGNALS if pattern.search(text)]
    risk = (
        InjectionRisk.BLOCK
        if any(level is InjectionRisk.BLOCK for _, level in matches)
        else (InjectionRisk.REVIEW if matches else InjectionRisk.NONE)
    )
    return ContentAssessment(risk=risk, signals=tuple(name for name, _ in matches))


def evidence_envelope(text: str, evidence_id: str) -> str:
    """Delimit and escape evidence before it enters an LLM context."""
    identifier = html.escape(evidence_id, quote=True)
    escaped_text = html.escape(text)
    return f'<untrusted-evidence id="{identifier}">\n{escaped_text}\n</untrusted-evidence>'
