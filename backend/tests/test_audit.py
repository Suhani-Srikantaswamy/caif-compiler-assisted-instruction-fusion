"""Adversarial tests added during the technical audit.

Each test targets a specific way the optimizer, the analyses or the validator
could be wrong. Several of them failed before the audit fixes (marked BUG).
"""
import random

import pytest

import core.alias_analyzer as aa
import core.catalyst_analyzer as ca
from core.alias_analyzer import AddressAnalysis, AliasKind
from core.config import FusionConfig
from core.fusion_detector import check_pair, consecutive_opportunities
from core.pipeline import run_caif
from core.validator import check_order, differential_test
from helpers import order, parse_ok, run


def reorder(seq, ids):
    by = {i.id: i for i in seq}
    return [by[x] for x in ids]


# ---------------------------------------------------------------------------
# Alias analysis soundness
# ---------------------------------------------------------------------------
def test_BUG_wraparound_is_may_alias():
    # R3 + 2**64 is the same address as R3 on a 64-bit machine.
    seq = parse_ok("X: LOAD R1, [R3+8]\nADD R4, R3, 18446744073709551616\nY: STORE [R4+8], R2")
    assert AddressAnalysis(seq).alias("X", "Y").kind == AliasKind.MAY_ALIAS


def test_BUG_wraparound_move_not_proposed():
    r = run("L1: LOAD R1, [R3+0]\nADD R4, R3, 18446744073709551616\nS1: STORE [R4+8], R2\nL2: LOAD R5, [R3+8]")
    assert r["status"] == "UNCHANGED"           # before the fix: unsafe move, caught only by the validator


def test_BUG_out_of_bounds_pointer_may_reach_other_object():
    seq = parse_ok("ADDR R3, A, 268435456\nX: STORE [R3+8], R2\nY: LOAD R5, [B+8]")
    assert AddressAnalysis(seq).alias("X", "Y").kind == AliasKind.MAY_ALIAS


def test_negative_symbol_offset_is_out_of_bounds():
    seq = parse_ok("ADDR R3, A, 0\nSUB R4, R3, 8\nX: STORE [R4+0], R2\nY: LOAD R5, [B+0]")
    assert AddressAnalysis(seq).alias("X", "Y").kind == AliasKind.MAY_ALIAS


def test_in_bounds_different_objects_still_no_alias():
    seq = parse_ok("ADDR R3, A, 4096\nX: STORE [R3+8], R2\nY: LOAD R5, [B+8]")
    assert AddressAnalysis(seq).alias("X", "Y").kind == AliasKind.NO_ALIAS


def test_access_ending_exactly_at_object_limit_is_in_bounds():
    seq = parse_ok(f"ADDR R3, A, {aa.OBJECT_LIMIT - 8}\nX: STORE [R3+0], R2\nY: LOAD R5, [B]")
    assert AddressAnalysis(seq).alias("X", "Y").kind == AliasKind.NO_ALIAS
    seq = parse_ok(f"ADDR R3, A, {aa.OBJECT_LIMIT - 4}\nX: STORE [R3+0], R2\nY: LOAD R5, [B]")
    assert AddressAnalysis(seq).alias("X", "Y").kind == AliasKind.MAY_ALIAS


def test_huge_offsets_give_no_provable_distance():
    seq = parse_ok("LOAD R1, [R3+0]\nADD R4, R3, 18446744073709551608\nLOAD R2, [R4+0]")
    assert "provable_distance" in {c.name for c in check_pair(seq, 0, 2, FusionConfig(target="Cons")).conditions if not c.passed}


def test_partial_overlap_different_sizes():
    seq = parse_ok("X: LOAD R1, [A+0]\nY: STORE.4 [A+4], R2\nZ: STORE.4 [A+8], R2")
    a = AddressAnalysis(seq)
    assert a.alias("X", "Y").kind == AliasKind.PARTIAL_ALIAS
    assert a.alias("X", "Z").kind == AliasKind.NO_ALIAS     # [0,8) and [8,12) only touch


