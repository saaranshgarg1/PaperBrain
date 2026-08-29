from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paperbrain.api.config import get_settings
from paperbrain.api.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PAPERBRAIN_STATE_PATH", str(tmp_path / "state.json"))
    get_settings.cache_clear()
    app = create_app()
    yield TestClient(app)
    get_settings.cache_clear()


REELS_CSV = """reel_code,material,grade,gsm,width,width_unit,length_mm,mass_kg,location,status,cost_per_kg
R-101,SBS,Premium,250,1250,mm,1500000,585.9,Warehouse A,new,1.25
R-102,SBS,Premium,250,1200,mm,900000,354.4,Warehouse A,open,1.25
R-103,ABC,Bogus,,1250,mm,1000,354.4,Warehouse A,new,
"""

ORDERS_CSV = """order_number,customer,material,gsm,sheet_width_mm,sheet_length_mm,quantity,due_date,overrun_percent,rotation_allowed
ORD-2001,Acme Printing,SBS,250,390,600,900,2030-09-15,2,no
ORD-2001,Acme Printing,SBS,250,205,600,600,2030-09-15,2,no
"""


def test_reels_import_dry_run_does_not_mutate(client: TestClient) -> None:
    response = client.post(
        "/v1/imports/reels",
        files={"file": ("reels.csv", REELS_CSV, "text/csv")},
        data={"dry_run": "true"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 3
    assert body["skipped_rows"] == 1
    assert any(issue["code"] == "MISSING_GSM" for issue in body["issues"])
    assert client.get("/v1/reels").json() == []


def test_reels_import_creates_reels_and_skips_bad_rows(client: TestClient) -> None:
    response = client.post(
        "/v1/imports/reels",
        files={"file": ("reels.csv", REELS_CSV, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created_reels"] == 2
    assert body["skipped_rows"] == 1

    reels = client.get("/v1/reels").json()
    codes = {reel["reel_code"] for reel in reels}
    assert codes == {"R-101", "R-102"}
    assert all(reel["verification_state"] == "provisional" for reel in reels)


def test_reels_import_rejects_duplicate_codes(client: TestClient) -> None:
    client.post(
        "/v1/imports/reels",
        files={"file": ("reels.csv", REELS_CSV, "text/csv")},
    )
    response = client.post(
        "/v1/imports/reels",
        files={"file": ("reels.csv", REELS_CSV, "text/csv")},
    )
    body = response.json()
    assert body["created_reels"] == 0
    assert body["skipped_rows"] == 3
    assert len([issue for issue in body["issues"] if issue["code"] == "DUPLICATE_REEL_CODE"]) == 2


def test_orders_import_groups_lines_and_rejects_unknown_material(client: TestClient) -> None:
    client.post(
        "/v1/imports/reels",
        files={"file": ("reels.csv", REELS_CSV, "text/csv")},
    )
    orders_csv = ORDERS_CSV + (
        "ORD-2002,Beta Packaging,XYZ,300,400,500,100,2030-09-10,,yes\n"
    )
    response = client.post(
        "/v1/imports/orders",
        files={"file": ("orders.csv", orders_csv, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created_orders"] == 1
    assert body["created_order_lines"] == 2
    assert body["skipped_rows"] == 1
    assert any(issue["code"] == "MATERIAL_NOT_FOUND" for issue in body["issues"])

    orders = client.get("/v1/orders").json()
    assert len(orders) == 1
    assert len(orders[0]["lines"]) == 2
    assert orders[0]["status"] == "confirmed"


def test_import_templates_available(client: TestClient) -> None:
    reels = client.get("/v1/imports/reels/template")
    orders = client.get("/v1/imports/orders/template")
    assert reels.status_code == 200
    assert orders.status_code == 200
    assert "reel_code" in reels.text
    assert "order_number" in orders.text
