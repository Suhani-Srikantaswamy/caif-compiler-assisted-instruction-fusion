"""End-to-end CAIF pipeline: runs Stages 2-9 and returns one JSON-able dict.

Each stage lives in its own module; this file only wires them together.
"""
from __future__ import annotations

import time

from .alias_analyzer import AddressAnalysis
from .config import FusionConfig
from .dependency_analyzer import annotate_dependencies, build_dependency_graph
from .fusion_detector import consecutive_opportunities, find_candidate_pairs
from .metrics import compute_metrics
from .optimizer import optimize
from .parser import parse_program
from .validator import validate


class PipelineError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__("; ".join(e["message"] for e in errors))
        self.errors = errors


def _ins_dicts(seq):
    return [dict(i.to_dict(), position=k) for k, i in enumerate(seq)]


def parse_stage(source: str, cfg: FusionConfig):
    pr = parse_program(source, cfg.default_size)
    errors = [e.__dict__ for e in pr.errors]
    return pr, errors


def analyze(source: str, cfg: FusionConfig) -> dict:
    """Stages 2-5 on the original program (no transformation)."""
    pr, errors = parse_stage(source, cfg)
    if errors:
        raise PipelineError(errors)
    seq = pr.instructions
    addr = AddressAnalysis(seq)
    graph = build_dependency_graph(seq, addr)
    annotate_dependencies(seq, graph)
    by_id = {i.id: i for i in seq}
    cands = find_candidate_pairs(seq, cfg, include_incompatible=True, addr=addr)
    from .catalyst_analyzer import analyze_catalyst
    cat_reports = {}
    for c in cands:
        if c.compatible and not c.consecutive:
            cat_reports[f"{c.head}-{c.tail}"] = analyze_catalyst(seq, c.head_pos, c.tail_pos, graph).to_dict()
    return {
        "instructions": _ins_dicts(seq),
        "blocks": pr.blocks,
        "memory": {k: v.to_dict() for k, v in addr.mem.items()},
        "graph": graph.to_dict(),
        "candidates": [c.to_dict(by_id, addr) for c in cands],
        "catalyst_reports": cat_reports,
        "_seq": seq, "_graph": graph, "_cands": cands,
    }


def run_caif(source: str, cfg: FusionConfig, run_differential: bool = True) -> dict:
    """Full pipeline: parse -> analyse -> optimise -> validate -> detect -> metrics."""
    cfg_errors = cfg.validate()
    if cfg_errors:
        raise PipelineError([{"line": 0, "message": m, "text": ""} for m in cfg_errors])
    t0 = time.perf_counter()
    a = analyze(source, cfg)
    seq, graph, cands = a.pop("_seq"), a.pop("_graph"), a.pop("_cands")
    t1 = time.perf_counter()
    opt = optimize(seq, cfg)
    t2 = time.perf_counter()
    validation = validate(seq, opt.optimized, run_differential=run_differential)
    t3 = time.perf_counter()

    status = "UNCHANGED"
    final = opt.optimized
    if [i.id for i in final] != [i.id for i in seq]:
        status = "OPTIMIZED"
    if not validation.valid:
        status = "REJECTED_BY_VALIDATOR"
        final = list(seq)      # never report an unsafe transformation: keep the original

    opps_before = consecutive_opportunities(seq, cfg)
    opps_after = consecutive_opportunities(final, cfg)
    by_id = {i.id: i for i in seq}
    final_graph = build_dependency_graph(final)
    metrics = compute_metrics(seq, final, cands, opps_before, opps_after, opt, graph)
    t4 = time.perf_counter()
    metrics["optimizer_time_ms"] = round((t2 - t1) * 1000, 3)
    metrics["analysis_time_ms"] = round((t1 - t0) * 1000, 3)
    metrics["validation_time_ms"] = round((t3 - t2) * 1000, 3)
    metrics["total_time_ms"] = round((t4 - t0) * 1000, 3)

    orig_pos = {i.id: k for k, i in enumerate(seq)}
    return {
        **a,
        "config": cfg.to_dict(),
        "status": status,
        "optimized": [dict(i.to_dict(), position=k, original_position=orig_pos[i.id]) for k, i in enumerate(final)],
        "optimized_graph": final_graph.to_dict(),
        "steps": [s.to_dict() for s in opt.steps],
        "pairs": [list(p) for p in opt.pairs],
        "proposed_order": [i.id for i in opt.optimized],
        "validation": validation.to_dict(),
        "opportunities_before": [p.to_dict(by_id) for p in opps_before],
        "opportunities_after": [p.to_dict(by_id) for p in opps_after],
        "metrics": metrics,
    }
