from .adapters import (
    ArxivConnector,
    CrossrefConnector,
    DataCiteConnector,
    DoajConnector,
    EuropePmcConnector,
    OpenAlexConnector,
    ZenodoConnector,
)
from .base import ConnectorRegistry
from .sources import SOURCES


def default_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry(SOURCES)
    registry.register("crossref", CrossrefConnector)
    registry.register("openalex", OpenAlexConnector)
    registry.register("datacite", DataCiteConnector)
    registry.register("europe_pmc", EuropePmcConnector)
    registry.register("arxiv", ArxivConnector)
    registry.register("doaj", DoajConnector)
    registry.register("zenodo", ZenodoConnector)
    return registry
