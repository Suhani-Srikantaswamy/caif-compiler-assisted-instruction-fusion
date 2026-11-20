import pytest
from fastapi.testclient import TestClient

import experiments.results as results
from main import app

client = TestClient(app)
SRC = "L1: LOAD R1, [A+0]\nX: ADD R2, R3, R4\nL2: LOAD R5, [A+8]"


@pytest.fixture(autouse=True)
def tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "DATA_DIR", tmp_path)
    monkeypatch.setattr(results, "EXP_DIR", tmp_path / "experiments")
    monkeypatch.setattr(results, "CONFIG_FILE", tmp_path / "configs.json")
    monkeypatch.setattr(results, "ROOT", tmp_path)


def test_health_and_examples():
    assert client.get("/api/health").json()["status"] == "ok"
    assert len(client.get("/api/examples").json()) >= 10


def test_parse_reports_errors_with_200():
    r = client.post("/api/parse", json={"source": "LAOD R1, [A]"}).json()
    assert not r["ok"] and "Invalid opcode" in r["errors"][0]["message"]


def test_analyze_and_optimize():
    a = client.post("/api/analyze", json={"source": SRC}).json()
    assert any(c["compatible"] for c in a["candidates"])
    o = client.post("/api/optimize", json={"source": SRC}).json()
    assert [i["id"] for i in o["optimized"]] == ["L1", "L2", "X"]
    assert o["validation"]["valid"] and o["metrics"]["additional_opportunities"] == 1


def test_optimize_invalid_program_is_422():
    r = client.post("/api/optimize", json={"source": "LOAD R1"})
    assert r.status_code == 422 and r.json()["detail"]["errors"]


def test_invalid_config_is_422():
    assert client.post("/api/optimize", json={"source": SRC, "config": {"target": "Helios"}}).status_code == 422


def test_validate_endpoint():
    ok = client.post("/api/validate", json={"source": SRC, "order": ["L1", "L2", "X"]}).json()
    assert ok["valid"]
    bad = client.post("/api/validate", json={"source": "S: STORE [A], R1\nL: LOAD R2, [A]", "order": ["L", "S"]}).json()
    assert not bad["valid"]


def test_experiments_roundtrip():
    run = client.post("/api/experiments/run", json={"label": "t", "sweep": False}).json()
    assert run["totals"]["all_valid"]
    listed = client.get("/api/experiments/results").json()
    assert listed[0]["id"] == run["id"]
    loaded = client.get(f"/api/experiments/{run['id']}").json()
    assert loaded["rows"] and loaded["files"]["json"].endswith(f"{run['id']}.json")   # files survive reload
    assert "# Experiment report" in client.get(f"/api/report/{run['id']}").json()["markdown"]
    assert client.get("/api/experiments/exp-00000000-000000").status_code == 404
    assert client.get("/api/experiments/..%2Fsecret").status_code == 404


def test_configs_roundtrip():
    client.post("/api/configs", json={"name": "wide", "config": {"window_bytes": 128}})
    assert client.get("/api/configs").json()[0]["config"]["window_bytes"] == 128
