# Experiment report `exp-20261119-233613-d044`

Generated: 2026-11-19T23:36:13 | Label: cli

> Locally generated results on the educational instruction model. 'Consecutive' counts are potential fusion opportunities, not measured hardware fusions; optimizer_time_ms is the compile-time cost of the Python optimizer, not program run time.

## Per-sample results

| Sample | Target | Instr | Mem | Cand. pairs | Deps | Attempted | OK | Rejected | Before | After | +Opp | Opt. time (ms) | Valid | Matches spec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. LOAD pair split by an independent instruction | ConsSBR64 | 4 | 2 | 1 | 2 | 1 | 1 | 0 | 0 | 1 | 1 | 0.0617 | yes | yes |
| 2. STORE pair split by an independent instruction | ConsSBR64 | 3 | 2 | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 1 | 0.0542 | yes | yes |
| 3. Intervening STORE to the same location | ConsSBR64 | 3 | 3 | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0.08 | yes | yes |
| 4. RAW register dependency (pointer chasing) | ConsSBR64 | 3 | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0353 | yes | yes |
| 5. Tail address computed late (use-def chain hoisting) | Cons | 5 | 2 | 1 | 3 | 1 | 1 | 0 | 0 | 1 | 1 | 0.0839 | yes | yes |
| 6. Accesses outside the 64-byte window | ConsSBR64 | 3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.027 | yes | yes |
| 7. Already consecutive pair | ConsSBR64 | 4 | 3 | 1 | 3 | 0 | 0 | 0 | 1 | 1 | 0 | 0.0299 | yes | yes |
| 8. Unknown (possibly aliasing) pointers | ConsSBR64 | 5 | 5 | 1 | 4 | 1 | 0 | 1 | 0 | 0 | 0 | 0.2543 | yes | yes |
| 9. Multiple candidate pairs (unrolled dot product) | ConsSBR64 | 10 | 6 | 3 | 10 | 3 | 3 | 0 | 0 | 3 | 3 | 0.3705 | yes | yes |
| 10. Multiple dependency constraints (WAR, CALL, success) | ConsSBR64 | 9 | 6 | 3 | 9 | 3 | 1 | 2 | 0 | 1 | 1 | 0.6225 | yes | yes |
| 11. STORE whose value is computed in the catalyst | ConsSBR64 | 5 | 3 | 1 | 2 | 1 | 1 | 0 | 0 | 1 | 1 | 0.1128 | yes | yes |
| 12. Use-def chain load conflicts with a catalyst store | ConsSBR64 | 4 | 4 | 1 | 4 | 1 | 0 | 1 | 0 | 0 | 0 | 0.1767 | yes | yes |
| 13. Candidates in different basic blocks | ConsSBR64 | 5 | 3 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0469 | yes | yes |

## Totals

- Instructions: 63, memory instructions: 43
- Compatible candidate pairs: 14
- Rearrangements attempted / successful / rejected: 13 / 8 / 5
- Consecutive fusion opportunities: 1 before -> 9 after (+8)
- Share of memory instructions in a consecutive pair: 4.65% -> 41.86%
- All transformations validated: True; all samples match their specification: True

## Rejection reasons

- **s03_intervening_store_alias**: S1 -> L2 [MEMORY/MEM-RAW]: S1 / L2: MUST_ALIAS - same object, identical bytes &A+8 (8 B). Moving L2 above S1 would break this dependence.
- **s08_unknown_addresses**: S1 -> L2 [MEMORY/MEM-RAW]: S1 / L2: MAY_ALIAS - cannot relate R11@in(B0) and R10@in(B0)+8 (unknown pointer) - conservatively assume they may overlap. Moving L2 above S1 would break this dependence.
- **s10_multiple_constraints**: I1 -> L2 [WAR/R2]: L2 overwrites R2, which I1 must read first. Moving L2 above I1 would break this dependence.
- **s10_multiple_constraints**: I2 -> L4 [MEMORY/CALL]: I2 (CALL helper) may read/write any memory, so I2 and L4 keep their order. Moving L4 above I2 would break this dependence.
- **s12_chain_load_conflict**: S9 -> I1 [MEMORY/MEM-RAW]: S9 / I1: MAY_ALIAS - cannot relate R9@in(B0) and &C (unknown pointer) - conservatively assume they may overlap. Moving I1 above S9 would break this dependence.
- **s12_chain_load_conflict**: S9 -> S2 [MEMORY/MEM-WAW]: S9 / S2: MAY_ALIAS - cannot relate R9@in(B0) and &B+8 (unknown pointer) - conservatively assume they may overlap. Moving S2 above S9 would break this dependence.

## Sensitivity: target model x fusion window (all samples)

| Target | Window (B) | Before | After | Successful | Rejected |
|---|---|---|---|---|---|
| ConsSBR | 16 | 1 | 7 | 6 | 5 |
| ConsSBR | 32 | 1 | 7 | 6 | 5 |
| ConsSBR | 64 | 1 | 7 | 6 | 5 |
| ConsSBR | 128 | 1 | 7 | 6 | 5 |
| ConsSBR64 | 16 | 1 | 7 | 6 | 5 |
| ConsSBR64 | 32 | 1 | 8 | 7 | 5 |
| ConsSBR64 | 64 | 1 | 8 | 7 | 5 |
| ConsSBR64 | 128 | 1 | 8 | 7 | 5 |
| Cons | 16 | 1 | 7 | 6 | 5 |
| Cons | 32 | 1 | 9 | 8 | 5 |
| Cons | 64 | 1 | 9 | 8 | 5 |
| Cons | 128 | 1 | 9 | 8 | 5 |
