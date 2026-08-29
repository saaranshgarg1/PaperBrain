from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from paperbrain.api.container import build_container
from paperbrain.api.routes import (
    demo,
    execution,
    health,
    imports,
    machines,
    materials,
    orders,
    planning,
    reels,
    simulation,
)
from paperbrain.api.schemas import ErrorResponse
from paperbrain.domain.errors import ConcurrencyError, DomainError, NotFoundError

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app() -> FastAPI:
    app = FastAPI(
        title="PaperBrain API",
        version="0.1.0",
        description="Paper inventory, feasibility, and cutting-plan optimization API",
    )
    settings = _settings()
    app.state.container = build_container(
        state_path=settings.resolved_state_path,
        seed_demo=settings.seed_demo,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(materials.router)
    app.include_router(machines.router)
    app.include_router(reels.router)
    app.include_router(orders.router)
    app.include_router(imports.router)
    app.include_router(demo.router)
    app.include_router(planning.router)
    app.include_router(simulation.router)
    app.include_router(execution.router)

    @app.middleware("http")
    async def persist_state(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        if request.method in MUTATING_METHODS and response.status_code < 400:
            request.app.state.container.persist()
        return response

    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        body = ErrorResponse(
            code=exc.violation.code,
            message=exc.violation.message,
            field=exc.violation.field,
            context=exc.violation.context,
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body.model_dump(mode="json"))

    @app.exception_handler(NotFoundError)
    async def handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        body = ErrorResponse(code="NOT_FOUND", message=str(exc))
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=body.model_dump(mode="json"))

    @app.exception_handler(ConcurrencyError)
    async def handle_conflict(_: Request, exc: ConcurrencyError) -> JSONResponse:
        body = ErrorResponse(code="CONCURRENCY_CONFLICT", message=str(exc))
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content=body.model_dump(mode="json"))

    _mount_ui(app, settings.resolved_ui_dist_path)
    return app


def _settings():  # type: ignore[no-untyped-def]
    from paperbrain.api.config import get_settings

    return get_settings()


def _mount_ui(app: FastAPI, dist: Path) -> None:
    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")


app = create_app()


def run() -> None:
    uvicorn.run("paperbrain.api.main:app", host="0.0.0.0", port=8000, reload=False)
