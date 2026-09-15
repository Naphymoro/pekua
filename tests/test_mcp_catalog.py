from pekua.mcp.server import connector_catalog


def test_catalog_keeps_restricted_sources_disabled() -> None:
    catalog = {item["source_id"]: item for item in connector_catalog()}
    for source_id in ("epo_ops", "wipo_patentscope", "aripo", "oapi", "cipc", "ajol"):
        assert catalog[source_id]["can_execute"] is False
        assert catalog[source_id]["state"] == "DISABLED"
