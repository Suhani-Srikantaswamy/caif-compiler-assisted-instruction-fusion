"""Fusion-opportunity metrics.

IMPORTANT: these numbers count *potential* fusion opportunities in the
simulated instruction model (adjacent compatible pairs a ConsSBR/ConsSBR64-style
decoder could fuse). They are not measured hardware fusions and not speedups.
"""
from __future__ import annotations


def compute_metrics(original, optimized, candidates, opps_before, opps_after, opt_result, graph) -> dict:
    formed = set(opt_result.pairs)
    rearranged = opt_result.rearranged
    rejected_unique = {(s.head, s.tail) for s in opt_result.rejected} - formed
    # Rejected heads that never found any partner (more useful than raw attempt counts)
    paired_ids = {x for p in formed for x in p}
    blocked_heads = sorted({h for (h, _t) in rejected_unique if h not in paired_ids})
    before, after = len(opps_before), len(opps_after)
    compatible = [c for c in candidates if c.compatible]
    return {
        "total_instructions": len(original),
        "memory_instructions": sum(1 for i in original if i.is_memory),
        "load_instructions": sum(1 for i in original if i.opcode == "LOAD"),
        "store_instructions": sum(1 for i in original if i.opcode == "STORE"),
        "dependencies": len(graph.edges),
        "dependency_counts": graph.counts(),
        "compatible_candidate_pairs": len(compatible),
        "non_consecutive_candidate_pairs": sum(1 for c in compatible if not c.consecutive),
        "consecutive_before": before,
        "consecutive_after": after,
        "additional_opportunities": after - before,
        "percent_increase": round(100.0 * (after - before) / before, 2) if before > 0 else None,
        "rearrangements_attempted": len(rearranged) + len(rejected_unique),
        "successful_rearrangements": len(rearranged),
        "rejected_rearrangements": len(rejected_unique),
        "blocked_heads": blocked_heads,
        "instructions_moved": sorted({m for s in rearranged for m in s.moved}),
        "fused_memory_ops_before_pct": round(100.0 * 2 * before / max(1, sum(1 for i in original if i.is_memory)), 2),
        "fused_memory_ops_after_pct": round(100.0 * 2 * after / max(1, sum(1 for i in original if i.is_memory)), 2),
        "fusion_class_after": _class_counts(opps_after),
        "fusion_class_before": _class_counts(opps_before),
        "note": "Potential consecutive fusion opportunities in the simulated model - not measured hardware fusion or speedup.",
    }


def _class_counts(opps) -> dict:
    out: dict[str, int] = {}
    for p in opps:
        out[p.fusion_class] = out.get(p.fusion_class, 0) + 1
    return out
