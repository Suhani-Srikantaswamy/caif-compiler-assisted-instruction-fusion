# CAIF: Compiler-Assisted Instruction Fusion, an educational implementation

*Research-based Compiler Design project, based on Reddy, Singh, Perais, Ros and Jimborean,
"Compiler-Assisted Instruction Fusion", CGO 2026.*

---

## A. Problem statement

Modern cores can **fuse** two adjacent instructions into one internal micro-operation. A
fused pair of memory operations takes one slot in the reorder buffer and in the load or
store queue, and needs one cache access. The cheapest fusion hardware works at decode time
and only looks at **consecutive** instructions that use the same base register within one
64-byte region.

Compilers, however, often separate fusible memory operations, for example when loops are
unrolled and accesses to different arrays are interleaved. A non-consecutive pair is
invisible to simple hardware. Hardware that fuses non-consecutive pairs (Helios) needs a
predictor, history buffers, validation at rename and issue, and recovery from
misprediction. **The problem: how can we get the benefit of non-consecutive fusion without
that hardware cost?**

## B. Motivation

The compiler sees the whole basic block. It is not limited to the hardware's allocation
window, and it can *prove* that a reordering is legal instead of predicting it. If the
compiler places each fusible pair next to each other, simple non-speculative hardware is
enough. There is nothing to mispredict, and fused operations do not have to wait for
in-between instructions before they commit.

## C. Literature study (summary of the paper)

* **Characterisation (Sec. III):** on neural-network layers running on a Gracemont-like core
  with Helios, 27.12% of memory operations were fused *non-consecutively*. Only 1.94% fell in
  the simplest Consecutive-SBR-contiguous category. The average distance between fused
  instructions was 4.16 instructions (NN) and 3.60 (SPEC).
* **Technique (Sec. IV):**
  *Middle end (LLVM IR):* in each basic block, take a HEAD load or store and scan for a TAIL
  of the same kind within 64 bytes. The distance comes from a common base pointer
  (`stripAndAccumulateConstantOffsets`) or from SCEV. The instructions in between form the
  *Catalyst*. Build the TAIL's use-def chain. No reordering if the chain contains the HEAD
  or needs a store. Alias analysis (LLVM, SVF Andersen and flow-sensitive, GraphAA) checks the
  tail and its chain against catalyst and head accesses. If the move is safe, the chain is
  hoisted above the HEAD and the TAIL is placed after it. Dynamic loop unrolling by 2 widens
  the scope.
  *Back end:* fusible pairs become **pseudo-instructions** before scheduling and register
  allocation, so the scheduler cannot separate them, and are expanded afterwards. Pairs that
  appear later, such as spills, are kept together with **DAG-mutation** cluster edges built
  on `BaseMemOpClusterMutation`.
* **Methodology (Sec. V):** PyTorch → ONNX → MLIR → LLVM IR, or C/C++ → clang. RISC-V
  RV64G binaries run on Spike, feeding a cycle-level out-of-order model. Hardware
  configurations: NoFusion, ConsSBR, ConsSBR64, Cons, Helios. Energy is modelled with CACTI.
* **Findings (Sec. VI, as reported):** on NN kernels, ConsSBR64 hardware reduces execution time
  by 1.2% with the baseline compiler and by **19.6% with CAIF**, which is more than Helios with
  the baseline compiler (6.6%). Helios + CAIF reaches 20.3%. On SPEC the ConsSBR64 reduction
  goes from 2.6% to 6.6% (the abstract gives 2.4% → 6.4%). Non-consecutive fusion drops from
  27.12% to 8.96% (NN), the catalyst depth from 4.16 to 1.68, and binary size grows by at most
  0.31%.

All of these numbers are **the authors' results**. This project does not reproduce them.

## D. System architecture

See [architecture.md](architecture.md). There are nine stages, and each is a separate Python
module with its own tests:

Input → Parse → Candidate detection → Dependence and alias analysis → Catalyst analysis →
Rearrangement → Validation (static re-check + differential execution) → Opportunity detection →
Results and visualisation.

A FastAPI layer exposes the stages, and a React application shows them on seven pages.

## E. Algorithm

See [algorithm.md](algorithm.md) for the precise rules and the safety argument. Pseudocode:

```
for each basic block B:
  claim already-consecutive compatible pairs
  repeat until no change:
    for HEAD in B (unpaired memory ops, program order):
      for TAIL after HEAD in B (same kind, unpaired):
        if not compatible(HEAD, TAIL): continue           # 64 B window, provable distance, ...
        if adjacent: pair them; break
        C     = instructions between HEAD and TAIL        # catalyst
        chain = use-def chain of TAIL inside [HEAD..TAIL]
        if HEAD in chain: reject
        if ∃ dependence edge  x → y  with  x ∈ {HEAD} ∪ (C \ chain),  y ∈ chain ∪ {TAIL}
              (other than HEAD → TAIL): reject            # RAW/WAR/WAW/MEMORY(alias)/CALL
        order := … chain, HEAD, TAIL, (C \ chain) …
        pair them; break
validate(original, result): static commutation check + interpreter differential test; on failure keep the original
```

## F. Implementation

See [implementation_details.md](implementation_details.md). Highlights:

* **Parser:** a teaching assembly language with explicit IDs, labels and size suffixes. It
  collects *all* errors with line numbers and never drops a line silently.
* **Alias analysis:** abstract addresses `(symbol | pointer value | absolute, offset)`,
  returning NO / MUST / PARTIAL / MAY alias. It is conservative for unknown pointers.
* **Dependence graph:** RAW, ADDRESS, WAR, WAW and MEMORY edges, each with a human-readable
  reason.
