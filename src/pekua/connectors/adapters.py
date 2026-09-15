from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import unescape
from typing import Any

from defusedxml import ElementTree  # type: ignore[import-untyped]

from .base import Connector, SchemaDrift
from .models import Query, SearchPage, SourceRecord
from .sources import SOURCES


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _authors(items: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    values = []
    for item in items:
        name = _text(item.get("display_name")) or " ".join(
            part for part in (_text(item.get("given")), _text(item.get("family"))) if part
        )
        if name:
            values.append(name)
    return tuple(values)


class CrossrefConnector(Connector):
    manifest = SOURCES["crossref"]

    async def search(self, query: Query) -> SearchPage:
        self.assert_permitted()
        params: dict[str, object] = {"query": query.text, "rows": min(query.limit, 1000)}
        if query.cursor:
            params["cursor"] = query.cursor
        data = await self.context.transport.get_json(
            self.url("works", params), headers=self.headers()
        )
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("items"), list):
            raise SchemaDrift("Crossref response missing message.items")
        records = []
        for item in message["items"]:
            if not isinstance(item, dict):
                continue
            doi = str(item.get("DOI", ""))
            titles = item.get("title") or []
            title = str(titles[0]) if titles else "Untitled"
            records.append(
                SourceRecord.now(
                    source_id="crossref",
                    source_record_id=doi,
                    title=title,
                    record_url=str(item.get("URL") or f"https://doi.org/{doi}"),
                    identifiers={"doi": doi} if doi else {},
                    authors=_authors(item.get("author") or []),
                    raw=item,
                )
            )
        cursor = message.get("next-cursor")
        return SearchPage(records=tuple(records), next_cursor=str(cursor) if cursor else None)


class OpenAlexConnector(Connector):
    manifest = SOURCES["openalex"]

    async def search(self, query: Query) -> SearchPage:
        self.assert_permitted()
        params: dict[str, object] = {"search": query.text, "per-page": min(query.limit, 200)}
        if query.cursor:
            params["cursor"] = query.cursor
        data = await self.context.transport.get_json(
            self.url("works", params), headers=self.headers()
        )
        items = data.get("results")
        if not isinstance(items, list):
            raise SchemaDrift("OpenAlex response missing results")
        records = []
        for item in items:
            if not isinstance(item, dict):
                continue
            primary = item.get("primary_location") or {}
            source = primary.get("source") or {}
            doi = str(item.get("doi") or "").removeprefix("https://doi.org/")
            oa = item.get("open_access") or {}
            best = item.get("best_oa_location") or {}
            records.append(
                SourceRecord.now(
                    source_id="openalex",
                    source_record_id=str(item.get("id", "")),
                    title=str(item.get("display_name") or "Untitled"),
                    record_url=str(item.get("id") or primary.get("landing_page_url") or ""),
                    identifiers={"doi": doi} if doi else {},
                    authors=tuple(
                        str(x.get("author", {}).get("display_name"))
                        for x in item.get("authorships", [])
                        if x.get("author")
                    ),
                    published_at=_text(item.get("publication_date")),
                    license=_text(best.get("license")),
                    full_text_url=_text(best.get("pdf_url")) if oa.get("is_oa") else None,
                    raw={**item, "primary_source": source.get("display_name")},
                )
            )
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        return SearchPage(records=tuple(records), next_cursor=str(cursor) if cursor else None)


class DataCiteConnector(Connector):
    manifest = SOURCES["datacite"]

    async def search(self, query: Query) -> SearchPage:
        self.assert_permitted()
        page = int(query.cursor or "1")
        data = await self.context.transport.get_json(
            self.url(
                "dois",
                {"query": query.text, "page[size]": min(query.limit, 100), "page[number]": page},
            ),
            headers=self.headers(),
        )
        items = data.get("data")
        if not isinstance(items, list):
            raise SchemaDrift("DataCite response missing data")
        records = []
        for item in items:
            attrs = item.get("attributes") or {}
            doi = str(attrs.get("doi") or item.get("id") or "")
            titles = attrs.get("titles") or []
            title = str(titles[0].get("title")) if titles else "Untitled"
            records.append(
                SourceRecord.now(
                    source_id="datacite",
                    source_record_id=doi,
                    title=title,
                    record_url=str(attrs.get("url") or f"https://doi.org/{doi}"),
                    identifiers={"doi": doi},
                    authors=tuple(
                        str(c.get("name")) for c in attrs.get("creators", []) if c.get("name")
                    ),
                    published_at=_text(attrs.get("published")),
                    raw=item,
                )
            )
        return SearchPage(
            records=tuple(records),
            next_cursor=str(page + 1) if len(items) == min(query.limit, 100) else None,
        )


