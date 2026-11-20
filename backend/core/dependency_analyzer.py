"""Stage 4 - Dependency analysis.

Builds a directed dependency graph. Edge src -> dst means "src must execute
before dst". Edges only connect instructions of the *same* basic block,
because CAIF never moves instructions across block boundaries.

Edge types
----------
RAW      dst reads a register value that src wrote (true dependence)
ADDRESS  a RAW dependence where the register is dst's memory base, i.e. src
         computes dst's address (shown separately because it is exactly the
         address computation CAIF must hoist together with the tail)
WAR      dst overwrites a register that src still needs to read (anti)
WAW      both write the same register; final value must stay the same (output)
MEMORY   two memory accesses that may touch the same bytes, at least one being
         a write (subtype MEM-RAW / MEM-WAR / MEM-WAW), or any memory access
         ordered against a CALL (subtype CALL)

Register edges are computed between *nearest* conflicting instructions; the
transitive closure then covers every ordering constraint.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from .alias_analyzer import AddressAnalysis
from .dataflow import reaching_defs
from .instruction import Instruction, MemKind


@dataclass
class DepEdge:
    src: str
    dst: str
    type: str          # RAW | ADDRESS | WAR | WAW | MEMORY
    subtype: str       # register name, or MEM-RAW / MEM-WAR / MEM-WAW / CALL
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DependencyGraph:
    nodes: list[str]
    edges: list[DepEdge]

    def preds(self, node: str) -> list[DepEdge]:
        return [e for e in self.edges if e.dst == node]

    def succs(self, node: str) -> list[DepEdge]:
        return [e for e in self.edges if e.src == node]

    def reachable_from(self, node: str) -> set[str]:
        out, work = set(), [node]
        adj: dict[str, list[str]] = {}
        for e in self.edges:
            adj.setdefault(e.src, []).append(e.dst)
        while work:
            n = work.pop()
            for m in adj.get(n, []):
                if m not in out:
                    out.add(m)
                    work.append(m)
        return out

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for e in self.edges:
            c[e.type] = c.get(e.type, 0) + 1
        return c

    def to_dict(self) -> dict:
        return {"nodes": self.nodes, "edges": [e.to_dict() for e in self.edges], "counts": self.counts()}


def _writes_mem(i: Instruction) -> bool:
    return i.mem_kind in (MemKind.WRITE, MemKind.READ_WRITE)


def _reads_mem(i: Instruction) -> bool:
    return i.mem_kind in (MemKind.READ, MemKind.READ_WRITE)


def build_dependency_graph(seq: list[Instruction], addr: AddressAnalysis | None = None) -> DependencyGraph:
    addr = addr or AddressAnalysis(seq)
    rdefs = reaching_defs(seq)
    edges: list[DepEdge] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(src, dst, typ, sub, reason):
        k = (src, dst, typ, sub)
        if k not in seen:
            seen.add(k)
            edges.append(DepEdge(src, dst, typ, sub, reason))

    blocks: dict[str, list[Instruction]] = {}
    for ins in seq:
        blocks.setdefault(ins.block, []).append(ins)

    for block in blocks.values():
        # ---- register dependencies -----------------------------------
        last_writer: dict[str, Instruction] = {}
        readers_since_write: dict[str, list[Instruction]] = {}
        for ins in block:
            for r in ins.sources:
                d = rdefs.get((ins.id, r))
                if d is not None:
                    is_addr = ins.mem is not None and ins.mem.base_is_register and ins.mem.base == r
                    typ = "ADDRESS" if is_addr else "RAW"
                    what = "memory address" if is_addr else "value"
                    add(d, ins.id, typ, r, f"{ins.id} reads {r} ({what}) written by {d}")
                readers_since_write.setdefault(r, []).append(ins)
            if ins.dest:
                r = ins.dest
                for rd in readers_since_write.get(r, []):
                    if rd.id != ins.id:
                        add(rd.id, ins.id, "WAR", r, f"{ins.id} overwrites {r}, which {rd.id} must read first")
                if r in last_writer:
                    add(last_writer[r].id, ins.id, "WAW", r,
                        f"{last_writer[r].id} and {ins.id} both write {r}; the later write must stay last")
                last_writer[r] = ins
                readers_since_write[r] = []

        # ---- memory dependencies ---------------------------------------
        memops = [i for i in block if i.mem_kind != MemKind.NONE]
        for a_idx, a in enumerate(memops):
            for b in memops[a_idx + 1:]:
                if not (_writes_mem(a) or _writes_mem(b)):
                    continue   # two reads never conflict
                if a.mem_kind == MemKind.READ_WRITE or b.mem_kind == MemKind.READ_WRITE:
                    call = a if a.mem_kind == MemKind.READ_WRITE else b
                    add(a.id, b.id, "MEMORY", "CALL",
                        f"{call.id} (CALL {call.symbol}) may read/write any memory, so {a.id} and {b.id} keep their order")
                    continue
                res = addr.alias(a.id, b.id)
                if not res.may_conflict:
                    continue
                if _writes_mem(a) and _reads_mem(b):
                    sub = "MEM-RAW"
                elif _reads_mem(a) and _writes_mem(b):
                    sub = "MEM-WAR"
                else:
                    sub = "MEM-WAW"
                add(a.id, b.id, "MEMORY", sub, f"{a.id} / {b.id}: {res.kind.value} - {res.reason}")

    return DependencyGraph([i.id for i in seq], edges)


def annotate_dependencies(seq: list[Instruction], graph: DependencyGraph) -> None:
    """Fill Instruction.depends_on from the graph (for display)."""
    preds: dict[str, list[str]] = {}
    for e in graph.edges:
        preds.setdefault(e.dst, [])
        if e.src not in preds[e.dst]:
            preds[e.dst].append(e.src)
    for ins in seq:
        ins.depends_on = preds.get(ins.id, [])
