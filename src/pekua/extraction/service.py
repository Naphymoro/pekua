from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from .models import DocumentArtifact, DocumentFormat, ExtractedDocument, Passage


class ExtractionError(RuntimeError):
    pass


class UnsupportedFormat(ExtractionError):
    pass


class BinaryExtractor(Protocol):
    name: str
    version: str

    def extract(self, artifact: DocumentArtifact) -> ExtractedDocument: ...


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            self.parts.append(data)


def _normalise(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


class DocumentExtractor:
    """Deterministic extraction facade. PDF/OCR engines are injected, never faked."""

    name = "pekua-structured-text"
    version = "1.0.0"

    def __init__(
        self, *, pdf_extractor: BinaryExtractor | None = None, max_bytes: int = 50_000_000
    ):
        self.pdf_extractor = pdf_extractor
        self.max_bytes = max_bytes

    def extract(self, artifact: DocumentArtifact) -> ExtractedDocument:
        if len(artifact.content) > self.max_bytes:
            raise ExtractionError(f"document exceeds {self.max_bytes} byte extraction limit")
        digest = hashlib.sha256(artifact.content).hexdigest()
        if digest != artifact.checksum_sha256.lower():
            raise ExtractionError("document checksum mismatch")
        if artifact.media_type == DocumentFormat.PDF:
            if self.pdf_extractor is None:
                raise UnsupportedFormat("PDF extractor is not configured")
            return self.pdf_extractor.extract(artifact)
        if artifact.media_type == DocumentFormat.TEXT:
            text = artifact.content.decode("utf-8", errors="replace")
            title = next((x.strip() for x in text.splitlines() if x.strip()), None)
        elif artifact.media_type == DocumentFormat.HTML:
            raw = artifact.content.decode("utf-8", errors="replace")
            parser = _TextHTMLParser()
            parser.feed(raw)
            text = html.unescape("\n".join(parser.parts))
            match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
            title = _normalise(html.unescape(match.group(1))) if match else None
        elif artifact.media_type in {DocumentFormat.JATS, DocumentFormat.TEI}:
            title, text = self._extract_xml(artifact.content)
        else:
            raise UnsupportedFormat(f"unsupported media type: {artifact.media_type}")
        return self._to_document(artifact, title, _normalise(text))

    def _extract_xml(self, content: bytes) -> tuple[str | None, str]:
        upper = content[:100_000].upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise ExtractionError("DTD and entity declarations are prohibited")
        try:
            root = ET.fromstring(content)  # noqa: S314 - DTD/entities rejected above
        except ET.ParseError as exc:
            raise ExtractionError("invalid XML document") from exc
        title = None
        for node in root.iter():
            local = node.tag.rsplit("}", 1)[-1]
            if local in {"article-title", "title"}:
                candidate = _normalise(" ".join(node.itertext()))
                if candidate:
                    title = candidate
                    break
        blocks: list[str] = []
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] in {"p", "abstract", "sec", "div"}:
                candidate = _normalise(" ".join(node.itertext()))
                if candidate and (not blocks or blocks[-1] != candidate):
                    blocks.append(candidate)
        return title, "\n\n".join(blocks)

    def _to_document(
        self, artifact: DocumentArtifact, title: str | None, text: str
    ) -> ExtractedDocument:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        passages: list[Passage] = []
        cursor = 0
        for ordinal, paragraph in enumerate(paragraphs):
            start = text.find(paragraph, cursor)
            end = start + len(paragraph)
            pid = str(
                uuid5(NAMESPACE_URL, f"{artifact.document_id}:{artifact.version_id}:{start}:{end}")
            )
            passages.append(
                Passage(
                    passage_id=pid,
                    document_id=artifact.document_id,
                    version_id=artifact.version_id,
                    text=paragraph,
                    ordinal=ordinal,
                    section=None,
                    page=None,
                    start_offset=start,
                    end_offset=end,
                )
            )
            cursor = end
        return ExtractedDocument(
            document_id=artifact.document_id,
            version_id=artifact.version_id,
            title=title,
            passages=tuple(passages),
            extractor=self.name,
            extractor_version=self.version,
        )
