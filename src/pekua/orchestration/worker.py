from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from .engine import Worker


async def run_worker_loop(worker: Worker, stop: asyncio.Event, idle_seconds: float = 1.0) -> None:
    while not stop.is_set():
        if not await worker.run_once():
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=idle_seconds)
    logging.getLogger(__name__).info("worker_stopped", extra={"worker_id": worker.worker_id})
