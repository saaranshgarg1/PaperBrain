from __future__ import annotations

import textwrap
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import PlainTextResponse

from paperbrain.api.container import Container
from paperbrain.api.dependencies import get_container
from paperbrain.application.import_service import ImportResult, import_orders, import_reels
from paperbrain.ingestion.orders_import import OrdersImportParser
from paperbrain.ingestion.reels_import import ReelsImportParser

router = APIRouter(prefix="/v1/imports", tags=["imports"])

REELS_TEMPLATE = textwrap.dedent(
    """\
    reel_code,material,grade,gsm,width,width_unit,length_mm,mass_kg,location,status,cost_per_kg,currency
    R-001,SBS,Premium,250,1250,mm,1500000,585.9,Main Store,new,1.25,USD
    R-002,SBS,Premium,250,1200,mm,900000,354.4,Main Store,open,1.25,USD
    """
)

ORDERS_TEMPLATE = textwrap.dedent(
    """\
    order_number,customer,material,gsm,sheet_width_mm,sheet_length_mm,quantity,due_date,overrun_percent,rotation_allowed
    ORD-1001,Acme Printing,SBS,250,390,600,900,2026-09-15,2,no
    ORD-1002,Acme Printing,SBS,250,205,600,600,2026-09-15,2,no
    """
)


@router.post("/reels", response_model=ImportResult, summary="Import reels from CSV")
async def import_reels_csv(
    container: Annotated[Container, Depends(get_container)],
    file: Annotated[UploadFile, File(description="Reel inventory CSV")],
    dry_run: Annotated[bool, Form(description="Validate only, do not save")] = False,
) -> ImportResult:
    content = (await file.read()).decode("utf-8-sig")
    records = ReelsImportParser().parse(content)
    return import_reels(container, records, dry_run=dry_run)


@router.post("/orders", response_model=ImportResult, summary="Import orders from CSV")
async def import_orders_csv(
    container: Annotated[Container, Depends(get_container)],
    file: Annotated[UploadFile, File(description="Customer orders CSV")],
    dry_run: Annotated[bool, Form(description="Validate only, do not save")] = False,
) -> ImportResult:
    content = (await file.read()).decode("utf-8-sig")
    records = OrdersImportParser().parse(content)
    return import_orders(container, records, dry_run=dry_run)


@router.get("/reels/template", response_class=PlainTextResponse, summary="Download the reel CSV template")
def reels_template() -> str:
    return REELS_TEMPLATE


@router.get("/orders/template", response_class=PlainTextResponse, summary="Download the order CSV template")
def orders_template() -> str:
    return ORDERS_TEMPLATE


__all__ = ["router", "REELS_TEMPLATE", "ORDERS_TEMPLATE"]
