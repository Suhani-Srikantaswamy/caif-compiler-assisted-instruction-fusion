import pytest

from core.catalyst_analyzer import analyze_catalyst
from core.dependency_analyzer import build_dependency_graph
from examples.sample_programs import SAMPLES
from helpers import order, parse_ok, run


# ---- catalyst analysis ------------------------------------------------------
def test_catalyst_identification():
    seq = parse_ok("H: LOAD R1, [A+0]\nC1: MUL R2, R1, R1\nC2: ADDR R4, A, 16\nC3: NOP\nT: LOAD R5, [R4+0]")
    rep = analyze_catalyst(seq, 0, 4, build_dependency_graph(seq))
    assert rep.catalyst == ["C1", "C2", "C3"]
    assert rep.chain == ["C2"] and rep.safe
    e = {x.id: x for x in rep.entries}
    assert e["C1"].depends_on_head and e["C1"].action == "STAYS" and e["C1"].can_remain
    assert e["C2"].in_tail_chain and e["C2"].provides == "address of tail" and e["C2"].action == "MOVES_WITH_TAIL"
    assert rep.proposed_order == ["C2", "H", "T", "C1", "C3"]


def test_catalyst_blocking_reported():
    seq = parse_ok("H: LOAD R1, [A+0]\nC: STORE [A+8], R2\nT: LOAD R3, [A+8]")
    rep = analyze_catalyst(seq, 0, 2, build_dependency_graph(seq))
    assert not rep.safe
    assert rep.entries[0].blocking and not rep.entries[0].can_remain
    assert rep.entries[0].memory_effect == "WRITE"


def test_chain_containing_head_is_rejected():
    seq = parse_ok("H: LOAD R1, [A+0]\nC: ADD R2, R1, 0\nT: STORE [R2+0], R3")
    rep = analyze_catalyst(seq, 0, 2, build_dependency_graph(seq))
    assert rep.head_in_chain and not rep.safe


# ---- safe rearrangements ----------------------------------------------------
def test_simple_tail_move():
    r = run("L1: LOAD R1, [A+0]\nX: ADD R2, R3, R4\nL2: LOAD R5, [A+8]")
    assert order(r) == ["L1", "L2", "X"] and r["status"] == "OPTIMIZED" and r["validation"]["valid"]


def test_chain_hoisted_with_tail():
    r = run("S1: STORE [B+0], R1\nLD: LOAD R2, [C+0]\nM: MUL R7, R8, R8\nAD: ADD R4, R2, R3\nS2: STORE [B+8], R4")
    assert order(r) == ["LD", "AD", "S1", "S2", "M"]


def test_catalyst_depending_on_head_may_stay():
    r = run("L1: LOAD R1, [A+0]\nD: ADD R2, R1, R1\nL2: LOAD R3, [A+8]")
    assert order(r) == ["L1", "L2", "D"]


def test_does_not_sort_by_opcode():
    # a LOAD on another object must not be moved next to L1 just because it is a load
    r = run("L1: LOAD R1, [A+0]\nX: ADD R2, R3, R4\nL2: LOAD R5, [B+8]")
    assert order(r) == ["L1", "X", "L2"]


# ---- rejections -----------------------------------------------------------
@pytest.mark.parametrize("src, reason", [
    ("L1: LOAD R1, [A+0]\nS: STORE [A+8], R2\nL2: LOAD R3, [A+8]", "MEM-RAW"),
    ("L1: LOAD R1, [R10+0]\nS: STORE [R11+0], R2\nL2: LOAD R3, [R10+8]", "MAY_ALIAS"),
    ("L1: LOAD R1, [A+0]\nU: ADD R6, R2, 1\nL2: LOAD R2, [A+8]", "WAR"),
    ("L1: LOAD R1, [A+0]\nW: MOV R2, 5\nL2: LOAD R2, [A+8]", "WAW"),
    ("L1: LOAD R1, [A+0]\nC: CALL f\nL2: LOAD R2, [A+8]", "CALL"),
    ("S1: STORE [A+0], R1\nS: STORE [R9], R2\nL: LOAD R3, [C]\nS2: STORE [A+8], R3", "MEM-RAW"),
    # catalyst redefines the head's base register, tail would read the wrong one
    ("L1: LOAD R1, [R3+0]\nX: ADD R3, R3, 0\nL2: LOAD R2, [R3+8]", None),
])
def test_unsafe_rearrangement_rejected(src, reason):
    r = run(src, target="Cons")
    assert r["status"] == "UNCHANGED"
    assert r["metrics"]["successful_rearrangements"] == 0
    if reason:
        rej = [s for s in r["steps"] if s["action"] == "REJECTED"]
        assert rej and any(reason in line for s in rej for line in s["explanation"])


def test_multiple_pairs():
    s = next(s for s in SAMPLES if s["id"] == "s09_multiple_pairs")
    r = run(s["source"])
    assert r["metrics"]["consecutive_after"] == 3
    assert sorted(map(tuple, r["pairs"])) == [("L1", "L3"), ("L2", "L4"), ("S1", "S2")]


def test_existing_pairs_are_not_broken():
    # (L3,L4) is already consecutive; using L4 as L1's tail would break it
    r = run("L1: LOAD R1, [A+0]\nX: NOP\nL3: LOAD R3, [A+8]\nL4: LOAD R4, [A+16]")
    assert ["L3", "L4"] in r["pairs"]
    assert r["metrics"]["consecutive_after"] >= r["metrics"]["consecutive_before"]


def test_basic_block_restriction():
    r = run("L1: LOAD R1, [A+0]\nX: NOP\nBR n\nn:\nL2: LOAD R2, [A+8]")
    assert order(r) == ["L1", "X", "I1", "L2"] and r["status"] == "UNCHANGED"


def test_deterministic():
    s = next(s for s in SAMPLES if s["id"] == "s10_multiple_constraints")
    a, b = run(s["source"]), run(s["source"])
    for k in ("optimized", "steps", "pairs", "validation"):
        assert a[k] == b[k]


@pytest.mark.parametrize("sample", SAMPLES, ids=[s["id"] for s in SAMPLES])
def test_samples_match_their_specification(sample):
    r = run(sample["source"], **sample["config"])
    assert r["validation"]["valid"]
    moved = r["metrics"]["successful_rearrangements"] > 0
    assert moved == sample["should_rearrange"], sample["expected"]
    assert r["metrics"]["consecutive_after"] >= r["metrics"]["consecutive_before"]
