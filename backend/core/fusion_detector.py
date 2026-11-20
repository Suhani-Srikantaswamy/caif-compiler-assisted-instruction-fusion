"""Stage 3 / Stage 8 - Fusion candidate detection.

Two separate concepts are kept apart on purpose:

* **Compatible candidate pair** (Stage 3): two memory operations of the same
  kind, in the same basic block, whose addresses the compiler can relate and
  whose accessed bytes fit in the fusion window. They may be far apart.
* **Consecutive fusion opportunity** (Stage 8): a compatible pair that is
  *adjacent* in the instruction stream, so simple decode-stage hardware
  (ConsSBR / ConsSBR64) could fuse it without any prediction.

The 64-byte window
------------------
The paper fuses pairs that "access memory locations within a 64-byte range"
(a cache line). In this model the condition is: the *span* from the lowest
byte touched by the pair to the highest byte touched is <= window_bytes,
i.e. ``max(end) - min(start) <= 64``. Without alignment information we cannot
know where cache-line boundaries fall, so this models "fits in one 64-byte
region" rather than "lies in the same physical cache line".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .alias_analyzer import AddressAnalysis
from .config import FusionConfig
from .dataflow import use_def_chain
from .instruction import Category, Instruction


@dataclass
class Condition:
    name: str
    passed: bool
    detail: str


@dataclass
class PairCheck:
    head: str
    tail: str
    head_pos: int
    tail_pos: int
    kind: str                      # "LOAD+LOAD" | "STORE+STORE"
    compatible: bool
    consecutive: bool
    fusion_class: str | None       # SBR-contiguous | SBR-window | DBR | None
    byte_distance: int | None
    span_bytes: int | None
    conditions: list[Condition] = field(default_factory=list)

    @property
    def instruction_distance(self) -> int:
        return self.tail_pos - self.head_pos

    @property
    def rearrangement_useful(self) -> bool:
        return self.compatible and not self.consecutive

    def failed(self) -> list[str]:
        return [c.detail for c in self.conditions if not c.passed]

    def to_dict(self, seq_by_id: dict[str, Instruction] | None = None, addr: AddressAnalysis | None = None) -> dict:
        d = {
            "head": self.head, "tail": self.tail, "head_pos": self.head_pos, "tail_pos": self.tail_pos,
            "kind": self.kind, "compatible": self.compatible, "consecutive": self.consecutive,
            "fusion_class": self.fusion_class, "byte_distance": self.byte_distance, "span_bytes": self.span_bytes,
            "instruction_distance": self.instruction_distance,
            "catalyst_size": max(0, self.instruction_distance - 1),
            "rearrangement_useful": self.rearrangement_useful,
            "conditions": [c.__dict__ for c in self.conditions],
        }
        if seq_by_id:
            d["head_text"], d["tail_text"] = seq_by_id[self.head].text, seq_by_id[self.tail].text
        if addr:
            d["head_mem"], d["tail_mem"] = addr.mem[self.head].to_dict(), addr.mem[self.tail].to_dict()
        return d


def _kind(a: Instruction, b: Instruction) -> str | None:
    if a.category == b.category == Category.LOAD:
        return "LOAD+LOAD"
    if a.category == b.category == Category.STORE:
        return "STORE+STORE"
    return None


def check_pair(seq: list[Instruction], h: int, t: int, cfg: FusionConfig,
               addr: AddressAnalysis | None = None) -> PairCheck:
    """Evaluate every compatibility condition for head=seq[h], tail=seq[t] (h < t)."""
    addr = addr or AddressAnalysis(seq)
    H, T = seq[h], seq[t]
    conds: list[Condition] = []
    kind = _kind(H, T)

    enabled = (kind == "LOAD+LOAD" and cfg.allow_load_pairs) or (kind == "STORE+STORE" and cfg.allow_store_pairs)
    conds.append(Condition("same_operation", bool(kind) and enabled,
                           f"{H.opcode}+{T.opcode}: " + ("supported pair type" if kind and enabled else
                           ("pair type disabled in configuration" if kind else "only LOAD+LOAD or STORE+STORE can be fused"))))
    conds.append(Condition("same_basic_block", H.block == T.block,
                           f"{H.id} in {H.block}, {T.id} in {T.block}" + ("" if H.block == T.block else ": CAIF never crosses block boundaries")))
    if cfg.max_instruction_distance is not None:
        ok = t - h <= cfg.max_instruction_distance
        conds.append(Condition("instruction_distance", ok,
                               f"{t - h} instruction(s) apart (limit {cfg.max_instruction_distance})"))

    byte_dist = span = None
    fclass = None
    if kind and H.mem and T.mem:
        mh, mt = addr.mem[H.id], addr.mem[T.id]
        byte_dist = addr.distance(H.id, T.id)
        conds.append(Condition("provable_distance", byte_dist is not None,
                               f"distance = {byte_dist} bytes ({mh.addr.text()} -> {mt.addr.text()})" if byte_dist is not None
                               else f"cannot prove the distance between {mh.addr.text()} and {mt.addr.text()} (different/unknown bases)"))
        sbr = mh.base_key == mt.base_key
        if cfg.requires_same_base_register:
            conds.append(Condition("same_base_register", sbr,
                                   f"both use base {H.mem.base}" if sbr else
                                   f"bases differ ({H.mem.base} vs {T.mem.base}, or the register was redefined); "
                                   f"target {cfg.target} needs the same base register"))
        if byte_dist is not None:
            lo = min(mh.addr.offset, mt.addr.offset)
            hi = max(mh.addr.offset + mh.size, mt.addr.offset + mt.size)
            span = hi - lo
            overlap = not (mh.addr.offset + mh.size <= mt.addr.offset or mt.addr.offset + mt.size <= mh.addr.offset)
            conds.append(Condition("non_overlapping", not overlap,
                                   "accessed bytes are disjoint" if not overlap else "the two accesses overlap; fusing them is not meaningful"))
            contiguous = (mh.addr.offset + mh.size == mt.addr.offset) or (mt.addr.offset + mt.size == mh.addr.offset)
            if cfg.requires_contiguous:
                conds.append(Condition("contiguous", contiguous,
                                       "accesses are back-to-back in memory" if contiguous else
                                       f"target ConsSBR needs contiguous accesses (gap: span {span} B vs {mh.size + mt.size} B accessed)"))
            conds.append(Condition("within_window", span <= cfg.window_bytes,
                                   f"span {span} B {'<=' if span <= cfg.window_bytes else '>'} {cfg.window_bytes} B window"))
            if all(c.passed for c in conds):
                fclass = ("SBR-contiguous" if contiguous else "SBR-window") if sbr else "DBR"
        if cfg.require_same_size:
            conds.append(Condition("same_size", mh.size == mt.size, f"sizes {mh.size} B and {mt.size} B"))
        if kind == "LOAD+LOAD":
            conds.append(Condition("distinct_destinations", H.dest != T.dest,
                                   f"destinations {H.dest} and {T.dest}" + ("" if H.dest != T.dest else ": a fused load cannot write one register twice")))
        # The tail's address must not be computed from the head's result.
        chain = use_def_chain(T, seq[h:t + 1])
        indep = H.id not in chain
        conds.append(Condition("tail_independent_of_head", indep,
                               "tail does not need the head's result" if indep else
                               f"{T.id}'s use-def chain contains the head {H.id}"))

    compatible = all(c.passed for c in conds)
    return PairCheck(H.id, T.id, h, t, kind or f"{H.opcode}+{T.opcode}", compatible, t == h + 1,
                     fclass if compatible else None, byte_dist, span, conds)


def find_candidate_pairs(seq: list[Instruction], cfg: FusionConfig, include_incompatible: bool = True,
                         addr: AddressAnalysis | None = None, limit: int = 400) -> list[PairCheck]:
    """All same-kind memory pairs (head before tail) in the same block, with their compatibility."""
    addr = addr or AddressAnalysis(seq)
    out: list[PairCheck] = []
    for h, H in enumerate(seq):
        if not H.is_memory:
            continue
        for t in range(h + 1, len(seq)):
            T = seq[t]
            if T.block != H.block:
                break
            if T.category != H.category:
                continue
            pc = check_pair(seq, h, t, cfg, addr)
            if pc.compatible or include_incompatible:
                out.append(pc)
                if len(out) >= limit:
                    return out
    return out


def consecutive_opportunities(seq: list[Instruction], cfg: FusionConfig) -> list[PairCheck]:
    """Adjacent compatible pairs, chosen greedily left-to-right (each instruction fuses at most once),
    as a decode-stage fusion unit would see them."""
    addr = AddressAnalysis(seq)
    out, i = [], 0
    while i < len(seq) - 1:
        if seq[i].is_memory and seq[i + 1].is_memory:
            pc = check_pair(seq, i, i + 1, cfg, addr)
            if pc.compatible:
                out.append(pc)
                i += 2
                continue
        i += 1
    return out
