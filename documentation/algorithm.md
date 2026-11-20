# The CAIF rearrangement algorithm (as implemented)

This file describes exactly what `backend/core/` does. Where the paper does not
specify a detail, the choice made here is marked **[our choice]**.

## 1. Definitions

* **Memory operation**: a `LOAD` or `STORE`.
* **Abstract address** of an operand `[BASE+off]`: `(kind, base, offset)`.
  * `symbol`: BASE is a symbol such as `A`. Distinct symbols are distinct objects.
  * `value`: BASE is a register holding an opaque pointer, identified by its reaching
    definition, e.g. `R3@in(B0)` (live into block B0) or `R5@I4` (produced by I4).
  * `absolute`: the register was set by `MOV Rd, imm`.

  Resolution follows `ADDR`, `MOV`, `ADD/SUB Rd, Rs, imm` back to a base and
  accumulates the constant offset. **Soundness limits (audit fix):** offsets beyond ±2^40 are
  not trusted (64-bit wrap-around), and two different symbols are `NO_ALIAS` only if both
  accesses are in bounds, i.e. inside `[0, 16 MiB)` of their object. Otherwise the answer is
  `MAY_ALIAS`. This is the educational analogue of LLVM's
  `stripAndAccumulateConstantOffsets` (paper Sec. IV-A1).
* **Distance** between two accesses: `offset_b - offset_a` if they share `(kind, base)`,
  otherwise *unknown*.
* **Span**: `max(end_a, end_b) - min(start_a, start_b)` in bytes.

## 2. Compatibility of a pair (HEAD at position h, TAIL at position t, h < t)

All of the following must hold (`fusion_detector.check_pair`):

| Condition | Rule |
|---|---|
| `same_operation` | both LOAD or both STORE, and that pair type is enabled |
| `same_basic_block` | same block (CAIF never crosses blocks, paper Sec. IV-A4) |
| `provable_distance` | the distance is known (same base object / pointer value) |
| `same_base_register` | targets ConsSBR/ConsSBR64 only: same syntactic base *and* same register value |
| `non_overlapping` | the accessed byte ranges are disjoint |
| `contiguous` | target ConsSBR only: one access ends where the other starts |
| `within_window` | `span <= window_bytes` (default **64**). **[our interpretation]** The paper's middle end requires the two accesses to lie "within a 64-byte range". Its back-end DAG mutation compares *offsets* (difference <= 64). Requiring the whole *span of bytes touched* to fit in 64 B is stricter, and closer to "both accesses fall in one 64-byte region". |
| `same_size` | only if configured |
| `distinct_destinations` | loads only: they write different registers |
| `tail_independent_of_head` | the TAIL's use-def chain (within `[h..t]`) does not contain the HEAD |
| `instruction_distance` | only if configured: `t - h <= limit` (the paper scans the whole block) |

Fusion class of a compatible pair: `SBR-contiguous`, `SBR-window` (same base register,
gap allowed) or `DBR` (different base registers, distance provable). These mirror the
paper's Consecutive-SBR-contiguous / -SBR-64bytes / -DBR categories (Sec. III-A).

## 3. Dependence graph (`dependency_analyzer`)

Edges `src -> dst` (src must stay first) inside each basic block:

