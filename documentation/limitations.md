# Limitations and differences from the paper

## What is faithful

* The problem: fusible memory pairs that are not consecutive, and simple hardware that only
  fuses consecutive pairs.
* The middle-end algorithm structure: scan each basic block, take a HEAD and look for a TAIL
  within a 64-byte range, collect the catalyst, compute the TAIL's use-def chain, refuse if
  it contains the HEAD, check memory dependences with alias analysis, then hoist the chain
  above the HEAD and place the TAIL right after it.
* Conservative safety: no transformation is made unless it is proven legal under the model.
* Hardware targets with the same names as in the paper (ConsSBR, ConsSBR64, Cons).

## Educational approximations

| Paper | Here | Consequence |
|---|---|---|
| LLVM IR (SSA) generated from C/C++ and ONNX models | hand-written register-level teaching ISA | Register WAR/WAW hazards exist here and are checked. They cannot occur in SSA. |
| `stripAndAccumulateConstantOffsets` + Scalar Evolution | constant-offset resolution through ADDR/MOV/ADD-imm | No loop induction variables or symbolic strides. Indexed addresses are unknown pointers. |
| LLVM AA + SVF (Andersen, flow-sensitive) + GraphAA | symbolic, intra-block, conservative | Any unknown pointer may alias anything, so some safe moves are rejected. |
| Interprocedural reordering across calls | `CALL` is a full memory barrier | Fewer opportunities near calls. |
| Dynamic loop unrolling (factor 2, innermost loops with < 50 instructions) | none. Samples are written already unrolled (sample 9) | – |
| Back end: pseudo-instructions + DAG mutations keep the order through `llc` | no back end. `llvm_demo/` shows the real LLVM clustering and `ldp` behaviour | The prototype's order is final by construction. |
| Register pressure kept low by design choices | not modelled | – |
| 64-byte region / cache line (middle end); offset difference <= 64 (back-end DAG mutation) | `span <= 64` bytes. Alignment is unknown | Stricter than an offset-difference test. Two accesses could fit in 64 B and still straddle a real cache-line boundary. |
| CALL clobbers caller-saved registers on a real machine | CALL only touches memory | A register-only instruction may be moved across a CALL. That is legal in this model, not on real hardware. |
| Spike + cycle-level Gracemont-like simulator, CACTI energy | **none** | Only *potential* opportunity counts. No speedup, energy or MPKI claims. |

## Correctness claims

* Under the modelled semantics (registers, byte-addressed memory, distinct symbols, opaque
  CALLs), the commutation argument in `algorithm.md` §4 and §6 shows that an accepted move
  preserves behaviour, given that the alias analysis is sound. This is an informal argument,
  not a machine-checked proof.
* The alias analysis is sound for this model because it only returns `NO_ALIAS` for two
  *in-bounds* accesses to distinct symbols (objects of at most 16 MiB), or for provably disjoint
  ranges from the same base value with offsets small enough (±2^40) that 64-bit wrap-around cannot
  occur. Before the audit, both conditions were missing (see `audit_report.md`).
* Evidence (testing, not proof): the Pytest suite, including two fuzz tests (300 and 250
  random programs, up to three targets each) where every result must pass the static re-check
  and the differential execution check, and mutation tests showing that a deliberately broken
  optimizer or alias analysis is caught.
* The static re-check shares the alias analysis with the optimizer. Only the
  interpreter-based differential test is independent of it, and it covers a finite set of
  scenarios. Pointers loaded from memory (pointer chasing) are not deliberately aimed at other
  accesses, so aliasing through them is exercised only by chance.

## Known simplifications in pair selection

* Greedy, in program order. An optimal pairing (a maximum matching) could sometimes form more
  pairs.
* Only the TAIL moves (upwards), as in the paper. Sinking the HEAD, or moving blocking
  catalyst instructions out of the way, is not attempted.
* Each instruction joins at most one pair. Chains of three or more fused operations are not
  modelled.
