import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from pekua.connectors.adapters import (
    ArxivConnector,
    CrossrefConnector,
    DoajConnector,
    ZenodoConnector,
)
from pekua.connectors.base import AccessDenied, ConnectorContext
from pekua.connectors.models import Query
from pekua.connectors.registry import default_registry


class FakeTransport:
    def __init__(self, *, data=None, text=""):
        self.data = data or {}
        self.text = text
        self.calls = []

    async def get_json(self, url, *, headers):
        self.calls.append((url, headers))
        return self.data

    async def get_text(self, url, *, headers):
        self.calls.append((url, headers))
        return self.text


class AccessGateTests(unittest.TestCase):
    def test_disabled_connectors_never_construct_or_call_transport(self):
        transport = FakeTransport()
        with self.assertRaises(AccessDenied):
            default_registry().create("epo_ops", ConnectorContext(transport=transport))
        with self.assertRaises(AccessDenied):
            default_registry().create("ajol", ConnectorContext(transport=transport))
        self.assertEqual([], transport.calls)

    def test_registry_exposes_disable_reason(self):
        manifest = default_registry().manifest("aripo")
        self.assertFalse(manifest.can_execute)
        self.assertIn("partnership", manifest.reason.lower())

    def test_registry_exposes_precise_activation_action(self):
        registry = default_registry()
        self.assertEqual("CODE_PENDING", registry.manifest("biorxiv").activation_state.value)
        self.assertEqual("AGREEMENT_REQUIRED", registry.manifest("ajol").activation_state.value)
        self.assertEqual("CREDENTIAL_MISSING", registry.manifest("epo_ops").activation_state.value)
        self.assertTrue(registry.manifest("doaj").can_execute)
        self.assertTrue(registry.manifest("zenodo").can_execute)


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_crossref_normalizes_provenance(self):
        transport = FakeTransport(
            data={
                "message": {
                    "items": [
                        {
                            "DOI": "10.1/example",
                            "title": ["African research"],
                            "URL": "https://doi.org/10.1/example",
                            "author": [{"given": "A", "family": "Scholar"}],
                        }
                    ],
                    "next-cursor": "next",
                }
            }
        )
        page = await CrossrefConnector(ConnectorContext(transport=transport)).search(
            Query(text="research")
        )
        self.assertEqual("10.1/example", page.records[0].identifiers["doi"])
        self.assertEqual(("A Scholar",), page.records[0].authors)
        self.assertEqual("next", page.next_cursor)

    async def test_arxiv_preserves_version_and_pdf_link(self):
        atom = """<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><id>http://arxiv.org/abs/2601.00001v2</id><title>A preprint</title>
          <summary>Evidence text</summary><published>2026-01-01T00:00:00Z</published>
          <author><name>A Researcher</name></author>
          <link title="pdf" href="https://arxiv.org/pdf/2601.00001v2" /></entry></feed>"""
        page = await ArxivConnector(ConnectorContext(transport=FakeTransport(text=atom))).search(
            Query(text="catalysis")
        )
        self.assertEqual("2", page.records[0].version)
        self.assertEqual("https://arxiv.org/pdf/2601.00001v2", page.records[0].full_text_url)

    async def test_doaj_normalizes_article_and_requires_licence_for_full_text(self):
        transport = FakeTransport(
            data={
                "total": 2,
                "results": [
                    {
                        "id": "record-1",
                        "bibjson": {
                            "title": "Open African research",
                            "abstract": "Evidence",
                            "year": "2026",
                            "author": [{"name": "A Scholar"}],
                            "identifier": [{"type": "doi", "id": "10.1/open"}],
                            "license": [{"type": "CC BY"}],
                            "link": [{"type": "fulltext", "url": "https://example.test/paper"}],
                        },
                    }
                ],
            }
        )
        page = await DoajConnector(ConnectorContext(transport=transport)).search(
            Query(text="green ammonia", limit=1)
        )
        self.assertIn("green%20ammonia", transport.calls[0][0])
        self.assertEqual("CC BY", page.records[0].license)
        self.assertEqual("https://example.test/paper", page.records[0].full_text_url)
        self.assertEqual("2", page.next_cursor)

    async def test_zenodo_normalizes_record_and_item_licence(self):
        transport = FakeTransport(
            data={
                "hits": {
                    "total": 1,
                    "hits": [
                        {
                            "id": 42,
                            "metadata": {
                                "title": "Dataset",
                                "doi": "10.5281/zenodo.42",
                                "creators": [{"name": "Researcher, A"}],
                                "publication_date": "2026-09-15",
                                "license": {"id": "cc-by-4.0"},
                            },
                            "links": {"html": "https://zenodo.org/records/42"},
                            "files": [
                                {"links": {"self": "https://zenodo.org/api/records/42/files/a/content"}}
                            ],
                        }
                    ],
                }
            }
        )
        page = await ZenodoConnector(ConnectorContext(transport=transport)).search(
            Query(text="dataset")
        )
        self.assertEqual("cc-by-4.0", page.records[0].license)
        self.assertEqual("10.5281/zenodo.42", page.records[0].identifiers["doi"])


if __name__ == "__main__":
    unittest.main()