* **RAW / ADDRESS**: dst reads a register whose reaching definition is src
  (ADDRESS when the register is dst's memory base).
* **WAR**: dst writes a register read by src since that register's previous write.
* **WAW**: consecutive writers of the same register.
* **MEMORY**: for every pair of memory accesses with at least one write whose alias
  result is not `NO_ALIAS` (MEM-RAW / MEM-WAR / MEM-WAW). A `CALL` is ordered against every
  memory access.

Register edges link only *nearest* conflicting instructions. Their transitive closure
gives every ordering constraint.

## 4. Catalyst analysis and the move (`catalyst_analyzer`)

```
catalyst = seq[h+1 .. t-1]
chain    = transitive RAW predecessors of TAIL, restricted to seq[h .. t]
if HEAD in chain:                        reject   # paper: "use-def chain of the Tail includes the Head"
moved    = chain ∪ {TAIL}
stays    = {HEAD} ∪ (catalyst \ chain)
violations = { e in edges : e.src in stays and e.dst in moved and e != (HEAD -> TAIL) }
if violations or moved ∩ locked:         reject   # locked = already in a formed pair [our choice]
new window order = chain (original order) + [HEAD, TAIL] + (catalyst \ chain) (original order)
```

**Why this is safe.** The new order changes the relative order of exactly these pairs:
(x in stays, y in moved, where x was before y), apart from HEAD/TAIL. If no dependence edge
connects such a pair, the transitive closure is unaffected, so every RAW keeps its reaching
definition, no anti/output hazard flips, and no possibly-aliasing memory access with a store
is reordered. This one rule covers all the alias checks listed in the paper's Figures 4 and 5:

* TAIL load vs catalyst stores: MEMORY edge store -> TAIL.
* TAIL store vs catalyst loads/stores: MEMORY edges -> TAIL.
* Loads in the chain vs catalyst stores and the HEAD store: MEMORY edges -> chain.

It also adds register WAR/WAW checks. In SSA IR those hazards cannot exist, but in a
register ISA they can (e.g. sample 10, where the tail overwrites R2 before a catalyst
instruction has read it).

## 5. Driver (`optimizer.optimize`)

```
seq = original; locked = {}; pairs = []
# Phase A [our choice]: claim pairs that are already consecutive, left to right
for i: if compatible(seq[i], seq[i+1]) and both unlocked: lock both
# Phase B: repeat until no new pair is formed
repeat:
  for each unlocked memory op HEAD, in current order:
     graph = dependences(seq)
     for each later TAIL in the same block (same kind, unlocked), in order:
        if not compatible(HEAD, TAIL): continue
        if TAIL is adjacent: lock pair; break
        report = analyze_catalyst(HEAD, TAIL)
        if report.safe:
            new = apply move; static re-check (validator.check_order)
            seq = new; lock pair; break
        else: record rejection (once per pair); try the next TAIL
until no change
```

Each instruction belongs to at most one pair, which matches a decoder that fuses an
instruction with at most one neighbour.

## 6. Validation (`validator`): re-derived from the original program

1. **Permutation**: same IDs, none lost, duplicated or added.
2. **Instructions unchanged**: same text and block for each ID.
3. **Basic blocks**: block order preserved; each branch still ends its block.
4. **Commutation (Bernstein) test**: for *every* pair whose relative order was inverted,
   check that neither writes a register the other reads or writes, that there is no CALL
   involved with a memory access, and that two accesses including a store are `NO_ALIAS`.
   If all inverted pairs commute, the new order can be reached by adjacent swaps of
   independent instructions, so the modelled semantics are preserved. This is a different
   formulation from the optimizer's edge test, so the two cross-check each other. **However, it uses the
   same alias analysis as the optimizer.** If the alias analysis were wrong, this check would agree with the
   wrong answer. `test_audit.py::test_mutant_alias_analysis_is_caught_by_differential_execution` shows exactly
   this, and shows that step 5 still catches it.
5. **Differential execution** (reference interpreter, independent of the alias analysis): both
   versions run under these register set-ups:
   * all unknown pointers in separate regions (no aliasing);
   * all unknown pointers equal (full aliasing);
   * **targeted aliasing**: each unknown pointer is aimed at every address another instruction
     touched, exactly and shifted by ±4 bytes for partial overlap (up to 60 such set-ups);
   * 8 random set-ups.

   A `CALL` overwrites every address the programs touch, so moving a memory access across a
   call changes the result. Final registers, memory and CALL observations must be identical.
   This is testing evidence, not a proof. Pointers loaded from memory are not targeted.

If validation fails, the pipeline discards the optimized sequence and reports
`REJECTED_BY_VALIDATOR`.

## 7. Fusion opportunity detection

The final sequence is scanned left to right. Each adjacent compatible pair is counted and
both instructions are skipped (greedy, non-overlapping). Then
`additional = after - before`, and the percentage change is reported only when
`before > 0`.
