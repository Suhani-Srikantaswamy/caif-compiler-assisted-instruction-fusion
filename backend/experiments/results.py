"""Local JSON/CSV storage for experiment runs and saved configurations."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
EXP_DIR = DATA_DIR / "experiments"
CONFIG_FILE = DATA_DIR / "configs.json"
ID_RE = re.compile(r"^exp-[0-9]{8}-[0-9]{6}(-[0-9a-f]{4})?$")

CSV_FIELDS = [
    "sample_id", "title", "kind", "target", "instructions", "memory_instructions", "candidate_pairs",
    "dependencies", "rearrangements_attempted", "successful_rearrangements", "rejected_rearrangements",
    "consecutive_before", "consecutive_after", "additional_opportunities", "percent_increase",
    "optimizer_time_ms", "validation_passed", "expected_rearrange", "matches_specification",
]


def save_run(run: dict) -> dict:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    jpath = EXP_DIR / f"{run['id']}.json"
    cpath = EXP_DIR / f"{run['id']}.csv"
    files = _files_for(run["id"])
    run["files"] = files            # stored inside the JSON so a reloaded run is complete
    jpath.write_text(json.dumps(run, indent=2))
    with cpath.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in run["rows"]:
            w.writerow({k: row.get(k) for k in CSV_FIELDS})
    return files


def _files_for(run_id: str) -> dict:
    return {"json": str((EXP_DIR / f"{run_id}.json").relative_to(ROOT)),
            "csv": str((EXP_DIR / f"{run_id}.csv").relative_to(ROOT))}


def list_runs() -> list[dict]:
    if not EXP_DIR.exists():
        return []
    out = []
    for p in sorted(EXP_DIR.glob("exp-*.json"), reverse=True):
        try:
            d = json.loads(p.read_text())
            out.append({"id": d["id"], "created": d["created"], "label": d.get("label", ""),
                        "samples": len(d["rows"]), "totals": d["totals"]})
        except (json.JSONDecodeError, KeyError):
            continue
    return out


def load_run(run_id: str) -> dict | None:
    if not ID_RE.match(run_id):
        return None
    p = EXP_DIR / f"{run_id}.json"
    if not p.exists():
        return None
    run = json.loads(p.read_text())
    run.setdefault("files", _files_for(run_id))   # runs saved before this field existed
    return run


def load_configs() -> list[dict]:
    if not CONFIG_FILE.exists():
        return []
    try:
        return json.loads(CONFIG_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_config(name: str, config: dict) -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfgs = [c for c in load_configs() if c["name"] != name]
    cfgs.append({"name": name, "config": config})
    CONFIG_FILE.write_text(json.dumps(cfgs, indent=2))
    return cfgs
