from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container

router = APIRouter(prefix="/v1/demo", tags=["demo"])


@router.post(
    "/seed",
    status_code=status.HTTP_201_CREATED,
    summary="Load a small demo dataset (only when the system is empty)",
)
def seed_demo(
    container: Annotated[Container, Depends(get_container)],
) -> JSONResponse:
    if container.reels.list_all():
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"code": "NOT_EMPTY", "message": "Demo data can only be loaded into an empty system"},
        )
    from paperbrain.demo.bootstrap import bootstrap_demo

    bootstrap_demo(container)
    container.persist()
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"code": "DEMO_SEEDED", "message": "Demo dataset loaded"},
    )