class EuropePmcConnector(Connector):
    manifest = SOURCES["europe_pmc"]

    async def search(self, query: Query) -> SearchPage:
        self.assert_permitted()
        params: dict[str, object] = {
            "query": query.text,
            "format": "json",
            "pageSize": min(query.limit, 1000),
        }
        if query.cursor:
            params["cursorMark"] = query.cursor
        data = await self.context.transport.get_json(
            self.url("search", params), headers=self.headers()
        )
        result_list = data.get("resultList") or {}
        items = result_list.get("result")
        if not isinstance(items, list):
            raise SchemaDrift("Europe PMC response missing resultList.result")
        records = tuple(
            SourceRecord.now(
                source_id="europe_pmc",
                source_record_id=str(x.get("id", "")),
                title=str(x.get("title") or "Untitled"),
                record_url=(
                    "https://europepmc.org/article/"
                    f"{x.get('source', 'MED')}/{x.get('id', '')}"
                ),
                identifiers={
                    k: str(v)
                    for k, v in {
                        "doi": x.get("doi"),
                        "pmid": x.get("pmid"),
                        "pmcid": x.get("pmcid"),
                    }.items()
                    if v
                },
                authors=tuple(
                    a.strip() for a in str(x.get("authorString") or "").split(",") if a.strip()
                ),
                published_at=_text(x.get("firstPublicationDate")),
                full_text_url=f"https://europepmc.org/articles/{x['pmcid']}"
                if x.get("isOpenAccess") == "Y" and x.get("pmcid")
                else None,
                raw=x,
            )
            for x in items
            if isinstance(x, dict)
        )
        cursor = data.get("nextCursorMark")
        return SearchPage(records=records, next_cursor=str(cursor) if cursor else None)


class ArxivConnector(Connector):
    manifest = SOURCES["arxiv"]
    _atom = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

    async def search(self, query: Query) -> SearchPage:
        self.assert_permitted()
        start = int(query.cursor or "0")
        url = self.url(
            "api/query",
            {
                "search_query": f"all:{query.text}",
                "start": start,
                "max_results": min(query.limit, 100),
            },
        )
        xml = await self.context.transport.get_text(
            url, headers={**self.headers(), "Accept": "application/atom+xml"}
        )
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            raise SchemaDrift("arXiv response is not valid Atom XML") from exc
        records = []
        for entry in root.findall("a:entry", self._atom):
            record_url = entry.findtext("a:id", default="", namespaces=self._atom)
            record_id = record_url.rsplit("/", 1)[-1]
            links = {
                link.attrib.get("title") or link.attrib.get("rel"): link.attrib.get("href")
                for link in entry.findall("a:link", self._atom)
            }
            authors = tuple(
                node.findtext("a:name", default="", namespaces=self._atom)
                for node in entry.findall("a:author", self._atom)
            )
            records.append(
                SourceRecord.now(
                    source_id="arxiv",
                    source_record_id=record_id,
                    title=" ".join(
                        entry.findtext("a:title", default="Untitled", namespaces=self._atom).split()
                    ),
                    record_url=record_url,
                    identifiers={"arxiv": record_id},
                    authors=authors,
                    abstract=unescape(
                        " ".join(
                            entry.findtext("a:summary", default="", namespaces=self._atom).split()
                        )
                    ),
                    published_at=_text(entry.findtext("a:published", namespaces=self._atom)),
                    version=record_id.rsplit("v", 1)[-1] if "v" in record_id else None,
                    full_text_url=links.get("pdf"),
                    raw={"atom_id": record_url},
                )
            )
        next_cursor = str(start + len(records)) if len(records) == min(query.limit, 100) else None
        return SearchPage(records=tuple(records), next_cursor=next_cursor)
