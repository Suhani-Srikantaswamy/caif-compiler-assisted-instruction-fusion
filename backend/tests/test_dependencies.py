from core.alias_analyzer import AddressAnalysis, AliasKind
from core.dependency_analyzer import build_dependency_graph
from helpers import parse_ok


def edges(src):
    seq = parse_ok(src)
    return {(e.src, e.dst, e.type, e.subtype) for e in build_dependency_graph(seq).edges}


def test_raw():
    assert ("L1", "A1", "RAW", "R1") in edges("L1: LOAD R1, [A]\nA1: ADD R2, R1, R3")


def test_address_dependency_is_labelled():
    assert ("D", "L", "ADDRESS", "R3") in edges("D: ADDR R3, A, 8\nL: LOAD R1, [R3+0]")


def test_war():
    assert ("X", "Y", "WAR", "R2") in edges("X: ADD R1, R2, 1\nY: LOAD R2, [A]")


def test_waw():
    assert ("X", "Y", "WAW", "R1") in edges("X: MOV R1, 1\nY: LOAD R1, [A]")


def test_no_register_edge_between_independent():
    assert not edges("X: ADD R1, R2, R3\nY: MUL R4, R5, R6")


def test_nearest_writer_only():
    e = edges("A1: MOV R1, 1\nA2: MOV R1, 2\nU: ADD R2, R1, 0")
    assert ("A2", "U", "RAW", "R1") in e and ("A1", "U", "RAW", "R1") not in e
    assert ("A1", "A2", "WAW", "R1") in e


def test_memory_raw_war_waw():
    e = edges("S: STORE [A], R1\nL: LOAD R2, [A]\nT: STORE [A], R3")
    assert ("S", "L", "MEMORY", "MEM-RAW") in e
    assert ("L", "T", "MEMORY", "MEM-WAR") in e
    assert ("S", "T", "MEMORY", "MEM-WAW") in e


def test_two_loads_never_conflict():
    assert not edges("X: LOAD R1, [A]\nY: LOAD R2, [A]")


def test_call_is_memory_barrier():
    e = edges("X: LOAD R1, [A]\nC: CALL f\nY: LOAD R2, [B]")
    assert ("X", "C", "MEMORY", "CALL") in e and ("C", "Y", "MEMORY", "CALL") in e


def test_no_edges_across_blocks():
    e = edges("X: STORE [A], R1\nBR n\nn:\nY: LOAD R1, [A]")
    assert not any(s == "X" and d == "Y" for s, d, *_ in e)


# ---- alias analysis --------------------------------------------------------
def alias(src, a, b):
    seq = parse_ok(src)
    return AddressAnalysis(seq).alias(a, b).kind


def test_alias_same_base_same_offset():
    assert alias("X: LOAD R1, [A+8]\nY: STORE [A+8], R2", "X", "Y") == AliasKind.MUST_ALIAS


def test_alias_same_base_disjoint_offsets():
    assert alias("X: LOAD R1, [A+0]\nY: STORE [A+8], R2", "X", "Y") == AliasKind.NO_ALIAS


def test_alias_same_base_partial_overlap():
    assert alias("X: LOAD R1, [A+0]\nY: STORE.4 [A+4], R2", "X", "Y") == AliasKind.PARTIAL_ALIAS


def test_alias_different_symbols():
    assert alias("X: LOAD R1, [A]\nY: STORE [B], R2", "X", "Y") == AliasKind.NO_ALIAS


def test_alias_unknown_pointers():
    assert alias("X: LOAD R1, [R10]\nY: STORE [R11], R2", "X", "Y") == AliasKind.MAY_ALIAS
    assert alias("X: LOAD R1, [A]\nY: STORE [R11], R2", "X", "Y") == AliasKind.MAY_ALIAS


def test_alias_resolves_address_arithmetic():
    src = "ADDR R3, A, 8\nADD R4, R3, 8\nMOV R5, R4\nX: LOAD R1, [A+16]\nY: STORE [R5+0], R2"
    seq = parse_ok(src)
    aa = AddressAnalysis(seq)
    assert aa.mem["Y"].addr.base == "A" and aa.mem["Y"].addr.offset == 16
    assert aa.alias("X", "Y").kind == AliasKind.MUST_ALIAS


def test_redefined_base_register_is_a_different_value():
    src = "X: LOAD R1, [R3+0]\nLOAD R3, [R9]\nY: STORE [R3+0], R2"
    assert alias(src, "X", "Y") == AliasKind.MAY_ALIAS
