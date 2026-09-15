from __future__ import annotations

import asyncio
import os
import signal
import socket

import httpx

from pekua.config import get_settings
from pekua.connectors.base import ConnectorContext, HttpxTransport
from pekua.connectors.models import Query
from pekua.connectors.registry import default_registry
from pekua.orchestration.contracts import PermanentTaskError, TaskContext, TaskResult
from pekua.orchestration.engine import Worker
from pekua.orchestration.worker import run_worker_loop
from pekua.storage.database import Database


async def search_source(payload: dict[str, object], context: TaskContext) -> TaskResult:
    del context
    source_id = payload.get("source_id")
    text = payload.get("query")
    if not isinstance(source_id, str) or not isinstance(text, str) or not text.strip():
        raise PermanentTaskError("source_id and non-empty query are required")
    limit_value = payload.get("limit", 25)
    if not isinstance(limit_value, int):
        raise PermanentTaskError("limit must be an integer")

    registry = default_registry()
    try:
        manifest = registry.manifest(source_id)
    except KeyError as exc:
        raise PermanentTaskError(f"unknown connector: {source_id}") from exc
    if not manifest.can_execute:
        reason = manifest.reason or "connector is disabled"
        raise PermanentTaskError(f"{source_id}: {reason}")
    async with httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client:
        connector = registry.create(
            source_id,
            ConnectorContext(
                transport=HttpxTransport(client),
                user_agent="Pekua/0.1 (repository: github.com/Naphymoro/pekua)",
            ),
        )
        page = await connector.search(Query(text=text, limit=limit_value))
    return TaskResult(
        {
            "source_id": source_id,
            "records": [record.model_dump(mode="json") for record in page.records],
            "next_cursor": page.next_cursor,
            "request_id": page.request_id,
        }
    )


async def serve() -> None:
    settings = get_settings()
    database = Database(settings.database_url.get_secret_value())
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop.set)

    worker = Worker(
        database.sessions,
        worker_id=f"{socket.gethostname()}:{os.getpid()}",
        handlers={"connector.search": search_source},
    )
    try:
        await run_worker_loop(worker, stop)
    finally:
        await database.close()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
