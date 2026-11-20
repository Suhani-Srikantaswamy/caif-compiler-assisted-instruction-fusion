# Technical audit report

Scope: every backend module (`core/`, `experiments/`, `examples/`, `main.py`), the frontend
pages and components, the tests and the paper references. Each finding was confirmed by
running an adversarial program against the code before it was fixed. The regression tests
are in `backend/tests/test_audit.py`, and those marked `BUG` failed before the fix.

## Execution flow (as traced in the code)

`POST /api/optimize` → `pipeline.run_caif`:

1. `parser.parse_program`: text → `Instruction` objects, basic blocks and errors.
2. `alias_analyzer.AddressAnalysis`: reaching definitions (`dataflow.reaching_defs`) →
   abstract address `(kind, base, offset)` for each memory operand.
3. `dependency_analyzer.build_dependency_graph`: RAW / ADDRESS / WAR / WAW edges between the
   nearest conflicting instructions; MEMORY edges between every pair of accesses with at
   least one write that is not `NO_ALIAS`; CALL ordered against every memory access. Edges
   stay inside one block.
4. `fusion_detector.find_candidate_pairs`: per-condition compatibility (for display).
5. `optimizer.optimize`: Phase A claims pairs that are already adjacent. Phase B loops over
   head → tail candidates, calling `check_pair` and then `catalyst_analyzer.analyze_catalyst`
   (catalyst, use-def chain, blocking edges). If safe, it applies the move and re-checks it
   with `static_recheck`. It repeats until no new pair forms.
6. `validator.validate(original, optimized)`: permutation, unchanged instructions, block
   structure, pairwise commutation of every inverted pair, then differential execution. On
   failure the pipeline keeps the original program.
7. `fusion_detector.consecutive_opportunities` on the original and final sequences →
   `metrics.compute_metrics`.

## Findings

| # | Severity | Where | Finding | Status |
|---|---|---|---|---|
| C1 | **Critical** | `alias_analyzer.alias_query`, `AddressAnalysis.distance` | Offsets were compared as unbounded integers, but registers wrap around modulo 2^64. `R3+2^64` was judged `NO_ALIAS` with `R3`, although it is the same address. The optimizer therefore **proposed an unsafe move**. The static validator agreed, because it shares the alias analysis. Only differential execution caught it, so the final output stayed safe. | Fixed: offsets beyond ±2^40 → `MAY_ALIAS` / distance unknown |
| C2 | **Critical** | `alias_analyzer.alias_query` | "Different symbols never overlap" was applied even to out-of-bounds accesses. `ADDR R3, A, 2^28` points into B in the interpreter's layout, yet was `NO_ALIAS` with B. Same consequence as C1. | Fixed: objects are at most `OBJECT_LIMIT` = 16 MiB; `NO_ALIAS` across symbols only if both accesses are in bounds. The interpreter places objects further apart than this (asserted). |
| M1 | Major | `parser.parse_program` (block naming) | The first block was always auto-named `B0`, even if the user defined a label `B0`. Two different blocks then shared a name, and the dependency analysis (which groups by name) merged them. A program with no transformation at all was then rejected by the validator. | Fixed: `fresh_block_name()` never reuses a label |
| M2 | Major | `validator.Interpreter` (CALL) | The interpreter's CALL wrote only to a hidden address, so a load or store moved across a CALL produced identical results: the differential check could not see the most important CALL bug. | Fixed: CALL records the memory it can see, then overwrites every address either program touches |
| M3 | Major | `validator.differential_test` | Unknown pointers were only "all equal", "all disjoint" or random. Aliasing between two unknown pointers at different offsets (`[R11+0]` vs `[R10+8]`) was never produced, so such a wrong reorder went undetected. | Fixed: **targeted scenarios** aim each unknown pointer at every address another instruction touches, exactly and ±4 bytes (up to 60 set-ups) |
| Mo1 | Moderate | UI (`OptimizationPage`, `Overview`, `ui.tsx`, `AboutPage`), README, docs | The validator was called "independent". Its static half uses the *same* alias analysis as the optimizer, so it cannot detect an alias-analysis bug (see C1/C2). Only differential execution is independent. | Wording corrected. A mutation test now demonstrates the distinction. |
| Mo2 | Moderate | `validator.Interpreter._read` | Read addresses were not reduced modulo 2^64, while writes were. This was inconsistent near the top of the address space. | Fixed |
| Mi1 | Minor | `Overview.tsx` | "1.94% of memory ops were fused by the simplest hardware" overstated the paper. Fig. 1 / Sec. III-A say 1.94% *fall in the Consecutive-SBR-contiguous category* under Helios. | Reworded |
| Mi2 | Minor | README, `limitations.md`, `algorithm.md` | Stale counts (113 tests, "12 scenarios"). | Updated |
| Mi3 | Minor | `algorithm.md`, `limitations.md` | The 64-byte rule (`span <= 64`) was presented as "the paper's rule". The paper's middle end says "within a 64-byte range", while its back-end DAG mutation compares offset difference <= 64. Ours is a stricter interpretation. | Documented as our interpretation |
| Mi4 | Minor | model | CALL does not clobber registers in this model, so a register-only instruction may cross a CALL. That is legal here, not on real hardware. | Documented |