* **Optimizer:** the paper's head/tail/catalyst/use-def-chain move, generalised to a single
  edge-based legality rule.
* **Validator:** a different formulation (pairwise commutation of every inverted pair) plus
  differential execution under aliasing scenarios. It shares no code with the optimizer's
  legality check.
* **UI:** an editor with sample programs, a candidate table with per-condition explanations,
  an interactive React Flow dependence graph with role colours and blocking edges, a
  side-by-side before/after view with a step-by-step replay, and a results dashboard.

## G. Results (generated by this implementation)

The full tables, regenerated by `python -m experiments.experiment_runner`, are in
[results.md](results.md). Raw data: `data/experiments/*.json|csv`. Run of 19 Nov 2026 over the
13 sample programs:

| Measure | Value |
|---|---|
| Instructions / memory instructions | 63 / 43 |
| Compatible candidate pairs | 14 |
| Rearrangements attempted / successful / rejected | 13 / 8 / 5 |
| Consecutive fusion opportunities, before → after | **1 → 9 (+8)** |
| Memory instructions in a consecutive pair | 4.65% → 41.86% |
| All transformations passed validation (static + differential) | yes |
| All samples behaved as specified | yes |
| Optimizer time per sample | < 1 ms (median of 25 runs; Python, compile-time only) |

Sensitivity over all samples (consecutive opportunities after CAIF):

| Target | 16 B | 32 B | 64 B | 128 B |
|---|---|---|---|---|
| ConsSBR | 7 | 7 | 7 | 7 |
| ConsSBR64 | 7 | 8 | 8 | 8 |
| Cons | 7 | 9 | 9 | 9 |

*These are potential opportunities in a simulated model. They are not hardware fusions and
not speedups, and they are not comparable to Section C.*

## H. Discussion

**Successful transformations.** The independent-catalyst cases (samples 1 and 2), chain
hoisting of an address computation (sample 5) and of a stored value (sample 11), and the
unrolled dot product (sample 9). In sample 9 no compatible pair was adjacent in the input,
and CAIF formed three: `(L1,L3)` on A, `(L2,L4)` on B and `(S1,S2)` on C, the last after
hoisting the `ADD` that computes S2's value.

**Rejected transformations.** Each has a concrete, reported cause:
* sample 3: an intervening store to the same bytes (MEM-RAW, MUST_ALIAS);
* sample 8: a store through an unknown pointer (MAY_ALIAS). The conservative analysis cannot
  rule out overlap, and the differential tester's full-aliasing scenario shows why that
  caution is needed;
* sample 10: a register WAR hazard, and a load that cannot cross a `CALL`;
* sample 12: a load in the tail's use-def chain, and the tail itself, both conflict with a
  store through an unknown pointer (the situation in Fig. 5 of the paper).

Samples 4, 6 and 13 are rejected earlier, at the compatibility stage: the tail depends on the
head, the span exceeds 64 bytes, and the operations are in different basic blocks.

**Observations.**
1. The target model matters. Sample 5 (different base registers) is only a candidate under
   `Cons`, and ConsSBR misses the non-contiguous pair in sample 10. This mirrors the
   paper's hierarchy of fusion hardware.
2. Smaller windows lose pairs (16 B removes the `D+0`/`D+16` pair).
3. Imprecise alias information is the main reason safe-looking moves are rejected. This
   is why the paper invests in SVF and GraphAA.
4. The real LLVM experiment in `llvm_demo/` shows the back-end side. With memory-op
   clustering disabled, the AArch64 scheduler leaves a load between `a[0]` and `a[1]`. The
   clustering DAG mutation makes them adjacent, and the load/store optimizer then forms `ldp`.

## I. Conclusion

The project implements the core idea of CAIF end to end. It identifies compatible memory
pairs, analyses the catalyst and the tail's use-def chain, proves safety with dependence and
alias analysis, rearranges the code, re-validates the result, and measures the
gain in *consecutive* fusion opportunities. On the sample workloads the number of such
opportunities rose from 1 to 9 with no unsafe transformation, illustrating the paper's
thesis: a compiler can turn non-consecutive fusion opportunities into consecutive ones, so
simple hardware can fuse them. Claims about performance remain those of the original paper.

## J. References

1. R. R. Reddy, S. Singh, A. Perais, A. Ros, A. Jimborean. *Compiler-Assisted Instruction
   Fusion*. CGO 2026. https://webs.um.es/aros/papers/pdfs/rrreddy-cgo26.pdf ·
   https://2026.cgo.org/details/cgo-2026-papers/34/Compiler-Assisted-Instruction-Fusion
2. S. Singh et al. *Exploring Instruction Fusion Opportunities in General Purpose
   Processors* (Helios). MICRO 2022.
3. C. Celio et al. *The Renewed Case for the Reduced Instruction Set Computer: Avoiding ISA
   Bloat with Macro-Op Fusion for RISC-V*. 2016.
4. C. Lattner, V. Adve. *LLVM: A Compilation Framework for Lifelong Program Analysis &
   Transformation*. CGO 2004.
5. LLVM documentation: *The LLVM Target-Independent Code Generator: SelectionDAG*.
   https://llvm.org/docs/CodeGenerator.html
6. LLVM documentation: *LLVM Alias Analysis Infrastructure*. https://llvm.org/docs/AliasAnalysis.html
7. LLVM `BaseMemOpClusterMutation` / memory-op clustering: https://reviews.llvm.org/D85517
8. A. Aho, M. Lam, R. Sethi, J. Ullman. *Compilers: Principles, Techniques, and Tools*, 2nd
   ed., ch. 9 (data-flow analysis) and ch. 10 (instruction scheduling).
