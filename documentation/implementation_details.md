# Implementation details

## The educational ISA

| Syntax | Category | Reads | Writes |
|---|---|---|---|
| `LOAD[.n] Rd, [BASE±off]` | LOAD | base reg (if register) | Rd; memory read of n bytes |
| `STORE[.n] [BASE±off], Rs` | STORE | base reg, Rs | memory write of n bytes |
| `ADD/SUB/MUL Rd, Rs, Rt\|imm` | ARITH | Rs, Rt | Rd |
| `MOV Rd, Rs\|imm` | MOVE | Rs | Rd |
| `ADDR Rd, SYM[, off]` | ADDRESS | – | Rd = &SYM + off |
| `CMP Rs, Rt\|imm` | COMPARE | Rs, Rt | FLAGS |
| `BR/BEQ/BNE label` | BRANCH (ends block) | FLAGS (conditional) | – |
| `CALL f` | CALL | – | may read/write any memory |
| `NOP` | OTHER | – | – |

* Registers are `R0`–`R31`, and `FLAGS` is implicit. The default access size is 8 bytes and
  can be changed per instruction with the `.1 .2 .4 .8` suffix.
* `ID: instr` gives an instruction an explicit ID (`L1:`, `S2:`, as in the paper's figures).
  A line containing only `name:` starts a new basic block. Unnamed instructions get
  `I1, I2, …`, skipping IDs the user has already taken.
* `;` and `//` start comments.
* Symbols are distinct objects, so a negative offset from a symbol is rejected.

## Parser error handling

Every line is checked. Each error carries a line number and a message, and valid lines are
still parsed, so the UI can mark several errors at once. Detected errors: invalid opcode,
missing or extra operands, invalid register (`R99`, `X1`), memory syntax (`A+0`, `[A+0`),
invalid offset (`[A+x]`, `[A+4+4]`, `[A-8]`, out of range), invalid size suffix, suffix on a
non-memory opcode, duplicate instruction ID, duplicate label, undefined branch target, and
empty program.

## Backend

* `core/` uses only the Python standard library (no NumPy needed).
* The analyses are recomputed for each attempt. With n instructions, building the graph is
  O(n²) because of the memory pairs. The demo programs are tiny, and the measured optimizer
  time per sample is well under 1 ms (see `results.md`).
* `pipeline.run_caif` measures analysis, optimizer and validation time separately with
  `time.perf_counter`. The experiment runner reports the **median of 25 optimizer runs**.
* The results are deterministic. There is no randomness except the seeded differential
  tester, and the tests check that two runs give identical output.

## Frontend

* `state/AppState.tsx` holds the source, the configuration and the last `/api/optimize`
  result. Every page reads from it. A banner warns when the editor changed after the last
  run.
* `graphs/DependencyGraph.tsx` (React Flow) uses a layered layout from `graphs/layout.ts`:
  row = program position, column = longest dependence path. Edge colour shows the
  dependence type, MEMORY edges are dashed, and edges that block the selected pair are
  animated in red. Clicking a node dims everything that is not a neighbour and opens the
  inspector.
* `lib/roles.ts` turns a catalyst report into HEAD / TAIL / CATALYST / REQUIRED / BLOCKED /
  FUSION roles. The same colours are used on every page.
* **Dark theme:** the app is always dark. `tailwind.config.js` inverts every colour scale
  (50 ↔ 950, 100 ↔ 900, …), so the components' ordinary utility classes (`bg-slate-50`
  page, `bg-slate-100` cards, `bg-blue-100 text-blue-800` chips) render as dark surfaces with
  light text. Hex colours used by React Flow and Recharts are set to dark values directly,
  and React Flow runs with `colorMode="dark"`.
* `charts/Charts.tsx` (Recharts) draws thin rounded bars from a validated dark-mode
  categorical palette (blue, orange, aqua, yellow, in fixed order), with tooltips and
  legends. Every chart has a table next to it.
* The paper's reported numbers live in `data/paperResults.ts`, with section references. They
  appear only in their own clearly labelled section.

## Tests

| Suite | File | Covers |
|---|---|---|
| Pytest | `test_parser.py` | every opcode, representation fields, blocks, 17 invalid inputs, duplicate IDs |
| | `test_dependencies.py` | RAW, ADDRESS, WAR, WAW, MEM-RAW/WAR/WAW, CALL, block isolation, alias kinds |
| | `test_fusion.py` | window boundary (64 vs 65), sizes, overlap, SBR/DBR per target, distance limit |
| | `test_optimizer.py` | catalyst roles, safe moves, chain hoisting, 7 rejection kinds, multiple pairs, block restriction, determinism, all 13 samples vs their specification |
| | `test_validator.py` | detects lost/duplicate/RAW/memory/block/CALL violations; **fuzz test: 300 random programs × 2 targets must always validate** |
| | `test_api.py` | every endpoint, 422 handling, experiment persistence and path safety |
| Vitest | `roles.test.ts`, `components.test.tsx`, `api.test.ts` | role assignment, graph layout, table rendering, API error mapping |
| | `pages.test.tsx` | all 7 pages render with real backend output (fixture generated from the API) |
