#!/bin/sh
# Optional LLVM exploration. Requires only Apple clang (Xcode command line tools).
# Shows: (1) LLVM IR with non-consecutive loads, (2) how the AArch64 back end's
# memory-op clustering (a DAG mutation) and load/store pairing change the result.
set -e
cd "$(dirname "$0")"
strip() { grep -vE '^\s*\.|^\s*;|^l|^\s*#' "$1"; }

clang -O3 -S -emit-llvm fusion_demo.c -o fusion_demo.ll
echo "=== 1. LLVM IR (middle end, after -O3) ==="
grep -E '^\s+%|^\s+ret|^define|^}' fusion_demo.ll

echo; echo "=== 2. AArch64, clustering OFF, pairing OFF ==="
clang -O3 -S fusion_demo.c -mllvm -aarch64-enable-ldst-opt=false -mllvm -misched-cluster=false -o fusion_demo.arm64.nocluster.s
strip fusion_demo.arm64.nocluster.s

echo; echo "=== 3. AArch64, clustering ON (DAG mutation), pairing OFF ==="
clang -O3 -S fusion_demo.c -mllvm -aarch64-enable-ldst-opt=false -o fusion_demo.arm64.nopair.s
strip fusion_demo.arm64.nopair.s

echo; echo "=== 4. AArch64 default: clustering ON + load-pair formation (ldp) ==="
clang -O3 -S fusion_demo.c -o fusion_demo.arm64.s
strip fusion_demo.arm64.s
