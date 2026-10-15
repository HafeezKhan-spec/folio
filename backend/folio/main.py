"""Folio ASGI application."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from folio.db import init_db
from folio.routes import router


def create_app(database_path: str | None = None) -> FastAPI:
    """Build the API, and serve the built frontend when it exists."""
    path = database_path or os.environ.get("FOLIO_DATABASE_PATH", "data/folio.db")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    init_db(path)
    app = FastAPI(title="Folio", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db_path = path
    app.include_router(router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    static_dir = Path(os.environ.get("FOLIO_STATIC_DIR", "frontend/dist"))
    index = static_dir / "index.html"
    if not index.is_file():
        return
    root = static_dir.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = (static_dir / full_path).resolve()
        if candidate.is_file() and (candidate == root or root in candidate.parents):
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
