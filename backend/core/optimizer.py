"""Stage 6 - The CAIF-inspired rearrangement algorithm.

Follows the structure of the paper's middle-end pass (Sec. IV-A):

  for each basic block:
    for each memory op HEAD (not yet paired), in program order:
      scan forward in the same block for a TAIL of the same kind:
        if (HEAD, TAIL) is not compatible            -> try the next tail
        if TAIL is right after HEAD                  -> already a consecutive pair
        catalyst  = instructions between them
        chain     = use-def chain of TAIL inside the catalyst
        if chain contains HEAD                       -> reject (paper rule)
        if any dependence would be reversed          -> reject, try the next tail
        otherwise: hoist chain above HEAD, put TAIL right after HEAD

Pair selection details that the paper does not specify (our choices):
  * Pairs that are *already consecutive* in the input are claimed first, so
    the optimizer never breaks an existing opportunity to create a new one.
  * Every instruction belongs to at most one pair; instructions of a formed
    pair are "locked" and will not be moved again.
  * The scan is repeated until no new pair is formed (fixed point), because
    one move can expose another consecutive pair.

Every committed step is also re-checked by validator.check_order (imported as static_recheck; a cheap
static safety net), and the whole result is validated again independently
by the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .alias_analyzer import AddressAnalysis
from .catalyst_analyzer import analyze_catalyst
from .config import FusionConfig
from .dependency_analyzer import build_dependency_graph
from .fusion_detector import check_pair
from .instruction import Instruction
from .validator import check_order as static_recheck   # cheap per-step safety net


@dataclass
class Step:
    number: int
    action: str                 # CONSECUTIVE | REARRANGED | REJECTED
    head: str
    tail: str
    pair: dict
    catalyst: dict | None
    before: list[str]
    after: list[str]
    moved: list[str]
    explanation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class OptimizationResult:
    original: list[Instruction]
    optimized: list[Instruction]
    steps: list[Step]
    pairs: list[tuple[str, str]]

    @property
    def rearranged(self) -> list[Step]:
        return [s for s in self.steps if s.action == "REARRANGED"]

    @property
    def rejected(self) -> list[Step]:
        return [s for s in self.steps if s.action == "REJECTED"]


def optimize(original: list[Instruction], cfg: FusionConfig) -> OptimizationResult:
    seq = list(original)
    by_id = {i.id: i for i in seq}
    locked: set[str] = set()
    pairs: list[tuple[str, str]] = []
    steps: list[Step] = []
    rejected_keys: set[tuple[str, str]] = set()

    def record(action, H, T, pc, rep, before, after, moved, expl):
        steps.append(Step(len(steps) + 1, action, H.id, T.id,
                          pc.to_dict(by_id), rep.to_dict() if rep else None,
                          before, after, moved, expl))

    # ---- Phase A: claim pairs that are already consecutive ----------------
    addr = AddressAnalysis(seq)
    i = 0
    while i < len(seq) - 1:
        H, T = seq[i], seq[i + 1]
        if H.is_memory and T.is_memory:
            pc = check_pair(seq, i, i + 1, cfg, addr)
            if pc.compatible:
                locked |= {H.id, T.id}
                pairs.append((H.id, T.id))
                ids = [x.id for x in seq]
                record("CONSECUTIVE", H, T, pc, None, ids, ids, [],
                       [f"{H.id} and {T.id} are already adjacent and compatible ({pc.fusion_class}); no movement needed."])
                i += 2
                continue
        i += 1

    # ---- Phase B: create new consecutive pairs by safe rearrangement ------
    changed, passes = True, 0
    while changed and passes < len(seq) + 1:
        changed, passes = False, passes + 1
        i = 0
        while i < len(seq):
            H = seq[i]
            if not H.is_memory or H.id in locked:
                i += 1
                continue
            addr = AddressAnalysis(seq)
            graph = build_dependency_graph(seq, addr)
            formed = False
            for t in range(i + 1, len(seq)):
                T = seq[t]
                if T.block != H.block:
                    break
                if T.category != H.category or T.id in locked:
                    continue
                pc = check_pair(seq, i, t, cfg, addr)
                if not pc.compatible:
                    continue
                ids = [x.id for x in seq]
                if t == i + 1:
                    locked |= {H.id, T.id}
                    pairs.append((H.id, T.id))
                    record("CONSECUTIVE", H, T, pc, None, ids, ids, [],
                           [f"{H.id} and {T.id} became adjacent after earlier moves; compatible ({pc.fusion_class})."])
                    formed = True
                    break
                rep = analyze_catalyst(seq, i, t, graph, locked)
                expl = [f"Candidate: HEAD {H.id} ({H.text}) at position {i}, TAIL {T.id} ({T.text}) at position {t}.",
                        f"Compatible: {pc.fusion_class}, {pc.byte_distance:+d} bytes apart, span {pc.span_bytes} B.",
                        f"Catalyst (between them): {', '.join(rep.catalyst) or 'none'}.",
                        f"Use-def chain of the TAIL inside the catalyst: {', '.join(rep.chain) or 'empty'}."]
                if rep.safe:
                    new_seq = seq[:i] + [by_id[x] for x in rep.proposed_order] + seq[t + 1:]
                    static = static_recheck(original, new_seq)
                    if not static.valid:   # safety net: should never trigger
                        expl.append("Static re-check failed: " + "; ".join(static.errors))
                        rejected_keys.add((H.id, T.id))
                        record("REJECTED", H, T, pc, rep, ids, ids, [], expl)
                        continue
                    moved = rep.chain + [T.id]
                    expl += [f"No dependence goes from {{HEAD}} ∪ (catalyst − chain) to (chain ∪ TAIL): the move is safe.",
                             (f"Hoist {', '.join(rep.chain)} above {H.id}, then place {T.id} right after {H.id}."
                              if rep.chain else f"Place {T.id} right after {H.id}."),
                             f"{H.id}+{T.id} is now a consecutive fusion opportunity."]
                    record("REARRANGED", H, T, pc, rep, ids, [x.id for x in new_seq], moved, expl)
                    seq = new_seq
                    locked |= {H.id, T.id}
                    pairs.append((H.id, T.id))
                    formed = changed = True
                    break
                if (H.id, T.id) not in rejected_keys:
                    rejected_keys.add((H.id, T.id))
                    record("REJECTED", H, T, pc, rep, ids, ids, [], expl + ["Rejected: " + r for r in rep.reasons()])
            pos = next(k for k, x in enumerate(seq) if x.id == H.id)
            i = pos + (2 if formed else 1)

    return OptimizationResult(list(original), seq, steps, pairs)
