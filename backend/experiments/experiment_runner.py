"""Systematic experiment runner.

Runs every predefined sample program through the full pipeline and records
the measured metrics. Also runs a small sensitivity study (target model x
fusion window). Everything reported here is produced by THIS implementation
on the educational ISA - it is not comparable to, and must not be mixed with,
the hardware results reported in the CAIF paper.

Usage:  python -m experiments.experiment_runner   (from backend/)
"""
from __future__ import annotations

import secrets
import statistics
import time
from dataclasses import replace
from datetime import datetime

from core.config import TARGETS, FusionConfig
from core.optimizer import optimize
from core.parser import parse_program
from core.pipeline import run_caif
from examples.sample_programs import SAMPLES
from experiments.results import ROOT, save_run

TIMING_REPEATS = 25
WINDOWS = (16, 32, 64, 128)


def _time_optimizer(source: str, cfg: FusionConfig) -> float:
    """Median wall-clock time (ms) of the optimizer alone (Stage 6) - NOT program execution time."""
    seq = parse_program(source, cfg.default_size).instructions
    times = []
    for _ in range(TIMING_REPEATS):
        t0 = time.perf_counter()
        optimize(seq, cfg)
        times.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(times), 4)


def run_suite(overrides: dict | None = None, label: str = "", sweep: bool = True) -> dict:
    overrides = overrides or {}
    rows = []
    for s in SAMPLES:
        cfg = FusionConfig(**{**s["config"], **overrides})
        r = run_caif(s["source"], cfg)
        m = r["metrics"]
        moved = m["successful_rearrangements"] > 0
        rows.append({
            "sample_id": s["id"], "title": s["title"], "kind": s["kind"], "target": cfg.target,
            "instructions": m["total_instructions"], "memory_instructions": m["memory_instructions"],
            "candidate_pairs": m["compatible_candidate_pairs"], "dependencies": m["dependencies"],
            "dependency_counts": m["dependency_counts"],
            "rearrangements_attempted": m["rearrangements_attempted"],
            "successful_rearrangements": m["successful_rearrangements"],
            "rejected_rearrangements": m["rejected_rearrangements"],
            "consecutive_before": m["consecutive_before"], "consecutive_after": m["consecutive_after"],
            "additional_opportunities": m["additional_opportunities"], "percent_increase": m["percent_increase"],
            "fused_memory_ops_before_pct": m["fused_memory_ops_before_pct"],
            "fused_memory_ops_after_pct": m["fused_memory_ops_after_pct"],
            "optimizer_time_ms": _time_optimizer(s["source"], cfg),
            "validation_passed": r["validation"]["valid"], "status": r["status"],
            "expected_rearrange": s["should_rearrange"],
            "matches_specification": moved == s["should_rearrange"] and r["validation"]["valid"],
            "rejection_reasons": [ln for st in r["steps"] if st["action"] == "REJECTED"
                                  for ln in st["explanation"] if ln.startswith("Rejected: ")],
        })

    def tot(k):
        return sum(r[k] for r in rows)

    totals = {k: tot(k) for k in ("instructions", "memory_instructions", "candidate_pairs", "dependencies",
                                   "rearrangements_attempted", "successful_rearrangements",
                                   "rejected_rearrangements", "consecutive_before", "consecutive_after",
                                   "additional_opportunities")}
    totals["all_valid"] = all(r["validation_passed"] for r in rows)
    totals["all_match_specification"] = all(r["matches_specification"] for r in rows)
    totals["fused_memory_ops_before_pct"] = round(100 * 2 * totals["consecutive_before"] / totals["memory_instructions"], 2)
    totals["fused_memory_ops_after_pct"] = round(100 * 2 * totals["consecutive_after"] / totals["memory_instructions"], 2)

    sweep_rows = []
    if sweep:
        for target in TARGETS:
            for w in WINDOWS:
                b = a = ok = rej = 0
                for s in SAMPLES:
                    cfg = replace(FusionConfig(**{**s["config"], **overrides}), target=target, window_bytes=w)
                    m = run_caif(s["source"], cfg, run_differential=False)["metrics"]
                    b += m["consecutive_before"]
                    a += m["consecutive_after"]
                    ok += m["successful_rearrangements"]
                    rej += m["rejected_rearrangements"]
                sweep_rows.append({"target": target, "window_bytes": w, "consecutive_before": b,
                                   "consecutive_after": a, "successful_rearrangements": ok,
                                   "rejected_rearrangements": rej})

    now = datetime.now()
    run = {
        "id": f"exp-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}",
        "created": now.isoformat(timespec="seconds"),
        "label": label,
        "overrides": overrides,
        "note": ("Locally generated results on the educational instruction model. 'Consecutive' counts are potential "
                 "fusion opportunities, not measured hardware fusions; optimizer_time_ms is the compile-time cost of "
                 "the Python optimizer, not program run time."),
        "rows": rows,
        "totals": totals,
        "sweep": sweep_rows,
    }
    save_run(run)
    return run


