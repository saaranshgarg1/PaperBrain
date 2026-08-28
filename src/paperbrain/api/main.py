from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from paperbrain.api.container import build_container
from paperbrain.api.routes import execution, health, machines, materials, orders, planning, reels, simulation
from paperbrain.api.schemas import ErrorResponse
from paperbrain.domain.errors import ConcurrencyError, DomainError, NotFoundError


def create_app() -> FastAPI:
    app = FastAPI(
        title="PaperBrain API",
        version="0.1.0",
        description="Paper inventory, feasibility, and cutting-plan optimization API",
    )
    app.state.container = build_container()
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
    app.include_router(planning.router)
    app.include_router(simulation.router)
    app.include_router(execution.router)

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

    return app


app = create_app()


def run() -> None:
    uvicorn.run("paperbrain.api.main:app", host="0.0.0.0", port=8000, reload=False)