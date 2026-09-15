from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from .models import ConnectorManifest, Query, SearchPage


class AccessDenied(RuntimeError):
    pass


class SchemaDrift(RuntimeError):
    pass


class Transport(Protocol):
    async def get_json(self, url: str, *, headers: Mapping[str, str]) -> Mapping[str, Any]: ...
    async def get_text(self, url: str, *, headers: Mapping[str, str]) -> str: ...


class HttpxTransport:
    """Async default transport; production workers may inject a traced client."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(timeout=30, follow_redirects=False)

    async def get_json(self, url: str, *, headers: Mapping[str, str]) -> Mapping[str, Any]:
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise SchemaDrift("Expected a JSON object")
        return value

    async def get_text(self, url: str, *, headers: Mapping[str, str]) -> str:
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


@dataclass(frozen=True)
class ConnectorContext:
    transport: Transport
    user_agent: str = "Pekua/0.1 (contact: research-admin@example.invalid)"


class Connector:
    manifest: ConnectorManifest

    def __init__(self, context: ConnectorContext):
        self.context = context

    def assert_permitted(self) -> None:
        if not self.manifest.can_execute:
            reason = self.manifest.reason or "source access has not been enabled"
            raise AccessDenied(f"{self.manifest.source_id}: {reason}")

    def headers(self) -> Mapping[str, str]:
        return {"Accept": "application/json", "User-Agent": self.context.user_agent}

    def url(self, path: str, params: Mapping[str, object]) -> str:
        assert self.manifest.base_url
        return f"{self.manifest.base_url.rstrip('/')}/{path.lstrip('/')}?{urlencode(params)}"

    async def search(self, query: Query) -> SearchPage:
        raise NotImplementedError


class ConnectorRegistry:
    def __init__(self, manifests: Mapping[str, ConnectorManifest]):
        self._manifests = dict(manifests)
        self._factories: dict[str, Callable[[ConnectorContext], Connector]] = {}

    def register(self, source_id: str, factory: Callable[[ConnectorContext], Connector]) -> None:
        if source_id not in self._manifests:
            raise KeyError(f"Manifest missing for {source_id}")
        self._factories[source_id] = factory

    def manifest(self, source_id: str) -> ConnectorManifest:
        return self._manifests[source_id]

    def create(self, source_id: str, context: ConnectorContext) -> Connector:
        manifest = self.manifest(source_id)
        if not manifest.can_execute:
            reason = manifest.reason or manifest.state.value
            raise AccessDenied(f"{source_id}: {reason}")
        try:
            connector = self._factories[source_id](context)
        except KeyError as exc:
            raise AccessDenied(f"{source_id}: connector implementation unavailable") from exc
        connector.assert_permitted()
        return connector

    def status(self) -> tuple[ConnectorManifest, ...]:
        return tuple(sorted(self._manifests.values(), key=lambda item: item.source_id))
