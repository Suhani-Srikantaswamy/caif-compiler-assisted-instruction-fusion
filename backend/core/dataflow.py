"""Reaching definitions inside a basic block (use-def information).

For every (instruction, register it reads) we find the instruction in the
same basic block that last wrote that register before it. If there is no
such writer, the value comes from outside the block ("live-in").

LLVM IR is in SSA form, so every value has exactly one definition and the
use-def chain is explicit. Our register-level ISA is not SSA, so we
reconstruct the same information with this simple backward scan.
"""
from __future__ import annotations

from .instruction import Instruction

LIVE_IN = None


def reaching_defs(seq: list[Instruction]) -> dict[tuple[str, str], str | None]:
    """Map (user_id, register) -> defining instruction id (or None = live-in to the block)."""
    result: dict[tuple[str, str], str | None] = {}
    last_def: dict[str, str] = {}
    current_block = None
    for ins in seq:
        if ins.block != current_block:
            current_block = ins.block
            last_def = {}
        for r in ins.sources:
            result[(ins.id, r)] = last_def.get(r, LIVE_IN)
        if ins.dest:
            last_def[ins.dest] = ins.id
    return result


def use_def_chain(tail: Instruction, seq: list[Instruction], within_ids: set[str] | None = None) -> list[str]:
    """Transitive register use-def chain of `tail`.

    Returns the IDs of every instruction whose result `tail` (transitively)
    needs. If `within_ids` is given, the walk only follows definitions in
    that set (e.g. the catalyst), and stops at instructions outside it.
    """
    rdefs = reaching_defs(seq)
    by_id = {i.id: i for i in seq}
    chain: list[str] = []
    seen: set[str] = set()
    work = [tail.id]
    while work:
        uid = work.pop()
        for r in by_id[uid].sources:
            d = rdefs.get((uid, r))
            if d is None or d in seen:
                continue
            if within_ids is not None and d not in within_ids:
                continue
            seen.add(d)
            chain.append(d)
            work.append(d)
    order = {i.id: k for k, i in enumerate(seq)}
    return sorted(chain, key=order.__getitem__)
