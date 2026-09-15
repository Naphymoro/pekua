from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AccessClass(StrEnum):
    PUBLIC_API = "PUBLIC_API"
    OPEN_REPOSITORY = "OPEN_REPOSITORY"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    PARTNERSHIP_REQUIRED = "PARTNERSHIP_REQUIRED"
    METADATA_ONLY = "METADATA_ONLY"
    MANUAL_ONLY = "MANUAL_ONLY"
    PROHIBITED = "PROHIBITED"


class ConnectorState(StrEnum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    RATE_LIMITED = "RATE_LIMITED"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"
    QUARANTINED = "QUARANTINED"


EXECUTABLE_ACCESS = frozenset({AccessClass.PUBLIC_API, AccessClass.OPEN_REPOSITORY})


class ConnectorManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_id: str
    display_name: str
    owner: str
    jurisdiction: str | None
    access_class: AccessClass
    state: ConnectorState
    base_url: str | None
    documentation_url: str | None
    formats: tuple[str, ...] = ()
    authentication: str = "none"
    credential_secret: str | None = None
    full_text: bool = False
    item_license_required: bool = True
    rate_limit_per_second: float = 1.0
    reason: str | None = None
    last_verified: str | None = None

    @property
    def can_execute(self) -> bool:
        return self.state == ConnectorState.ENABLED and self.access_class in EXECUTABLE_ACCESS


class Query(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    limit: int = Field(default=25, ge=1, le=1000)
    cursor: str | None = None
    filters: dict[str, str] = Field(default_factory=dict)


class SourceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_id: str
    source_record_id: str
    title: str
    record_url: str
    retrieved_at: str
    identifiers: dict[str, str] = Field(default_factory=dict)
    authors: tuple[str, ...] = ()
    abstract: str | None = None
    published_at: str | None = None
    version: str | None = None
    license: str | None = None
    full_text_url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def now(cls, **kwargs: Any) -> SourceRecord:
        return cls(retrieved_at=datetime.now(UTC).isoformat(), **kwargs)


class SearchPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    records: tuple[SourceRecord, ...]
    next_cursor: str | None = None
    request_id: str | None = None
