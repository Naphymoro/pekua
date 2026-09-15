import hashlib

import pytest

from pekua.extraction import (
    CitationValidationError,
    CitationValidator,
    ClaimProposal,
    DocumentArtifact,
    DocumentExtractor,
    ExtractionError,
)


def artifact(content: bytes) -> DocumentArtifact:
    return DocumentArtifact(
        document_id="doc-1",
        version_id="v1",
        media_type="text/plain",
        content=content,
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        tenant_id="tenant-a",
        source_uri="https://example.org/doc",
    )


def test_checksum_and_citation_offsets_are_preserved() -> None:
    result = DocumentExtractor().extract(artifact(b"A title\n\nA supports B."))
    assert result.passages[1].text == "A supports B."
    assert (result.passages[1].start_offset, result.passages[1].end_offset) == (9, 22)


def test_checksum_mismatch_is_rejected() -> None:
    source = artifact(b"trusted")
    with pytest.raises(ExtractionError, match="checksum"):
        DocumentExtractor().extract(source.model_copy(update={"content": b"tampered"}))


def test_citation_validator_rejects_hallucinated_quote() -> None:
    document = DocumentExtractor().extract(artifact(b"A title\n\nA supports B."))
    passage = document.passages[1]
    claim = ClaimProposal(
        claim_id="claim-1",
        document_id="doc-1",
        version_id="v1",
        passage_id=passage.passage_id,
        claim_text="A supports C",
        quote="A supports C.",
        quote_start=0,
        quote_end=13,
        confidence=0.9,
    )
    with pytest.raises(CitationValidationError, match="does not match"):
        CitationValidator().validate(document, claim)
