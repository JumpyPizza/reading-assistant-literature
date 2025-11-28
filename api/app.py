from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.documents import router as documents_router
from api.routes.jobs import router as jobs_router


def create_app() -> FastAPI:
    app = FastAPI(title="Reading Assistant API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(documents_router)
    app.include_router(jobs_router)

    @app.get("/healthz")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
