"""Stage 7 - Independent validation of a transformed sequence.

The validator does NOT trust the optimizer. Given the ORIGINAL program and a
proposed order it checks, from scratch:

1. Permutation   - same instruction IDs, none lost, none duplicated, none new.
2. Basic blocks  - every instruction stays in its block, blocks keep their
                   order, each branch remains the last instruction of its block.
3. Dependences   - Bernstein-style commutation test: every pair of
                   instructions whose relative order was *inverted* must be
                   independent (no register written by one and read/written by
                   the other; no possibly-overlapping memory accesses with a
                   write; nothing crosses a CALL). If every inverted pair
                   commutes, the new order can be reached by swapping
                   independent neighbours, so the modelled semantics are
                   unchanged. This is a different formulation from the
                   optimizer's edge-based check, so the two cross-check each other.
4. Differential execution - both programs are run in a small interpreter
                   under several memory/aliasing scenarios (including one
                   where every unknown pointer aliases the same address) and
                   the final registers, memory and CALL observations must match.
                   This is testing, not proof: it can find bugs, not prove
                   their absence.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

from .alias_analyzer import OBJECT_LIMIT, AddressAnalysis
from .instruction import FLAGS, Instruction, MemKind

MASK = (1 << 64) - 1
SYMBOL_SPACING = 0x1000_0000          # > OBJECT_LIMIT, so in-bounds objects never overlap
assert SYMBOL_SPACING > OBJECT_LIMIT


@dataclass
class Check:
    name: str
    passed: bool
    details: str


@dataclass
class ValidationResult:
    valid: bool
    checks: list[Check] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"valid": self.valid, "checks": [c.__dict__ for c in self.checks], "errors": self.errors}


# ----------------------------------------------------------------------------
# Static checks
# ----------------------------------------------------------------------------
def _reg_reads(i: Instruction) -> set[str]:
    return set(i.sources)


def _reg_writes(i: Instruction) -> set[str]:
    return {i.dest} if i.dest else set()


def _commute(a: Instruction, b: Instruction, addr: AddressAnalysis) -> str | None:
    """Return None if a and b can be swapped, else the reason they cannot."""
    for x, y in ((a, b), (b, a)):
        clash = _reg_writes(x) & (_reg_reads(y) | _reg_writes(y))
        if clash:
            return f"{x.id} writes {', '.join(sorted(clash))} which {y.id} uses"
    if a.mem_kind == MemKind.NONE or b.mem_kind == MemKind.NONE:
        return None
    if MemKind.READ_WRITE in (a.mem_kind, b.mem_kind):
        return f"{a.id} and {b.id}: memory access reordered across a CALL"
    if a.mem_kind == MemKind.READ and b.mem_kind == MemKind.READ:
        return None
    res = addr.alias(a.id, b.id)
    if res.may_conflict:
        return f"{a.id} and {b.id} may access the same memory ({res.kind.value}) and one is a store"
    return None


def check_order(original: list[Instruction], new: list[Instruction]) -> ValidationResult:
    checks: list[Check] = []
    errors: list[str] = []
    orig_ids = [i.id for i in original]
    new_ids = [i.id for i in new]

    # 1. permutation
    missing = sorted(set(orig_ids) - set(new_ids))
    extra = sorted(set(new_ids) - set(orig_ids))
    dups = sorted({x for x in new_ids if new_ids.count(x) > 1})
    perm_ok = not (missing or extra or dups) and len(new_ids) == len(orig_ids)
    msg = "all {} instructions present exactly once".format(len(orig_ids)) if perm_ok else \
        f"missing={missing} extra={extra} duplicated={dups}"
    checks.append(Check("permutation", perm_ok, msg))
    if not perm_ok:
        errors.append("Instruction set changed: " + msg)
        return ValidationResult(False, checks, errors)

    orig_by_id = {i.id: i for i in original}
    # 2. identity of instructions (no rewritten operands)
    changed = [n.id for n in new if n.text != orig_by_id[n.id].text or n.block != orig_by_id[n.id].block]
    checks.append(Check("instructions_unchanged", not changed,
                        "operands and block of every instruction are unchanged" if not changed else f"modified: {changed}"))
    if changed:
        errors.append(f"Instructions were modified: {changed}")

    # 3. basic block structure
    def block_seq(ids):
        out = []
        for x in ids:
            b = orig_by_id[x].block
            if not out or out[-1] != b:
                out.append(b)
        return out
    ob, nb = block_seq(orig_ids), block_seq(new_ids)
    blocks_ok = ob == nb
    term_ok = True
    for k, x in enumerate(new_ids):
        ins = orig_by_id[x]
        if ins.is_terminator and k + 1 < len(new_ids) and orig_by_id[new_ids[k + 1]].block == ins.block:
            term_ok = False
            errors.append(f"Branch {x} is no longer the last instruction of block {ins.block}")
    checks.append(Check("basic_blocks", blocks_ok and term_ok,
                        "no instruction crossed a block boundary; branches still end their blocks" if blocks_ok and term_ok
                        else f"block order {ob} -> {nb}"))
    if not blocks_ok:
        errors.append("An instruction was moved across a basic-block boundary")

    # 4. inverted pairs must commute
    addr = AddressAnalysis(original)
    pos = {x: k for k, x in enumerate(new_ids)}
    inverted = 0
    bad = []
    for a_i in range(len(original)):
        for b_i in range(a_i + 1, len(original)):
            a, b = original[a_i], original[b_i]
            if pos[a.id] > pos[b.id]:
                inverted += 1
                why = _commute(a, b, addr)
                if why:
                    bad.append(why)
    checks.append(Check("dependences_preserved", not bad,
                        f"{inverted} reordered instruction pair(s), all independent" if not bad else "; ".join(bad)))
    errors += [f"Dependence violated: {b}" for b in bad]
    return ValidationResult(not errors, checks, errors)


# ----------------------------------------------------------------------------
# Differential execution
# ----------------------------------------------------------------------------
class Interpreter:
    """Reference interpreter for the educational ISA (straight-line semantics).

    * Registers are 64-bit and wrap around; memory is byte-addressed, little-endian,
      and every address is taken modulo 2**64 (reads and writes alike).
    * Uninitialised memory holds a deterministic pseudo-random byte per address.
    * Branches are no-ops (fall through): CAIF only reorders inside a basic block,
      so running every block in order exercises every reordering.
    * CALL models "may read/write any memory": it records a digest of the memory it
      can see, then overwrites every address in `clobber` (the addresses the
      program touches). A memory access moved across a CALL therefore changes
      what is read or what survives - so such a bug becomes observable.
      CALL does not modify registers (simplification: no caller-saved registers).
    """

    def __init__(self, symbol_bases: dict[str, int], init_regs: dict[str, int], seed: int,
                 clobber: frozenset[int] = frozenset()):
        self.sym = symbol_bases
        self.regs: dict[str, int] = dict(init_regs)
        self.mem: dict[int, int] = {}
        self.seed = seed
        self.clobber = clobber
        self.calls: list[tuple[str, str]] = []
        self.trace: list[tuple[str, int, int]] = []    # (instruction id, address, size) of each access

    def _init_byte(self, a: int) -> int:
        return ((a * 2654435761 + self.seed * 40503) >> 5) & 0xFF

    def _byte(self, a: int) -> int:
        return self.mem.get(a, self._init_byte(a))

    def _read(self, a: int, size: int) -> int:
        v = 0
        for k in range(size):
            v |= self._byte((a + k) & MASK) << (8 * k)
        return v

    def _write(self, a: int, size: int, v: int) -> None:
        for k in range(size):
            self.mem[(a + k) & MASK] = (v >> (8 * k)) & 0xFF

    def _reg(self, r: str) -> int:
        return self.regs.get(r, 0)

    def _addr(self, i: Instruction) -> int:
        m = i.mem
        base = self._reg(m.base) if m.base_is_register else self.sym[m.base]
        return (base + m.offset) & MASK

    def run(self, seq: list[Instruction]) -> "Interpreter":
        for i in seq:
            op = i.opcode
            if op == "LOAD":
                a = self._addr(i)
                self.trace.append((i.id, a, i.mem.size))
                self.regs[i.dest] = self._read(a, i.mem.size)
            elif op == "STORE":
                a = self._addr(i)
                self.trace.append((i.id, a, i.mem.size))
                self._write(a, i.mem.size, self._reg(i.sources[-1]))
            elif op in ("ADD", "SUB", "MUL"):
                x = self._reg(i.sources[0])
                y = self._reg(i.sources[1]) if len(i.sources) > 1 else i.immediates[0]
                self.regs[i.dest] = (x + y if op == "ADD" else x - y if op == "SUB" else x * y) & MASK
            elif op == "MOV":
                self.regs[i.dest] = (self._reg(i.sources[0]) if i.sources else i.immediates[0]) & MASK
            elif op == "ADDR":
                self.regs[i.dest] = (self.sym[i.symbol] + i.immediates[0]) & MASK
            elif op == "CMP":
                x = self._reg(i.sources[0])
                y = self._reg(i.sources[1]) if len(i.sources) > 1 else i.immediates[0] & MASK
                self.regs[FLAGS] = 0 if x == y else (1 if x > y else 2)
            elif op == "CALL":
                n = len(self.calls) + 1
                seen = sorted((a, self._byte(a)) for a in self.clobber | set(self.mem))
                self.calls.append((i.symbol, hashlib.sha1(repr(seen).encode()).hexdigest()[:12]))
                for a in self.clobber:                       # the callee writes "everywhere"
                    self.mem[a] = (self._byte(a) * 31 + 17 * n + 1) & 0xFF
            # BR/BEQ/BNE/NOP: no state change in straight-line execution
        return self

    def state(self) -> tuple:
        return (tuple(sorted(self.regs.items())), tuple(sorted(self.mem.items())), tuple(self.calls))


def _live_in_registers(seq: list[Instruction]) -> list[str]:
    written, live = set(), []
    for i in seq:
        for r in i.sources:
            if r not in written and r not in live and r != FLAGS:
                live.append(r)
        if i.dest:
            written.add(i.dest)
    return live


def _bytes_of(trace) -> set[int]:
    return {(a + k) & MASK for _id, a, size in trace for k in range(size)}


def _scenarios(original, sym_bases, live, rng, max_targeted: int, random_trials: int):
    """Register set-ups that deliberately create aliasing between unknown pointers
    and every other access. Returns a list of (label, regs)."""
    disjoint = {r: 0x9000_0000 + 0x100_0000 * k for k, r in enumerate(live)}
    out = [("no aliasing (pointers in separate regions)", dict(disjoint))]
    first = next(iter(sym_bases.values()), 0x5000_0000)
    out.append(("full aliasing (every unknown pointer = same address)", {r: first for r in live}))

    # Accesses seen in the disjoint run tell us where every instruction touches memory.
    probe = Interpreter(sym_bases, disjoint, 0).run(original).trace
    live_set = set(live)
    by_id = {i.id: i for i in original}
    pointer_uses = sorted({(by_id[iid].mem.base, by_id[iid].mem.offset) for iid, _a, _s in probe
                           if by_id[iid].mem.base_is_register and by_id[iid].mem.base in live_set})
    targets = sorted({a for _iid, a, _s in probe})
    targeted = []
    for reg, off in pointer_uses:
        for t in targets:
            for delta in (0, -4, 4):
                regs = dict(disjoint)
                regs[reg] = (t - off + delta) & MASK
                if regs[reg] != disjoint[reg]:
                    targeted.append((f"{reg} aimed at address 0x{t:x}{delta:+d}", regs))
    rng.shuffle(targeted)
    out += targeted[:max_targeted]

    targets_rand = list(sym_bases.values()) or [first]
    for k in range(random_trials):
        regs = {}
        for r in live:
            if rng.random() < 0.6:
                regs[r] = rng.choice(targets_rand) + rng.choice([0, 0, 4, 8, 16, 24, 32])
            else:
                regs[r] = rng.randrange(0, 1 << 16)
        out.append((f"random #{k + 1}", regs))
    return out


def differential_test(original: list[Instruction], new: list[Instruction], seed: int = 1234,
                      max_targeted: int = 60, random_trials: int = 8) -> Check:
    """Run original and new programs on the reference interpreter under many register
    set-ups and compare final registers, memory and CALL observations.
    This is finite testing: it can expose a wrong transformation, never prove one correct."""
    symbols = sorted({i.mem.base for i in original if i.mem and not i.mem.base_is_register} |
                     {i.symbol for i in original if i.opcode == "ADDR"})
    # Objects are placed further apart than OBJECT_LIMIT, matching the alias model.
    sym_bases = {s: SYMBOL_SPACING * (k + 1) for k, s in enumerate(symbols)}
    live = _live_in_registers(original)
    rng = random.Random(seed)
    scenarios = _scenarios(original, sym_bases, live, rng, max_targeted, random_trials)
    for n, (label, regs) in enumerate(scenarios):
        # Addresses either program touches in this scenario -> what a CALL may overwrite.
        touched = frozenset(_bytes_of(Interpreter(sym_bases, regs, seed + n).run(original).trace) |
                            _bytes_of(Interpreter(sym_bases, regs, seed + n).run(new).trace))
        a = Interpreter(sym_bases, regs, seed + n, touched).run(original).state()
        b = Interpreter(sym_bases, regs, seed + n, touched).run(new).state()
        if a != b:
            diff = []
            ra, rb = dict(a[0]), dict(b[0])
            diff += [f"{r}: {ra.get(r)} vs {rb.get(r)}" for r in sorted(set(ra) | set(rb)) if ra.get(r) != rb.get(r)][:4]
            if a[1] != b[1]:
                diff.append("memory contents differ")
            if a[2] != b[2]:
                diff.append("CALL observations differ")
            return Check("differential_execution", False,
                         f"scenario '{label}': final state differs ({'; '.join(diff)})")
    return Check("differential_execution", True,
                 f"original and optimized programs produced identical registers, memory and CALL observations "
                 f"in {len(scenarios)} scenarios (no aliasing, full aliasing, pointers deliberately aimed at "
                 f"every accessed address, random). This is testing evidence, not a proof.")


def validate(original: list[Instruction], new: list[Instruction], run_differential: bool = True) -> ValidationResult:
    res = check_order(original, new)
    if res.valid and run_differential:
        d = differential_test(original, new)
        res.checks.append(d)
        if not d.passed:
            res.errors.append(d.details)
            res.valid = False
    return res
