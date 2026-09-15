from __future__ import annotations

import pytest

from pekua.orchestration.contracts import PermanentTaskError, TaskContext
from pekua.worker import search_source


@pytest.mark.asyncio
async def test_search_handler_rejects_invalid_payload_before_network() -> None:
    context = TaskContext("job", 1, "tenant", "trace", None, False)
    with pytest.raises(PermanentTaskError):
        await search_source({"source_id": "arxiv"}, context)


@pytest.mark.asyncio
async def test_search_handler_cannot_bypass_disabled_connector() -> None:
    context = TaskContext("job", 1, "tenant", "trace", None, False)
    with pytest.raises(PermanentTaskError, match="Documented machine access"):
        await search_source({"source_id": "aripo", "query": "ammonia"}, context)
