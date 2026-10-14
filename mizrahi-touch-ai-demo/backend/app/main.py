"""Loan Case Service — FastAPI entrypoint. Serves the API, the MCP endpoint and the
built single-page app (customer app, banker console, admin settings) on one port."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, db
from .api import admin, assistant, banker, followup, routes
from .config import settings
from .mcp import server as mcp_server
from .policy import store
from .workflow import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    store.ensure_seeded()
    engine.start_workers()
    yield
    engine.stop_workers()


app = FastAPI(title="Mizrahi Tefahot × JEEN — Loan Completion Agent (concept demo)", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(routes.router)
app.include_router(assistant.router)
app.include_router(banker.router)
app.include_router(followup.router)
app.include_router(admin.router)
app.include_router(mcp_server.router)

if settings.frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = settings.frontend_dist / path
        if path and target.is_file() and settings.frontend_dist in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(settings.frontend_dist / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def root():
        return JSONResponse({"service": "loan-case-service", "frontend": "not built — run the frontend build"})
