"""Stage 5 - Catalyst analysis.

For a candidate pair (HEAD at position h, TAIL at position t), the
*catalyst* is every instruction strictly between them (the paper keeps them
in a queue named "Catalyst").

The CAIF move (paper Sec. IV-A) is::

    before:  ... HEAD  c1 c2 ... ck  TAIL ...
    after :  ... [use-def chain of TAIL, in original order]  HEAD TAIL  [rest of catalyst] ...

so the instructions that compute the TAIL's address / stored value are
hoisted above the HEAD together with the TAIL, and everything else in the
catalyst stays in its relative order after the pair.

The move is legal iff no dependence edge goes from an instruction that stays
behind ({HEAD} + catalyst-minus-chain) to an instruction that moves up
(chain + TAIL) - except HEAD -> TAIL, whose order is preserved. This
generalises the paper's list of alias checks (tail vs catalyst stores, chain
loads vs catalyst/head stores, ...) and also covers WAR/WAW register
hazards that cannot occur in LLVM's SSA IR but do occur in a register ISA.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .dataflow import use_def_chain
from .dependency_analyzer import DepEdge, DependencyGraph
from .instruction import Category, Instruction, MemKind


@dataclass
class CatalystEntry:
    id: str
    text: str
    position: int
    depends_on_head: bool
    head_edges: list[str]
    in_tail_chain: bool
    provides: str | None          # what it produces for the tail (address / stored value / chain input)
    memory_effect: str            # NONE | READ | WRITE | CALL
    action: str                   # MOVES_WITH_TAIL | STAYS
    can_remain: bool              # True if it may safely stay where it is
    blocking: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class CatalystReport:
    head: str
    tail: str
    catalyst: list[str]
    chain: list[str]
    head_in_chain: bool
    locked_conflicts: list[str]
    violations: list[DepEdge]
    entries: list[CatalystEntry]
    proposed_order: list[str]     # window order after the move (only meaningful if safe)

    @property
    def safe(self) -> bool:
        return not self.head_in_chain and not self.violations and not self.locked_conflicts

    def reasons(self) -> list[str]:
        r = []
        if self.head_in_chain:
            r.append(f"The use-def chain of tail {self.tail} includes head {self.head}: the tail needs the head's result, "
                     "so it cannot be placed next to it as an independent fused partner (paper rule).")
        for e in self.violations:
            r.append(f"{e.src} -> {e.dst} [{e.type}{'/' + e.subtype if e.subtype else ''}]: {e.reason}. "
                     f"Moving {e.dst} above {e.src} would break this dependence.")
        for c in self.locked_conflicts:
            r.append(c)
        return r

    def to_dict(self) -> dict:
        return {
            "head": self.head, "tail": self.tail, "catalyst": self.catalyst, "chain": self.chain,
            "head_in_chain": self.head_in_chain, "safe": self.safe, "reasons": self.reasons(),
            "violations": [e.to_dict() for e in self.violations],
            "entries": [e.to_dict() for e in self.entries], "proposed_order": self.proposed_order,
        }


def _mem_effect(i: Instruction) -> str:
    if i.mem_kind == MemKind.READ_WRITE:
        return "CALL"
    return i.mem_kind.value


def analyze_catalyst(seq: list[Instruction], h: int, t: int, graph: DependencyGraph,
                     locked: set[str] | None = None) -> CatalystReport:
    locked = locked or set()
    H, T = seq[h], seq[t]
    catalyst = seq[h + 1:t]
    cat_ids = [c.id for c in catalyst]

    # Use-def chain of the tail, restricted to the window [HEAD .. TAIL].
    chain_full = use_def_chain(T, seq[h:t + 1])
    head_in_chain = H.id in chain_full
    chain = [c for c in chain_full if c != H.id]
    chain_set = set(chain)
    moved = chain_set | {T.id}
    stays = {H.id} | (set(cat_ids) - chain_set)

    violations = [e for e in graph.edges
                  if e.src in stays and e.dst in moved and not (e.src == H.id and e.dst == T.id)]

    locked_conflicts = [f"{x} already belongs to a fused pair; moving it would split that pair."
                        for x in sorted(moved & locked)]

    reach_from_head = graph.reachable_from(H.id)
    # What each chain member provides to the tail.
    rd_direct: dict[str, str] = {}
    for e in graph.preds(T.id):
        if e.type == "ADDRESS":
            rd_direct[e.src] = "address of tail"
        elif e.type == "RAW":
            rd_direct.setdefault(e.src, "value stored by tail" if T.category == Category.STORE else "input of tail")

    entries = []
    for pos, c in enumerate(catalyst, start=h + 1):
        head_edges = [f"{e.src}->{e.dst} {e.type}" for e in graph.edges if e.src == H.id and e.dst == c.id]
        blocking = []
        for e in violations:
            if e.src == c.id:
                blocking.append(f"must stay before {e.dst} ({e.type}{'/' + e.subtype if e.subtype else ''})")
            if e.dst == c.id:
                blocking.append(f"cannot be hoisted above {e.src} ({e.type}{'/' + e.subtype if e.subtype else ''})")
        in_chain = c.id in chain_set
        provides = rd_direct.get(c.id) or ("input to the tail's use-def chain" if in_chain else None)
        entries.append(CatalystEntry(
            id=c.id, text=c.text, position=pos,
            depends_on_head=c.id in reach_from_head, head_edges=head_edges,
            in_tail_chain=in_chain, provides=provides, memory_effect=_mem_effect(c),
            action="MOVES_WITH_TAIL" if in_chain else "STAYS",
            can_remain=not in_chain and not blocking, blocking=blocking,
        ))

    proposed = chain + [H.id, T.id] + [c for c in cat_ids if c not in chain_set]
    return CatalystReport(H.id, T.id, cat_ids, chain, head_in_chain, locked_conflicts, violations, entries, proposed)
