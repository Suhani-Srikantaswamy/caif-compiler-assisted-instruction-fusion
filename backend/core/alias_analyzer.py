"""Simplified, conservative alias analysis.

Every memory operand is resolved to an *abstract address*::

    (kind, base, offset)

    kind = "symbol"  : base is a named object (A, B, ...). Distinct symbols are
                       distinct objects and never overlap.
    kind = "value"   : base is an opaque pointer value, e.g. "R3@in(B0)"
                       (live into the block) or "R5@I4" (produced by I4).
    kind = "absolute": a constant address (from MOV Rd, imm).

Resolution follows ADDR / MOV / ADD-imm / SUB-imm chains, which is the
educational analogue of LLVM's ``stripAndAccumulateConstantOffsets`` (find a
common base pointer and accumulate constant offsets). When two addresses
share a base we can compute the exact distance; otherwise the analysis must
answer MAY_ALIAS.

Soundness limits (audit fix)
----------------------------
Registers are 64-bit, so an address computation wraps around modulo 2**64
(e.g. R3 + 2**64 is the same address as R3). Exact offset arithmetic is
therefore only trusted while every offset stays within +/- OFFSET_LIMIT, far
from any wrap-around. Beyond that the analysis answers MAY_ALIAS / "distance
unknown".

"Different symbols never overlap" only holds for accesses that stay *inside*
their object. Each symbol is modelled as an object of at most OBJECT_LIMIT
bytes, so an access to SYM+offset is in bounds only if
0 <= offset and offset + size <= OBJECT_LIMIT. An out-of-bounds access (for
example ADDR R3, A, 2**28) may land in another object, so NO_ALIAS is never
derived from it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .dataflow import reaching_defs
from .instruction import Instruction


OBJECT_LIMIT = 1 << 24      # max size of one symbol object (16 MiB) in the model
OFFSET_LIMIT = 1 << 40      # beyond this, constant-offset reasoning is not trusted (wrap-around)


def _in_bounds(p: "AbsAddr", size: int) -> bool:
    """A symbol access that provably stays inside its object."""
    return p.kind == "symbol" and 0 <= p.offset and p.offset + size <= OBJECT_LIMIT


def _exact(p: "AbsAddr") -> bool:
    """Offset small enough that 64-bit wrap-around cannot affect comparisons."""
    return abs(p.offset) <= OFFSET_LIMIT


class AliasKind(str, Enum):
    NO_ALIAS = "NO_ALIAS"
    MUST_ALIAS = "MUST_ALIAS"        # exactly the same bytes
    PARTIAL_ALIAS = "PARTIAL_ALIAS"  # provably overlapping, but not identical
    MAY_ALIAS = "MAY_ALIAS"          # cannot prove anything -> assume overlap


@dataclass(frozen=True)
class AbsAddr:
    kind: str
    base: str
    offset: int

    def text(self) -> str:
        if self.kind == "absolute":
            return f"0x{self.offset:x}"
        b = f"&{self.base}" if self.kind == "symbol" else self.base
        return b if self.offset == 0 else f"{b}{'+' if self.offset > 0 else '-'}{abs(self.offset)}"


@dataclass
class AliasResult:
    kind: AliasKind
    reason: str

    @property
    def may_conflict(self) -> bool:
        return self.kind != AliasKind.NO_ALIAS


@dataclass
class MemInfo:
    """Resolved information about one memory instruction."""
    ins_id: str
    addr: AbsAddr
    size: int
    base_key: tuple          # syntactic base identity used for the "same base register" test

    def to_dict(self) -> dict:
        return {
            "ins_id": self.ins_id, "kind": self.addr.kind, "base": self.addr.base,
            "offset": self.addr.offset, "size": self.size, "address": self.addr.text(),
            "range": f"[{self.addr.text()}, +{self.size})",
            "base_key": "/".join(str(x) for x in self.base_key),
        }


class AddressAnalysis:
    """Resolves the address of every memory instruction in a sequence."""

    def __init__(self, seq: list[Instruction]):
        self.seq = seq
        self.by_id = {i.id: i for i in seq}
        self.rdefs = reaching_defs(seq)
        self._cache: dict[tuple[str, str], AbsAddr] = {}
        self.mem: dict[str, MemInfo] = {}
        for ins in seq:
            if ins.mem is not None:
                self.mem[ins.id] = self._resolve_mem(ins)

    def register_value(self, user: Instruction, reg: str, depth: int = 0) -> AbsAddr:
        key = (user.id, reg)
        if key in self._cache:
            return self._cache[key]
        d_id = self.rdefs.get(key)
        if d_id is None:
            val = AbsAddr("value", f"{reg}@in({user.block})", 0)
        else:
            val = self._value_of_def(self.by_id[d_id], depth)
        self._cache[key] = val
        return val

    def _value_of_def(self, d: Instruction, depth: int) -> AbsAddr:
        opaque = AbsAddr("value", f"{d.dest}@{d.id}", 0)
        if depth > 64:
            return opaque
        if d.opcode == "ADDR":
            return AbsAddr("symbol", d.symbol, d.immediates[0])
        if d.opcode == "MOV":
            if d.immediates:
                return AbsAddr("absolute", "", d.immediates[0])
            return self.register_value(d, d.sources[0], depth + 1)
        if d.opcode in ("ADD", "SUB") and d.immediates:
            base = self.register_value(d, d.sources[0], depth + 1)
            delta = d.immediates[0] if d.opcode == "ADD" else -d.immediates[0]
            return AbsAddr(base.kind, base.base, base.offset + delta)
        return opaque   # LOAD, MUL, reg+reg ADD, ...: unknown value

    def _resolve_mem(self, ins: Instruction) -> MemInfo:
        m = ins.mem
        if m.base_is_register:
            base = self.register_value(ins, m.base)
            addr = AbsAddr(base.kind, base.base, base.offset + m.offset)
            key = ("reg", m.base, self.rdefs.get((ins.id, m.base)) or f"in({ins.block})")
        else:
            addr = AbsAddr("symbol", m.base, m.offset)
            key = ("sym", m.base)
        return MemInfo(ins.id, addr, m.size, key)

    # ---- queries -------------------------------------------------------
    def distance(self, a_id: str, b_id: str) -> int | None:
        """Byte distance b - a if both addresses share a base, else None."""
        a, b = self.mem[a_id].addr, self.mem[b_id].addr
        if a.kind == b.kind and a.base == b.base and _exact(a) and _exact(b):
            return b.offset - a.offset
        return None

    def alias(self, a_id: str, b_id: str) -> AliasResult:
        return alias_query(self.mem[a_id], self.mem[b_id])


def _rng(p: AbsAddr, size: int) -> str:
    return f"{p.text()} ({size} B)"


def alias_query(a: MemInfo, b: MemInfo) -> AliasResult:
    pa, pb = a.addr, b.addr
    if pa.kind == "symbol" and pb.kind == "symbol" and pa.base != pb.base:
        if _in_bounds(pa, a.size) and _in_bounds(pb, b.size):
            return AliasResult(AliasKind.NO_ALIAS, f"different objects {pa.base} and {pb.base}, both accessed in bounds, never overlap")
        return AliasResult(AliasKind.MAY_ALIAS,
                           f"{_rng(pa, a.size)} or {_rng(pb, b.size)} lies outside its object "
                           f"(objects are at most {OBJECT_LIMIT} B), so it may reach the other object")
    if pa.kind == pb.kind and pa.base == pb.base and not (_exact(pa) and _exact(pb)):
        return AliasResult(AliasKind.MAY_ALIAS,
                           f"offsets {pa.offset} / {pb.offset} are too large to compare safely (64-bit wrap-around)")
    if pa.kind == pb.kind and pa.base == pb.base:
        lo_a, hi_a = pa.offset, pa.offset + a.size
        lo_b, hi_b = pb.offset, pb.offset + b.size
        what = "same object" if pa.kind == "symbol" else ("absolute addresses" if pa.kind == "absolute" else "same base pointer")
        if hi_a <= lo_b or hi_b <= lo_a:
            return AliasResult(AliasKind.NO_ALIAS, f"{what}, disjoint byte ranges {_rng(pa, a.size)} and {_rng(pb, b.size)}")
        if lo_a == lo_b and hi_a == hi_b:
            return AliasResult(AliasKind.MUST_ALIAS, f"{what}, identical bytes {_rng(pa, a.size)}")
        return AliasResult(AliasKind.PARTIAL_ALIAS, f"{what}, overlapping byte ranges {_rng(pa, a.size)} and {_rng(pb, b.size)}")
    return AliasResult(
        AliasKind.MAY_ALIAS,
        f"cannot relate {pa.text()} and {pb.text()} (unknown pointer) - conservatively assume they may overlap")