# ---------------------------------------------------------------------------
# Basic blocks
# ---------------------------------------------------------------------------
def test_BUG_label_named_like_auto_block():
    seq = parse_ok("L1: LOAD R1, [A+0]\nBR B0\nB0:\nL2: LOAD R2, [A+8]")
    assert seq[0].block != seq[2].block


def test_BUG_unchanged_program_with_label_B0_is_valid():
    r = run("L1: LOAD R1, [A+0]\nX: ADD R2, R3, R4\nBR B0\nB0:\nS: STORE [A+8], R9\nL2: LOAD R5, [A+8]")
    assert r["validation"]["valid"] and r["status"] == "UNCHANGED"


def test_same_pattern_in_two_blocks_optimized_independently():
    r = run("L1: LOAD R1, [A+0]\nX1: NOP\nL2: LOAD R2, [A+8]\nBR next\nnext:\n"
            "L3: LOAD R3, [A+16]\nX2: NOP\nL4: LOAD R4, [A+24]")
    assert order(r) == ["L1", "L2", "X1", "I1", "L3", "L4", "X2"]
    assert r["metrics"]["consecutive_after"] == 2
    # L2 + L3 are adjacent-compatible addresses, but in different blocks: never paired
    assert ["L2", "L3"] not in r["pairs"]


def test_validator_rejects_moving_instruction_after_branch():
    seq = parse_ok("A: LOAD R1, [A]\nB: NOP\nBR n\nn:\nC: NOP")
    assert not check_order(seq, reorder(seq, ["A", "I1", "B", "C"])).valid


# ---------------------------------------------------------------------------
# Memory dependences in the move
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("src", [
    # tail STORE would move above a catalyst LOAD that may read the same bytes (MEM-WAR)
    "S1: STORE [A+0], R1\nL: LOAD R5, [R9+0]\nS2: STORE [A+8], R2",
    # tail LOAD would move above a catalyst STORE that partially overlaps it (MEM-RAW)
    "L1: LOAD R1, [A+0]\nS9: STORE.2 [A+14], R5\nL2: LOAD R2, [A+8]",
    # load in the tail's use-def chain reads what a catalyst store wrote (MUST alias)
    "S1: STORE [B+0], R1\nS9: STORE [C+0], R2\nL: LOAD R3, [C+0]\nS2: STORE [B+8], R3",
    # chain member overwrites a register the HEAD still reads (WAR HEAD -> chain)
    "S1: STORE [A+0], R7\nC: ADD R7, R8, 1\nS2: STORE [A+8], R7",
    # STORE tail across a CALL
    "S1: STORE [A+0], R1\nCALL f\nS2: STORE [A+8], R2",
])
def test_unsafe_moves_rejected(src):
    r = run(src)
    assert r["status"] == "UNCHANGED" and r["metrics"]["rejected_rearrangements"] >= 1, r["steps"]


def test_store_tail_overlapping_catalyst_store_rejected():
    # Under ConsSBR, S1+S9 is not a pair (gap 8..12), S1+S2 is (contiguous).
    # S9 writes bytes 12..16, which S2 overwrites: S2 may not move above S9 (MEM-WAW, PARTIAL).
    r = run("S1: STORE [A+0], R1\nS9: STORE.4 [A+12], R5\nS2: STORE [A+8], R2", target="ConsSBR")
    assert r["status"] == "UNCHANGED"
    assert any("PARTIAL_ALIAS" in line for s in r["steps"] for line in s["explanation"])


def test_register_only_instruction_may_cross_call():
    # In this model CALL only touches memory, so a pure register op is independent of it.
    r = run("L1: LOAD R1, [A+0]\nCALL f\nADDR R4, A, 8\nL2: LOAD R5, [R4+0]", target="Cons")
    assert r["status"] == "UNCHANGED"  # L2 itself still may not cross the CALL