def render_markdown(run: dict) -> str:
    L = [f"# Experiment report `{run['id']}`", "",
         f"Generated: {run['created']}" + (f" | Label: {run['label']}" if run.get("label") else ""), "",
         f"> {run['note']}", "", "## Per-sample results", "",
         "| Sample | Target | Instr | Mem | Cand. pairs | Deps | Attempted | OK | Rejected | Before | After | +Opp | Opt. time (ms) | Valid | Matches spec |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in run["rows"]:
        L.append(f"| {r['title']} | {r['target']} | {r['instructions']} | {r['memory_instructions']} | {r['candidate_pairs']} | "
                 f"{r['dependencies']} | {r['rearrangements_attempted']} | {r['successful_rearrangements']} | "
                 f"{r['rejected_rearrangements']} | {r['consecutive_before']} | {r['consecutive_after']} | "
                 f"{r['additional_opportunities']} | {r['optimizer_time_ms']} | {'yes' if r['validation_passed'] else 'NO'} | "
                 f"{'yes' if r['matches_specification'] else 'NO'} |")
    t = run["totals"]
    L += ["", "## Totals", "",
          f"- Instructions: {t['instructions']}, memory instructions: {t['memory_instructions']}",
          f"- Compatible candidate pairs: {t['candidate_pairs']}",
          f"- Rearrangements attempted / successful / rejected: {t['rearrangements_attempted']} / "
          f"{t['successful_rearrangements']} / {t['rejected_rearrangements']}",
          f"- Consecutive fusion opportunities: {t['consecutive_before']} before -> {t['consecutive_after']} after "
          f"(+{t['additional_opportunities']})",
          f"- Share of memory instructions in a consecutive pair: {t['fused_memory_ops_before_pct']}% -> {t['fused_memory_ops_after_pct']}%",
          f"- All transformations validated: {t['all_valid']}; all samples match their specification: {t['all_match_specification']}",
          "", "## Rejection reasons", ""]
    for r in run["rows"]:
        for reason in r["rejection_reasons"]:
            L.append(f"- **{r['sample_id']}**: {reason.removeprefix('Rejected: ')}")
    if run.get("sweep"):
        L += ["", "## Sensitivity: target model x fusion window (all samples)", "",
              "| Target | Window (B) | Before | After | Successful | Rejected |", "|---|---|---|---|---|---|"]
        for s in run["sweep"]:
            L.append(f"| {s['target']} | {s['window_bytes']} | {s['consecutive_before']} | {s['consecutive_after']} | "
                     f"{s['successful_rearrangements']} | {s['rejected_rearrangements']} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    run = run_suite(label="cli")
    md = render_markdown(run)
    out = ROOT / "documentation" / "results.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(md)
    print(md)
    print(f"Saved {run['files']['json']}, {run['files']['csv']} and documentation/results.md")
