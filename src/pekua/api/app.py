from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header
from fastapi.responses import FileResponse

from pekua import __version__
from pekua.config import get_settings
from pekua.connectors.registry import default_registry
from pekua.orchestration.api import configure_session_factory
from pekua.orchestration.api import router as jobs_router
from pekua.storage.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    database = Database(settings.database_url.get_secret_value())
    configure_session_factory(database.sessions)
    app.state.database = database
    try:
        yield
    finally:
        await database.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Pekua API",
        version=__version__,
        description="Evidence-first scholarly, preprint and patent intelligence",
        lifespan=lifespan,
    )
    app.include_router(jobs_router)

    @app.get("/", include_in_schema=False)
    async def workspace() -> FileResponse:
        return FileResponse(Path(__file__).parents[1] / "ui" / "index.html")

    @app.get("/health/live", tags=["system"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready", tags=["system"])
    async def readiness() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/api/v1/connectors", tags=["connectors"])
    async def connector_status(
        x_tenant_id: str = Header(alias="X-Tenant-ID"),
    ) -> list[dict[str, object]]:
        del x_tenant_id
        return [
            {
                "source_id": item.source_id,
                "display_name": item.display_name,
                "access_class": item.access_class.value,
                "state": item.state.value,
                "can_execute": item.can_execute,
                "full_text": item.full_text,
                "reason": item.reason,
                "documentation_url": item.documentation_url,
                "activation_state": item.activation_state.value,
                "activation_action": item.activation_action,
                "capabilities": list(item.capabilities),
            }
            for item in default_registry().status()
        ]

    return app


app = create_app()


def run() -> None:
    uvicorn.run("pekua.api.app:app", host="0.0.0.0", port=8000)  # noqa: S104