# ---------------------------------------------------------------------------
# Differential execution checker really observes the bugs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("src, bad", [
    ("C: CALL f\nL: LOAD R1, [A+0]", ["L", "C"]),                       # BUG: was undetected
    ("S: STORE [A+0], R1\nC: CALL f", ["C", "S"]),                      # BUG: was undetected
    ("S: STORE [R11+0], R2\nL: LOAD R3, [R10+8]", ["L", "S"]),          # BUG: was undetected
    ("S: STORE [R11+40], R2\nL: LOAD R3, [R10+8]", ["L", "S"]),         # BUG: was undetected
    ("S: STORE.4 [R11+4], R2\nL: LOAD R3, [R10+0]", ["L", "S"]),        # partial overlap
    ("S: STORE [R11+0], R2\nT: STORE [R10+0], R3", ["T", "S"]),         # WAW through pointers
    ("S: STORE [A+8], R2\nL: LOAD R3, [A+8]", ["L", "S"]),
])
def test_differential_detects_wrong_order(src, bad):
    seq = parse_ok(src)
    assert not differential_test(seq, reorder(seq, bad)).passed


def test_differential_accepts_correct_order():
    seq = parse_ok("S: STORE [A+0], R1\nL: LOAD R3, [B+8]\nC: ADD R5, R6, R7")
    assert differential_test(seq, reorder(seq, ["C", "L", "S"])).passed


# ---------------------------------------------------------------------------
# Mutation tests: the validator is not just repeating the optimizer
# ---------------------------------------------------------------------------
UNSAFE_PROGRAMS = [
    "L1: LOAD R1, [A+0]\nS1: STORE [A+8], R2\nL2: LOAD R3, [A+8]",
    "L1: LOAD R1, [A+0]\nU: ADD R6, R2, 1\nL2: LOAD R2, [A+8]",
    "L1: LOAD R1, [R10+0]\nS1: STORE [R11+0], R5\nL2: LOAD R2, [R10+8]",
    "L1: LOAD R1, [A+0]\nC: CALL f\nL2: LOAD R2, [A+8]",
]


@pytest.mark.parametrize("src", UNSAFE_PROGRAMS)
def test_mutant_optimizer_without_legality_check_is_caught(monkeypatch, src):
    """Break the optimizer: ignore every blocking dependence. The validator must
    reject the result and the pipeline must keep the original program."""
    real = ca.analyze_catalyst

    def broken(*args, **kw):
        rep = real(*args, **kw)
        rep.violations = []
        rep.head_in_chain = False
        return rep
    monkeypatch.setattr("core.optimizer.analyze_catalyst", broken)
    monkeypatch.setattr("core.optimizer.static_recheck", lambda o, n: type("R", (), {"valid": True, "errors": []})())
    r = run(src)
    assert r["status"] == "REJECTED_BY_VALIDATOR"
    assert order(r) == [i["id"] for i in r["instructions"]]      # original kept


@pytest.mark.parametrize("src", [UNSAFE_PROGRAMS[0], UNSAFE_PROGRAMS[2]])
def test_mutant_alias_analysis_is_caught_by_differential_execution(monkeypatch, src):
    """Break the alias analysis shared by optimizer AND static validator (always NO_ALIAS).
    The static check is fooled - only the interpreter-based check is independent of it."""
    monkeypatch.setattr(aa, "alias_query", lambda a, b: aa.AliasResult(AliasKind.NO_ALIAS, "mutant"))
    r = run(src)
    checks = {c["name"]: c["passed"] for c in r["validation"]["checks"]}
    assert checks["dependences_preserved"] is True       # fooled, as expected
    assert checks["differential_execution"] is False     # but this catches it
    assert r["status"] == "REJECTED_BY_VALIDATOR"


# ---------------------------------------------------------------------------
# Invariants over random programs (stronger generator than test_validator's fuzz)
# ---------------------------------------------------------------------------
def _random_program(rng):
    regs = [f"R{i}" for i in range(1, 8)]
    lines = []
    for k in range(rng.randint(3, 12)):
        c = rng.random()
        base = rng.choice(["A", "A", "B", "R9", "R10", "R11"])
        off = rng.choice([0, 4, 8, 12, 16, 24, 32, 40, 72])
        size = rng.choice(["", "", ".4", ".2"])
        if c < 0.35:
            lines.append(f"LOAD{size} {rng.choice(regs)}, [{base}+{off}]")
        elif c < 0.6:
            lines.append(f"STORE{size} [{base}+{off}], {rng.choice(regs)}")
        elif c < 0.72:
            lines.append(f"ADD {rng.choice(regs)}, {rng.choice(regs)}, {rng.choice(regs)}")
        elif c < 0.8:
            lines.append(f"ADD R9, R9, {rng.choice([0, 8, -8])}")
        elif c < 0.87:
            lines.append(f"ADDR R10, A, {rng.choice([0, 8, 16])}")
        elif c < 0.92:
            lines.append("CALL g")
        elif c < 0.96:
            lines.append(f"LOAD R11, [{rng.choice(['A', 'R11'])}+0]")   # pointer loaded from memory
        else:
            lines += [f"BR b{k}", f"b{k}:"]
    return "\n".join(lines)


