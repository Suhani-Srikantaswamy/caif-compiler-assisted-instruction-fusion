from core.config import FusionConfig
from core.fusion_detector import check_pair, consecutive_opportunities, find_candidate_pairs
from helpers import parse_ok


def pc(src, h=0, t=1, **cfg):
    seq = parse_ok(src)
    return check_pair(seq, h, t, FusionConfig(**cfg))


def failed(p):
    return {c.name for c in p.conditions if not c.passed}


def test_contiguous_same_base():
    p = pc("LOAD R1, [A+0]\nLOAD R2, [A+8]")
    assert p.compatible and p.consecutive and p.fusion_class == "SBR-contiguous"
    assert p.byte_distance == 8 and p.span_bytes == 16


def test_window_non_contiguous():
    p = pc("LOAD R1, [A+0]\nLOAD R2, [A+40]")
    assert p.compatible and p.fusion_class == "SBR-window" and p.span_bytes == 48


def test_window_boundary_exactly_64():
    assert pc("LOAD R1, [A+0]\nLOAD R2, [A+56]").compatible          # span 64
    assert "within_window" in failed(pc("LOAD R1, [A+0]\nLOAD R2, [A+57]"))  # span 65


def test_window_configurable():
    assert pc("LOAD R1, [A+0]\nLOAD R2, [A+100]", window_bytes=128).compatible


def test_reverse_order_addresses():
    p = pc("LOAD R1, [A+8]\nLOAD R2, [A+0]")
    assert p.compatible and p.byte_distance == -8


def test_sizes_count_toward_span():
    assert pc("LOAD.4 R1, [A+0]\nLOAD.4 R2, [A+60]").compatible       # span 64
    assert not pc("LOAD.8 R1, [A+0]\nLOAD.8 R2, [A+60]").compatible   # span 68


def test_overlap_rejected():
    assert "non_overlapping" in failed(pc("LOAD R1, [A+0]\nLOAD.4 R2, [A+4]"))


def test_different_symbols_incompatible():
    assert "provable_distance" in failed(pc("LOAD R1, [A+0]\nLOAD R2, [B+8]"))


def test_load_store_mix_incompatible():
    assert "same_operation" in failed(pc("LOAD R1, [A+0]\nSTORE [A+8], R2"))


def test_pair_types_configurable():
    assert not pc("STORE [A], R1\nSTORE [A+8], R2", allow_store_pairs=False).compatible


def test_same_destination_rejected():
    assert "distinct_destinations" in failed(pc("LOAD R1, [A+0]\nLOAD R1, [A+8]"))


def test_cons_sbr_requires_contiguous():
    assert pc("LOAD R1, [A+0]\nLOAD R2, [A+8]", target="ConsSBR").compatible
    assert "contiguous" in failed(pc("LOAD R1, [A+0]\nLOAD R2, [A+16]", target="ConsSBR"))


def test_different_base_register_depends_on_target():
    src = "ADDR R3, A, 0\nADDR R4, A, 8\nLOAD R1, [R3+0]\nLOAD R2, [R4+0]"
    assert "same_base_register" in failed(pc(src, 2, 3))
    p = pc(src, 2, 3, target="Cons")
    assert p.compatible and p.fusion_class == "DBR"


def test_same_register_redefined_is_not_same_base():
    src = "LOAD R1, [R3+0]\nADD R3, R3, 8\nLOAD R2, [R3+0]"
    p = pc(src, 0, 2)
    assert "same_base_register" in failed(p)
    assert pc(src, 0, 2, target="Cons").compatible   # R3+8 is still provable relative to old R3


def test_tail_depending_on_head_incompatible():
    p = pc("LOAD R4, [R4+0]\nLOAD R5, [R4+8]")
    assert "tail_independent_of_head" in failed(p)


def test_different_blocks_incompatible():
    seq = parse_ok("LOAD R1, [A]\nBR n\nn:\nLOAD R2, [A+8]")
    assert "same_basic_block" in failed(check_pair(seq, 0, 2, FusionConfig()))


def test_max_instruction_distance():
    src = "LOAD R1, [A]\nNOP\nNOP\nLOAD R2, [A+8]"
    assert pc(src, 0, 3).compatible
    assert "instruction_distance" in failed(pc(src, 0, 3, max_instruction_distance=2))


def test_candidate_listing_and_flags():
    seq = parse_ok("L1: LOAD R1, [A+0]\nNOP\nL2: LOAD R2, [A+8]\nL3: LOAD R3, [B]")
    cands = find_candidate_pairs(seq, FusionConfig())
    comp = [(c.head, c.tail) for c in cands if c.compatible]
    assert comp == [("L1", "L2")]
    c = cands[0]
    assert not c.consecutive and c.rearrangement_useful and c.instruction_distance == 2


def test_consecutive_opportunities_greedy_non_overlapping():
    seq = parse_ok("LOAD R1, [A+0]\nLOAD R2, [A+8]\nLOAD R3, [A+16]")
    opps = consecutive_opportunities(seq, FusionConfig())
    assert [(o.head, o.tail) for o in opps] == [("I1", "I2")]   # each instruction fuses at most once
