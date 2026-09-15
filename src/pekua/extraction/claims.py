from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ExtractedDocument


class EntityProposal(BaseModel):
    model_config = ConfigDict(frozen=True)
    entity_id: str
    entity_type: str
    canonical_name: str
    aliases: tuple[str, ...] = ()


class RelationProposal(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_entity_id: str
    predicate: str
    target_entity_id: str


class ClaimProposal(BaseModel):
    model_config = ConfigDict(frozen=True)
    claim_id: str
    document_id: str
    version_id: str
    passage_id: str
    claim_text: str
    quote: str
    quote_start: int = Field(ge=0)
    quote_end: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    entities: tuple[EntityProposal, ...] = ()
    relations: tuple[RelationProposal, ...] = ()

    @model_validator(mode="after")
    def offsets_are_ordered(self) -> ClaimProposal:
        if self.quote_end < self.quote_start:
            raise ValueError("claim quote offsets are invalid")
        return self


class CitationValidationError(ValueError):
    pass


class CitationValidator:
    """Rejects hallucinated or cross-version citation anchors deterministically."""

    def validate(self, document: ExtractedDocument, claim: ClaimProposal) -> None:
        if (claim.document_id, claim.version_id) != (document.document_id, document.version_id):
            raise CitationValidationError("claim cites a different document version")
        passage = next(
            (item for item in document.passages if item.passage_id == claim.passage_id), None
        )
        if passage is None:
            raise CitationValidationError("cited passage does not exist")
        if claim.quote_end > len(passage.text):
            raise CitationValidationError("quote exceeds passage bounds")
        if passage.text[claim.quote_start : claim.quote_end] != claim.quote:
            raise CitationValidationError("quote does not match cited passage")
