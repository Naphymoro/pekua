from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentFormat(StrEnum):
    TEXT = "text/plain"
    HTML = "text/html"
    JATS = "application/jats+xml"
    TEI = "application/tei+xml"
    PDF = "application/pdf"


class DocumentArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)
    document_id: str
    version_id: str
    media_type: str
    content: bytes
    checksum_sha256: str
    tenant_id: str
    source_uri: str
    licence: str | None = None
    access_scope: str = "public"


class Passage(BaseModel):
    model_config = ConfigDict(frozen=True)
    passage_id: str
    document_id: str
    version_id: str
    text: str
    ordinal: int
    section: str | None
    page: int | None
    start_offset: int
    end_offset: int
    metadata: Mapping[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def offsets_are_valid(self) -> Passage:
        if self.start_offset < 0 or self.end_offset < self.start_offset:
            raise ValueError("passage offsets are invalid")
        return self


class ExtractedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)
    document_id: str
    version_id: str
    title: str | None
    passages: tuple[Passage, ...]
    extractor: str
    extractor_version: str
    warnings: tuple[str, ...] = ()
