# Optional LLVM extension: watching LLVM order and pair memory operations

The CAIF paper implements its technique inside LLVM, targeting RISC-V. This machine has
**Apple clang 17** but no standalone `opt`/`llc` and no RISC-V back end, so a full LLVM
pass is out of scope. This small, real experiment still shows the two LLVM back-end
mechanisms the paper builds on, using the AArch64 back end.

Run it with `./run_demo.sh`. The output is saved in [demo_output.txt](demo_output.txt).

## What the example shows

`fusion_demo.c` loads `a[0]`, does unrelated work (a multiply and a load of `b[3]`),
then loads `a[1]`. `a[0]` and `a[1]` are 8 bytes apart, inside one 64-byte region.

| Step | What we see | Relation to the paper |
|---|---|---|
| 1. LLVM IR (`-O3 -emit-llvm`) | `load %0` … `mul`, `gep %1+24`, `load` … `gep %0+8`, `load` | The two `a` loads are **non-consecutive** in the middle end. The catalyst is `mul, gep, load b[3]`. The `gep %0, 8` is the tail's **use-def chain** (address computation), and it shares the base `%0` with the head. This is what `stripAndAccumulateConstantOffsets` finds (Sec. IV-A1). |
| 2. AArch64, `-misched-cluster=false -aarch64-enable-ldst-opt=false` | `ldr [x0]`, `ldr [x1,#24]`, `ldr [x0,#8]` | Without help the scheduler leaves `ldr [x1,#24]` between the pair, so they are not consecutive. |
| 3. Clustering on, pairing off | `ldr [x1,#24]`, `ldr [x0]`, `ldr [x0,#8]` | The **memory-op clustering DAG mutation** (`BaseMemOpClusterMutation`, Sec. II-B3) adds weak edges so the same-base loads become adjacent. The paper extends this mechanism (Sec. IV-B2). |
| 4. Default `-O3` | `ldp x9, x10, [x0]` | AArch64's load/store optimizer merges the adjacent pair into an ISA-level **load pair** (Sec. II-A1). RISC-V has no such instruction, which is why the paper relies on micro-architectural fusion of adjacent instructions instead. |

## What this demo does *not* show

* It is not CAIF. Here the pair is close enough for LLVM's existing clustering to fix it.
  CAIF adds middle-end reordering with alias analysis for distant pairs, plus
  pseudo-instructions so that later passes cannot undo the order.
* There is no RISC-V code and no hardware measurement.
* Exact output depends on the clang version. The listing in `demo_output.txt` comes from
  Apple clang 17.0.0 (clang-1700.3.19.1) on arm64 macOS.
