from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Database, get_session
from responses import success
from routes.channels import router as channels_router
from routes.companies import router as companies_router
from routes.dashboard import router as dashboard_router
from routes.runs import router as runs_router


def create_app(database_url: str | None = None) -> FastAPI:
    database = Database(
        database_url
        or os.getenv("VESTIGE_DATABASE_URL", "sqlite:///output/vestige.db")
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        database.create_all()
        yield
        database.dispose()

    app = FastAPI(title="Vestige Admin API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:9091", "http://127.0.0.1:9091"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.database = database
    app.dependency_overrides[get_session] = database.session

    @app.get("/api/health")
    def health():
        return success({"status": "ok"})

    app.include_router(companies_router)
    app.include_router(channels_router)
    app.include_router(dashboard_router)
    app.include_router(runs_router)

    return app


app = create_app()