def test_fuzz_invariants():
    rng = random.Random(2026)
    optimized = 0
    for _ in range(250):
        src = _random_program(rng)
        for target in ("ConsSBR", "ConsSBR64", "Cons"):
            r = run_caif(src, FusionConfig(target=target))
            assert r["validation"]["valid"] and r["status"] != "REJECTED_BY_VALIDATOR", src
            m = r["metrics"]
            assert m["consecutive_after"] >= m["consecutive_before"], src
            assert m["consecutive_after"] >= len(r["pairs"]), src
            # every formed pair is adjacent and compatible in the final sequence
            final = [i["id"] for i in r["optimized"]]
            for h, t in r["pairs"]:
                assert final.index(t) == final.index(h) + 1, (src, h, t)
            if r["status"] == "OPTIMIZED":
                optimized += 1
    assert optimized > 30     # the fuzz really exercises transformations


def test_opportunity_count_is_maximum_on_adjacent_pairs():
    # greedy left-to-right on a chain of adjacent compatible pairs yields the maximum matching
    seq = parse_ok("LOAD R1, [A+0]\nLOAD R2, [A+8]\nLOAD R3, [A+16]\nLOAD R4, [A+24]")
    assert len(consecutive_opportunities(seq, FusionConfig())) == 2


# ---------------------------------------------------------------------------
# Experiment results are computed, aggregated correctly and not hardcoded
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_results(tmp_path, monkeypatch):
    import experiments.results as res
    monkeypatch.setattr(res, "ROOT", tmp_path)
    monkeypatch.setattr(res, "DATA_DIR", tmp_path)
    monkeypatch.setattr(res, "EXP_DIR", tmp_path / "experiments")
    return tmp_path


def test_experiment_totals_are_sums_of_rows(tmp_results):
    from experiments.experiment_runner import run_suite
    run = run_suite(sweep=False)
    for k in ("instructions", "memory_instructions", "consecutive_before", "consecutive_after",
              "successful_rearrangements", "rejected_rearrangements", "rearrangements_attempted"):
        assert run["totals"][k] == sum(r[k] for r in run["rows"]), k
    t = run["totals"]
    assert t["additional_opportunities"] == t["consecutive_after"] - t["consecutive_before"]
    assert t["fused_memory_ops_after_pct"] == round(100 * 2 * t["consecutive_after"] / t["memory_instructions"], 2)
    for r in run["rows"]:
        if r["consecutive_before"] == 0:
            assert r["percent_increase"] is None          # undefined, never "infinite" or 0
        else:
            assert r["percent_increase"] == round(100 * (r["consecutive_after"] - r["consecutive_before"]) / r["consecutive_before"], 2)


def test_experiment_results_follow_the_input(tmp_results, monkeypatch):
    """Swap the sample list: the results must change accordingly (nothing is hardcoded)."""
    import experiments.experiment_runner as er
    fake = [{"id": "x1", "title": "x", "kind": "success", "should_rearrange": True, "config": {},
             "source": "L1: LOAD R1, [A+0]\nNOP\nL2: LOAD R2, [A+8]\nS1: STORE [B+0], R1\nNOP\nS2: STORE [B+8], R2"}]
    monkeypatch.setattr(er, "SAMPLES", fake)
    run = er.run_suite(sweep=False)
    assert len(run["rows"]) == 1
    assert run["rows"][0]["consecutive_before"] == 0 and run["rows"][0]["consecutive_after"] == 2
