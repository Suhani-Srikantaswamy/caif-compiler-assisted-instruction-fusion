import random

from core.config import FusionConfig
from core.metrics import compute_metrics  # noqa: F401  (imported for coverage of module)
from core.validator import check_order, differential_test, validate
from helpers import parse_ok, run


def reorder(seq, ids):
    by = {i.id: i for i in seq}
    return [by[x] for x in ids]


def test_identity_is_valid():
    seq = parse_ok("A: LOAD R1, [A]\nB: ADD R2, R1, 1")
    assert validate(seq, list(seq)).valid


def test_detects_missing_and_duplicate():
    seq = parse_ok("A: LOAD R1, [A]\nB: ADD R2, R1, 1")
    assert not check_order(seq, [seq[0]]).valid
    assert not check_order(seq, [seq[0], seq[0]]).valid


def test_detects_raw_violation():
    seq = parse_ok("A: LOAD R1, [A]\nB: ADD R2, R1, 1")
    r = validate(seq, reorder(seq, ["B", "A"]))
    assert not r.valid and any("writes R1" in e for e in r.errors)


def test_detects_memory_violation_statically_and_dynamically():
    seq = parse_ok("S: STORE [A+8], R2\nL: LOAD R3, [A+8]")
    bad = reorder(seq, ["L", "S"])
    assert not check_order(seq, bad).valid
    d = differential_test(seq, bad)
    assert not d.passed


def test_detects_may_alias_violation_dynamically():
    seq = parse_ok("S: STORE [R11+0], R2\nL: LOAD R3, [R10+0]")
    assert not differential_test(seq, reorder(seq, ["L", "S"])).passed   # full-aliasing scenario catches it


def test_detects_block_crossing():
    seq = parse_ok("A: LOAD R1, [A]\nBR n\nn:\nB: LOAD R2, [B]")
    r = check_order(seq, reorder(seq, ["A", "B", "I1"]))
    assert not r.valid


def test_detects_call_crossing():
    seq = parse_ok("A: LOAD R1, [A]\nC: CALL f")
    assert not check_order(seq, reorder(seq, ["C", "A"])).valid


def test_independent_swap_valid():
    seq = parse_ok("A: LOAD R1, [A]\nB: STORE [B], R2\nC: ADD R5, R6, R7")
    assert validate(seq, reorder(seq, ["C", "B", "A"])).valid


def test_fuzz_optimizer_always_validates():
    """Random programs: every optimized result must pass the independent validator."""
    rng = random.Random(7)
    regs = [f"R{i}" for i in range(1, 8)]
    for _ in range(300):
        lines = []
        for _k in range(rng.randint(3, 10)):
            c = rng.random()
            base = rng.choice(["A", "A", "B", "R9", "R10"])
            off = rng.choice([0, 8, 16, 24, 32, 72])
            if c < 0.35:
                lines.append(f"LOAD {rng.choice(regs)}, [{base}+{off}]")
            elif c < 0.6:
                lines.append(f"STORE [{base}+{off}], {rng.choice(regs)}")
            elif c < 0.75:
                lines.append(f"ADD {rng.choice(regs)}, {rng.choice(regs)}, {rng.choice(regs)}")
            elif c < 0.85:
                lines.append(f"ADD R9, R9, {rng.choice([0, 8])}")
            elif c < 0.95:
                lines.append(f"ADDR R10, A, {rng.choice([0, 8, 16])}")
            else:
                lines.append("CALL g")
        for target in ("ConsSBR64", "Cons"):
            r = run("\n".join(lines), target=target)
            assert r["status"] != "REJECTED_BY_VALIDATOR", lines
            assert r["validation"]["valid"], lines
            assert r["metrics"]["consecutive_after"] >= r["metrics"]["consecutive_before"] or \
                r["metrics"]["successful_rearrangements"] == 0, lines


# ---- metrics -------------------------------------------------------------
def test_metrics_counts():
    r = run("L1: LOAD R1, [A+0]\nX: NOP\nL2: LOAD R2, [A+8]\nS1: STORE [B], R1\nS2: STORE [B+8], R2")
    m = r["metrics"]
    assert m["total_instructions"] == 5 and m["memory_instructions"] == 4
    assert m["consecutive_before"] == 1 and m["consecutive_after"] == 2
    assert m["additional_opportunities"] == 1 and m["percent_increase"] == 100.0
    assert m["successful_rearrangements"] == 1 and m["rejected_rearrangements"] == 0


def test_percent_undefined_when_before_is_zero():
    m = run("L1: LOAD R1, [A+0]\nX: NOP\nL2: LOAD R2, [A+8]")["metrics"]
    assert m["consecutive_before"] == 0 and m["percent_increase"] is None
