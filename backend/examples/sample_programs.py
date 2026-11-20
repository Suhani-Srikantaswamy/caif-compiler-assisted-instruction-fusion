"""Predefined sample programs.

Each sample documents what it is designed to show (`expected`), the
dependences involved, and whether a rearrangement *should* happen. These are
specifications written by hand; the optimizer's actual output is always
computed at run time and compared against them in the tests and the UI.
"""
from __future__ import annotations

SAMPLES: list[dict] = [
    {
        "id": "s01_load_pair_independent",
        "title": "1. LOAD pair split by an independent instruction",
        "kind": "success",
        "description": "Two loads from A+0 and A+8 (same 64-byte region) are separated by an unrelated ADD.",
        "expected": "L2 is moved directly after L1; the ADD stays after the pair. +1 consecutive opportunity.",
        "dependencies": "ADD reads R3,R4 and writes R2 - it shares no register or memory with L2.",
        "should_rearrange": True,
        "config": {},
        "source": """\
; a[0] and a[1] are loaded, an unrelated add sits in between
L1: LOAD R1, [A+0]
ADD R2, R3, R4
L2: LOAD R5, [A+8]
ADD R6, R1, R5
""",
    },
    {
        "id": "s02_store_pair_independent",
        "title": "2. STORE pair split by an independent instruction",
        "kind": "success",
        "description": "Stores to B+0 and B+8 are separated by a MUL that touches neither.",
        "expected": "S2 is moved directly after S1. +1 consecutive opportunity.",
        "dependencies": "MUL writes R6; S2 reads R2 and writes B+8. No conflicts.",
        "should_rearrange": True,
        "config": {},
        "source": """\
S1: STORE [B+0], R1
MUL R6, R7, R8
S2: STORE [B+8], R2
""",
    },
    {
        "id": "s03_intervening_store_alias",
        "title": "3. Intervening STORE to the same location",
        "kind": "rejected",
        "description": "L2 reads A+8, but the catalyst store S1 writes A+8 first.",
        "expected": "Rejected: hoisting L2 above S1 would read the old value (MEM-RAW, MUST_ALIAS).",
        "dependencies": "S1 -> L2 memory RAW dependence (identical bytes A+8..A+16).",
        "should_rearrange": False,
        "config": {},
        "source": """\
L1: LOAD R1, [A+0]
S1: STORE [A+8], R2
L2: LOAD R3, [A+8]
""",
    },
    {
        "id": "s04_raw_register_dependency",
        "title": "4. RAW register dependency (pointer chasing)",
        "kind": "rejected",
        "description": "L1 loads a new pointer into R4; L2's address is computed from that loaded value.",
        "expected": "Not a valid pair: the tail's use-def chain contains the head (RAW/ADDRESS L1 -> L2), "
                    "and the distance between the two addresses cannot be proven.",
        "dependencies": "L1 -> L2 ADDRESS (RAW on R4). ADD R6 is independent.",
        "should_rearrange": False,
        "config": {},
        "source": """\
; linked list: R4 = node->next, then read a field of the NEW node
L1: LOAD R4, [R4+0]
ADD R6, R6, 1
L2: LOAD R5, [R4+8]
""",
    },
    {
        "id": "s05_tail_address_calculation",
        "title": "5. Tail address computed late (use-def chain hoisting)",
        "kind": "success",
        "description": "The tail's address register R4 is produced by an ADDR in the catalyst. "
                       "CAIF must hoist that ADDR above the head together with the tail. "
                       "Uses target 'Cons' because the two loads use different base registers "
                       "(R3 vs R4) whose distance is still provable (both point into A).",
        "expected": "ADDR R4 and L2 are hoisted; MUL (which depends on the head) stays behind. "
                    "Switch the target to ConsSBR64 to see it rejected as 'different base register'.",
        "dependencies": "ADDR R4 -> L2 (ADDRESS). L1 -> MUL (RAW on R1). L1 and L2 are independent.",
        "should_rearrange": True,
        "config": {"target": "Cons"},
        "source": """\
ADDR R3, A, 0
L1: LOAD R1, [R3+0]
MUL R2, R1, R1        ; uses the head's result -> must stay after the head
ADDR R4, A, 16        ; address of the tail
L2: LOAD R5, [R4+0]
""",
    },
    {
        "id": "s06_out_of_range",
        "title": "6. Accesses outside the 64-byte window",
        "kind": "rejected",
        "description": "A+0 and A+128 belong to the same array but are 136 bytes apart in span.",
        "expected": "Not compatible: span 136 B > 64 B window. Nothing moves.",
        "dependencies": "None between L1 and L2.",
        "should_rearrange": False,
        "config": {},
        "source": """\
L1: LOAD R1, [A+0]
ADD R2, R3, R4
L2: LOAD R5, [A+128]
""",
    },
    {
        "id": "s07_already_consecutive",
        "title": "7. Already consecutive pair",
        "kind": "success",
        "description": "The compiler already emitted the two loads back to back.",
        "expected": "Recognised as an existing opportunity; no movement. Before = after = 1.",
        "dependencies": "ADD R3 depends on both loads (RAW); the STORE depends on ADD.",
        "should_rearrange": False,
        "config": {},
        "source": """\
L1: LOAD R1, [A+0]
L2: LOAD R2, [A+8]
ADD R3, R1, R2
S1: STORE [B+0], R3
""",
    },
    {
        "id": "s08_unknown_addresses",
        "title": "8. Unknown (possibly aliasing) pointers",
        "kind": "rejected",
        "description": "L1/L2 share base R10, but the catalyst stores through R11, which may point anywhere. "
                       "L3/L4 use different unknown pointers R12 and R13.",
        "expected": "L1+L2 rejected (S1 MAY_ALIAS with L2). L3+L4 not even compatible (distance unprovable).",
        "dependencies": "S1 -> L2 MEMORY (MAY_ALIAS). Conservative analysis must assume overlap.",
        "should_rearrange": False,
        "config": {},
        "source": """\
L1: LOAD R1, [R10+0]
S1: STORE [R11+0], R5     ; R11 is a function argument: may alias R10
L2: LOAD R2, [R10+8]
L3: LOAD R3, [R12+0]
L4: LOAD R4, [R13+8]
""",
    },
    {
        "id": "s09_multiple_pairs",
        "title": "9. Multiple candidate pairs (unrolled dot product)",
        "kind": "success",
        "description": "A 2x unrolled body of c = a[i]*b[i] + a[i+1]*b[i+1]. Loads from A and B are interleaved, "
                       "so no two compatible loads are adjacent.",
        "expected": "Three new consecutive pairs: (L1,L3) on A, (L2,L4) on B and (S1,S2) on C "
                    "(the ADD computing S2's value is hoisted with it).",
        "dependencies": "MULs depend on their loads; ADD R7 on both MULs; S1 on ADD R7; S2 on ADD R8.",
        "should_rearrange": True,
        "config": {},
        "source": """\
L1: LOAD R1, [A+0]
L2: LOAD R2, [B+0]
MUL R3, R1, R2
L3: LOAD R4, [A+8]
L4: LOAD R5, [B+8]
MUL R6, R4, R5
ADD R7, R3, R6
S1: STORE [C+0], R7
ADD R8, R1, R4
S2: STORE [C+8], R8
""",
    },
    {
        "id": "s10_multiple_constraints",
        "title": "10. Multiple dependency constraints (WAR, CALL, success)",
        "kind": "mixed",
        "description": "Three candidate pairs, each facing a different constraint.",
        "expected": "(L1,L2) rejected by WAR on R2; (L3,L4) rejected because L4 cannot cross the CALL; "
                    "(S1,S2) succeeds - MOV R9 is independent.",
        "dependencies": "ADD R6 reads R2 before L2 overwrites it (WAR). CALL is a memory barrier. ",
        "should_rearrange": True,
        "config": {},
        "source": """\
L1: LOAD R1, [A+0]
ADD R6, R2, 1          ; still needs the OLD value of R2
L2: LOAD R2, [A+8]     ; overwrites R2 -> WAR with the ADD
L3: LOAD R3, [B+0]
CALL helper            ; may read/write any memory
L4: LOAD R4, [B+8]
S1: STORE [D+0], R1
MOV R9, 0
S2: STORE [D+16], R3
""",
    },
    {
        "id": "s11_store_value_chain",
        "title": "11. STORE whose value is computed in the catalyst",
        "kind": "success",
        "description": "The tail stores R4 = C[0] + R3. Its use-def chain (LOAD R2 and ADD R4) is hoisted above the head.",
        "expected": "Chain {I1 (LOAD R2), I3 (ADD R4)} moves above S1; S2 follows S1; the unrelated MUL stays behind.",
        "dependencies": "LOAD R2 -> ADD R4 -> S2 (RAW). The chain load reads C, the head writes B: NO_ALIAS.",
        "should_rearrange": True,
        "config": {},
        "source": """\
S1: STORE [B+0], R1
LOAD R2, [C+0]
MUL R7, R8, R8
ADD R4, R2, R3
S2: STORE [B+8], R4
""",
    },
    {
        "id": "s12_chain_load_conflict",
        "title": "12. Use-def chain load conflicts with a catalyst store",
        "kind": "rejected",
        "description": "Like Fig. 5 of the paper: the tail's chain contains a load, and a catalyst store through "
                       "an unknown pointer may alias both that load and the tail.",
        "expected": "Rejected: MEM-RAW (store -> chain load) and MEM-WAW (store -> tail) may-alias dependences.",
        "dependencies": "S9 -> I1 (MEM-RAW, MAY_ALIAS), S9 -> S2 (MEM-WAW, MAY_ALIAS).",
        "should_rearrange": False,
        "config": {},
        "source": """\
S1: STORE [B+0], R1
S9: STORE [R9+0], R2   ; unknown pointer
LOAD R3, [C+0]          ; value for the tail
S2: STORE [B+8], R3
""",
    },
    {
        "id": "s13_basic_block_boundary",
        "title": "13. Candidates in different basic blocks",
        "kind": "rejected",
        "description": "A conditional branch separates the loads. CAIF never moves code across block boundaries.",
        "expected": "No pair is formed across the branch; nothing moves.",
        "dependencies": "CMP -> BEQ (RAW on FLAGS). Loads are in blocks B0, B1 and 'done'.",
        "should_rearrange": False,
        "config": {},
        "source": """\
L1: LOAD R1, [A+0]
CMP R1, 0
BEQ done
L2: LOAD R2, [A+8]
done:
L3: LOAD R3, [A+16]
""",
    },
]

SAMPLES_BY_ID = {s["id"]: s for s in SAMPLES}
