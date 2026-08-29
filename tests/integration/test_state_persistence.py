from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paperbrain.api.config import get_settings
from paperbrain.api.main import create_app


@pytest.fixture
def state_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "state.json"
    monkeypatch.setenv("PAPERBRAIN_STATE_PATH", str(path))
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def _client() -> TestClient:
    return TestClient(create_app())


def test_state_survives_restart(state_path: Path) -> None:
    first = _client()
    assert first.post("/v1/demo/seed").status_code == 201
    assert len(first.get("/v1/reels").json()) == 2

    second = _client()
    assert len(second.get("/v1/reels").json()) == 2
    assert len(second.get("/v1/orders").json()) == 1
    assert state_path.exists()


def test_plan_report_survives_restart(state_path: Path) -> None:
    first = _client()
    first.post("/v1/demo/seed")
    solve = first.post("/v1/planning/runs", json={"policy_profile": "normal"})
    assert solve.status_code == 200
    plan_id = solve.json()["plan_id"]

    second = _client()
    listed = second.get("/v1/planning/plans").json()
    assert [item["plan_id"] for item in listed] == [plan_id]
    report = second.get(f"/v1/planning/plans/{plan_id}")
    assert report.status_code == 200
    assert report.json()["validation_valid"] is True
    assert report.json()["patterns"]


def test_failed_request_does_not_persist(state_path: Path) -> None:
    first = _client()
    first.post("/v1/demo/seed")
    # 422 domain error must not write state
    first.post("/v1/demo/seed")
    assert first.get("/v1/reels").json()

    second = _client()
    assert len(second.get("/v1/reels").json()) == 2


def test_no_state_path_means_memory_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PAPERBRAIN_STATE_PATH", "")
    get_settings.cache_clear()
    first = _client()
    first.post("/v1/demo/seed")
    second = _client()
    assert second.get("/v1/reels").json() == []
