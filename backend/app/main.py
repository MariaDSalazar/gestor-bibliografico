"""FastAPI — punto de entrada (capa de interfaces).

Composition root + montaje de routers + mapeo de excepciones de dominio a HTTP.
Arranque dev:  uvicorn app.main:app --reload  (desde la carpeta backend/)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .bootstrap import build_container
from .domain.exceptions import ExtractionError, NotFoundError, ValidationError
from .interfaces.api.deps import set_container
from .interfaces.api.routers import auth, citations, collections, documents, export


def create_app() -> FastAPI:
    # Composition root: arma el contenedor y lo registra para la DI.
    set_container(build_container())

    app = FastAPI(title="Gestor Bibliográfico", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Desarrollo: evita que el navegador cachee el frontend (HTML/JS/CSS).
    @app.middleware("http")
    async def _no_cache(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response

    # Excepciones de dominio → HTTP (sin acoplar el dominio a FastAPI).
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _validation(_: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ExtractionError)
    async def _extraction(_: Request, exc: ExtractionError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(NotImplementedError)
    async def _not_implemented(_: Request, exc: NotImplementedError):
        return JSONResponse(status_code=501, content={"detail": str(exc)})

    @app.get("/api/health")
    def health():
        return {"ok": True, "stack": "fastapi", "arch": "ddd"}

    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(collections.router)
    app.include_router(citations.router)
    app.include_router(export.router)

    # VISTA: sirve el frontend estático (Vue + PrimeVue, sin build). Sin Node.
    root = Path(__file__).resolve().parents[2]
    static_dir = root / "frontend"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")

    return app


app = create_app()