Fixed before this audit (same session): the Results page crashed on reloaded experiment runs
because the `files` field was not stored. The sample list was not reloaded when the
backend started late.

## Checked and found correct (no change needed)

* **RAW / WAR / WAW**: edges link the nearest conflicting instructions, in program order
  (src before dst). Every register conflict between two instructions has a path of such
  edges (argued in `algorithm.md` §3–4), so checking direct edges in the move is enough.
* **Move legality** (`analyze_catalyst`): a reordered pair is always (stays-member, moved-member).
  Any dependence path between them must contain a direct edge from the stays set to the moved
  set, and every such edge is checked. HEAD → TAIL is allowed because their order is kept.
* **Memory dependences**: every load/store pair with at least one store, and every access
  against a CALL, gets an edge unless `NO_ALIAS`. Two loads never conflict.
* **Use-def chain**: the transitive RAW predecessors of the TAIL within `[HEAD..TAIL]`. A chain
  containing the HEAD is rejected (paper rule). Stores cannot appear in a register chain;
  memory-carried dependences on a store are rejected through MEMORY edges, which matches the
  paper's "if the use-def chain requires a store, we avoid reordering".
* **Basic blocks**: no edges and no pairs across blocks. The window between HEAD and TAIL lies in
  one block, and branches stay last (validator checks this).
* **Multiple pairs / locking**: formed pairs are never split (fuzz invariant: every formed
  pair is adjacent in the final sequence).
* **Opportunity counts**: the greedy left-to-right scan on adjacent pairs gives a maximum
  matching. It is never below the optimizer's pair count, and never below the original count
  (checked over 3,000+ random runs).
* **Percentages**: `None` when the denominator is 0. Experiment totals are sums of per-sample
  rows (tested). Results change when the inputs change (tested), so nothing is hardcoded.
* **Optimizer timing** is labelled as compile-time cost everywhere, never as a speedup.
* **Paper numbers** in `frontend/src/data/paperResults.ts` were re-checked against the paper
  text (Sec. III-A, VI-A, VI-B, VI-D, VI-E, abstract). They are shown only in their own
  labelled section.

## Paper mechanisms vs educational simplifications

| Paper mechanism | Implemented? |
|---|---|
| Head/tail scan within a basic block, same kind (load+load, store+store) | Yes |
| 64-byte range condition | Yes, as `span <= 64` (stricter interpretation) |
| Common base via `stripAndAccumulateConstantOffsets` | Educational analogue (constant offsets through ADDR/MOV/ADD-imm) |
| SCEV distance when no common base | No (no loops / induction variables) |
| Catalyst queue | Yes |
| Use-def chain hoisted above the head, tail placed after the head | Yes, same transformation |
| Reject if the chain contains the head | Yes |
| Alias checks of Figs. 4 and 5 (tail vs catalyst, chain loads vs catalyst/head stores) | Yes, generalised as one edge rule |
| Register WAR/WAW checks | Extra (needed because the ISA is not SSA) |
| LLVM AA + SVF Andersen / flow-sensitive + GraphAA | Simplified conservative symbolic analysis |
| Reordering across function calls (GraphAA) | No: CALL is a memory barrier |
| Dynamic loop unrolling ×2 | No |
| Pseudo-instructions + DAG mutations in the back end | No back end; real LLVM clustering shown in `llvm_demo/` |
| Cycle-level evaluation, energy, MPKI | No: only potential opportunity counts |

## Tests added in the audit (`tests/test_audit.py`, 37 tests)

Alias soundness (wrap-around, out-of-bounds, negative offsets, the exact object-limit
boundary, partial overlap of different sizes) · basic-block naming and independent per-block
optimization · 6 unsafe-move programs (MEM-WAR / MEM-RAW partial / chain load / head→chain WAR /
store across CALL, plus a ConsSBR partial-WAW case) · 7 wrong orders that differential
execution must detect · **mutation tests**: the optimizer without its legality check
(4 programs) and a broken alias analysis shared with the static validator (2 programs) must
both end in `REJECTED_BY_VALIDATOR` · a 250-program × 3-target fuzz with invariants (valid,
count monotone, formed pairs adjacent, ≥ 30 programs actually optimized) · experiment
aggregation and not-hardcoded checks.
