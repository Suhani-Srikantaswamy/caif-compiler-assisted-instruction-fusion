import pytest

from core.instruction import Category, MemKind
from core.parser import parse_program
from helpers import parse_ok


def errors(src):
    r = parse_program(src)
    assert not r.ok
    return [e.message for e in r.errors]


def test_parses_all_opcodes():
    seq = parse_ok("""
        L1: LOAD R1, [A+0]
        LOAD.4 R2, [R3+8]
        STORE [B+0], R2
        STORE.2 [R4-2], R1
        ADD R5, R1, R2
        SUB R6, R5, 3
        MUL R7, R6, R6
        MOV R8, R7
        MOV R9, 42
        ADDR R10, A, 16
        ADDR R11, B
        CMP R1, 0
        CALL foo
        NOP
        BNE end
        end:
        BR end
    """)
    assert [i.opcode for i in seq] == ["LOAD", "LOAD", "STORE", "STORE", "ADD", "SUB", "MUL", "MOV", "MOV",
                                        "ADDR", "ADDR", "CMP", "CALL", "NOP", "BNE", "BR"]


def test_instruction_representation_fields():
    ld, st, add = parse_ok("L1: LOAD.4 R1, [R3+8]\nSTORE [A+16], R1\nADD R2, R1, 4")
    assert (ld.id, ld.opcode, ld.category, ld.dest, ld.sources) == ("L1", "LOAD", Category.LOAD, "R1", ["R3"])
    assert (ld.mem.base, ld.mem.base_is_register, ld.mem.offset, ld.mem.size) == ("R3", True, 8, 4)
    assert ld.mem_kind == MemKind.READ and ld.block == "B0" and ld.explanation
    assert st.mem.base == "A" and not st.mem.base_is_register and st.sources == ["R1"] and st.mem_kind == MemKind.WRITE
    assert st.mem.size == 8   # default size
    assert add.immediates == [4] and add.sources == ["R1"]
    assert st.id == "I1" and add.id == "I2"      # auto IDs


def test_default_size_configurable():
    (ld,) = parse_ok("LOAD R1, [A]", size=4)
    assert ld.mem.size == 4


def test_cmp_writes_flags_and_branch_reads_it():
    cmp_, br = parse_ok("CMP R1, R2\nBEQ x\nx:\nNOP")[:2]
    assert cmp_.dest == "FLAGS" and br.sources == ["FLAGS"]


def test_basic_blocks_split_at_labels_and_branches():
    seq = parse_ok("LOAD R1, [A]\nBR next\nLOAD R2, [A+8]\nnext:\nLOAD R3, [A+16]")
    assert [i.block for i in seq] == ["B0", "B0", "B1", "next"]


def test_comments_and_blank_lines_ignored():
    seq = parse_ok("; header\n\n  LOAD R1, [A+0]   // trailing\n# not a comment? \n" .replace("# not a comment? \n", ""))
    assert len(seq) == 1


def test_hex_and_leading_zero_offsets():
    a, b = parse_ok("LOAD R1, [A+0x10]\nLOAD R2, [A+08]")
    assert a.mem.offset == 16 and b.mem.offset == 8


@pytest.mark.parametrize("src, fragment", [
    ("LAOD R1, [A+0]", "Invalid opcode"),
    ("LOAD R1", "Missing operands"),
    ("ADD R1, R2", "Missing operands"),
    ("LOAD R1, [A+0], R2", "Too many operands"),
    ("LOAD R99, [A+0]", "Invalid register"),
    ("LOAD X1, [A+0]", "Invalid register"),
    ("ADD R1, R2, foo", "Invalid operand"),
    ("LOAD R1, A+0", "Incorrect memory address syntax"),
    ("LOAD R1, [A+0", "Incorrect memory address syntax"),
    ("LOAD R1, [A+x]", "Invalid memory offset"),
    ("LOAD R1, [A+4+4]", "Invalid memory offset"),
    ("LOAD R1, [A-8]", "Invalid memory offset"),
    ("LOAD R1, [A+99999999]", "Invalid memory offset"),
    ("LOAD.3 R1, [A]", "Invalid access-size suffix"),
    ("ADD.4 R1, R2, R3", "Size suffix is only allowed"),
    ("BR nowhere", "not defined"),
    ("", "empty"),
])
def test_invalid_input_reports_errors(src, fragment):
    msgs = errors(src)
    assert any(fragment in m for m in msgs), msgs


def test_duplicate_instruction_ids():
    msgs = errors("L1: LOAD R1, [A]\nL1: LOAD R2, [A+8]")
    assert any("Duplicate instruction ID 'L1'" in m for m in msgs)


def test_all_errors_reported_not_just_first():
    r = parse_program("LAOD R1, [A]\nLOAD R1, [A]\nLOAD R99, [A]")
    assert [e.line for e in r.errors] == [1, 3]
    assert len(r.instructions) == 1   # the valid line is still parsed, nothing silently dropped


def test_auto_ids_avoid_user_ids():
    seq = parse_ok("I1: LOAD R1, [A]\nLOAD R2, [A+8]")
    assert [i.id for i in seq] == ["I1", "I2"]
