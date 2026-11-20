"""Internal instruction representation for the CAIF educational ISA.

This is a *simulated* assembly-like instruction set designed for teaching.
It is NOT RISC-V (or any real) machine code. Each line of the input program
becomes one `Instruction` object.

Design notes
------------
* Registers are R0..R31. A special implicit register ``FLAGS`` is written by
  CMP and read by conditional branches.
* A memory operand is ``[BASE+OFFSET]`` where BASE is either
    - a *symbol* (e.g. ``A``, ``buf``): a distinct memory object, like a
      global array or a stack slot. Two different symbols never overlap.
    - a *register* (e.g. ``R3``): a pointer held in a register.
* Access size is given by an optional opcode suffix: ``LOAD.4`` = 4 bytes.
  Without a suffix, the configured default size (8 bytes) is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Category(str, Enum):
    LOAD = "LOAD"
    STORE = "STORE"
    ARITH = "ARITH"          # ADD, SUB, MUL
    MOVE = "MOVE"            # MOV
    ADDRESS = "ADDRESS"      # ADDR (address calculation)
    COMPARE = "COMPARE"      # CMP
    BRANCH = "BRANCH"        # BR / BEQ / BNE  (basic-block terminators)
    CALL = "CALL"            # CALL (opaque; may read/write any memory)
    OTHER = "OTHER"          # NOP


class MemKind(str, Enum):
    NONE = "NONE"
    READ = "READ"
    WRITE = "WRITE"
    READ_WRITE = "READ_WRITE"   # CALL: unknown side effects


@dataclass(frozen=True)
class OpcodeSpec:
    name: str
    category: Category
    description: str


# Registry of supported opcodes. To add an opcode: add it here and teach the
# parser its operand format (parser.OPERAND_FORMATS) and the interpreter its
# semantics (validator.Interpreter).
OPCODES: dict[str, OpcodeSpec] = {
    "LOAD": OpcodeSpec("LOAD", Category.LOAD, "Load from memory into a register"),
    "STORE": OpcodeSpec("STORE", Category.STORE, "Store a register into memory"),
    "ADD": OpcodeSpec("ADD", Category.ARITH, "Integer addition"),
    "SUB": OpcodeSpec("SUB", Category.ARITH, "Integer subtraction"),
    "MUL": OpcodeSpec("MUL", Category.ARITH, "Integer multiplication"),
    "MOV": OpcodeSpec("MOV", Category.MOVE, "Copy a register or immediate"),
    "ADDR": OpcodeSpec("ADDR", Category.ADDRESS, "Address calculation: Rd = &SYMBOL + offset"),
    "CMP": OpcodeSpec("CMP", Category.COMPARE, "Compare two operands, writes FLAGS"),
    "BR": OpcodeSpec("BR", Category.BRANCH, "Unconditional branch (ends a basic block)"),
    "BEQ": OpcodeSpec("BEQ", Category.BRANCH, "Branch if FLAGS == equal (ends a basic block)"),
    "BNE": OpcodeSpec("BNE", Category.BRANCH, "Branch if FLAGS != equal (ends a basic block)"),
    "CALL": OpcodeSpec("CALL", Category.CALL, "Call an opaque function (memory barrier)"),
    "NOP": OpcodeSpec("NOP", Category.OTHER, "No operation"),
}

FLAGS = "FLAGS"
NUM_REGISTERS = 32
VALID_SIZES = (1, 2, 4, 8)


@dataclass
class MemOperand:
    """A memory reference `[base + offset]` of `size` bytes."""
    base: str                 # symbol name or register name
    base_is_register: bool
    offset: int
    size: int

    def text(self) -> str:
        if self.offset == 0:
            return f"[{self.base}]"
        sign = "+" if self.offset >= 0 else "-"
        return f"[{self.base}{sign}{abs(self.offset)}]"


@dataclass
class Instruction:
    id: str                        # unique ID (user-given, e.g. "L1", or auto "I3")
    index: int                     # position in the ORIGINAL program (0-based)
    line: int                      # source line number (1-based)
    opcode: str
    category: Category
    text: str                      # canonical text, e.g. "LOAD R1, [A+8]"
    dest: Optional[str] = None     # destination register (incl. FLAGS)
    sources: list[str] = field(default_factory=list)   # registers read (incl. address base)
    immediates: list[int] = field(default_factory=list)
    mem: Optional[MemOperand] = None
    mem_kind: MemKind = MemKind.NONE
    symbol: Optional[str] = None   # ADDR's symbol, or CALL/branch target
    block: str = "B0"              # basic block identifier
    explanation: str = ""
    # Filled in by the dependency analyser (IDs of instructions this one depends on)
    depends_on: list[str] = field(default_factory=list)

    @property
    def is_memory(self) -> bool:
        return self.category in (Category.LOAD, Category.STORE)

    @property
    def is_terminator(self) -> bool:
        return self.category == Category.BRANCH

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        d["mem_kind"] = self.mem_kind.value
        return d


def explain(ins: Instruction) -> str:
    """Human-readable explanation of what an instruction does."""
    op = ins.opcode
    if op == "LOAD":
        return f"{ins.dest} ← memory{ins.mem.text()} ({ins.mem.size} bytes)"
    if op == "STORE":
        return f"memory{ins.mem.text()} ← {ins.sources[-1]} ({ins.mem.size} bytes)"
    if op in ("ADD", "SUB", "MUL"):
        sym = {"ADD": "+", "SUB": "-", "MUL": "×"}[op]
        rhs = ins.sources[1] if len(ins.sources) > 1 else str(ins.immediates[0])
        return f"{ins.dest} ← {ins.sources[0]} {sym} {rhs}"
    if op == "MOV":
        return f"{ins.dest} ← {ins.sources[0] if ins.sources else ins.immediates[0]}"
    if op == "ADDR":
        return f"{ins.dest} ← address of {ins.symbol} + {ins.immediates[0]}"
    if op == "CMP":
        rhs = ins.sources[1] if len(ins.sources) > 1 else str(ins.immediates[0])
        return f"FLAGS ← compare({ins.sources[0]}, {rhs})"
    if op == "BR":
        return f"jump to {ins.symbol} (ends basic block {ins.block})"
    if op in ("BEQ", "BNE"):
        cond = "equal" if op == "BEQ" else "not equal"
        return f"if FLAGS is {cond}, jump to {ins.symbol} (ends basic block {ins.block})"
    if op == "CALL":
        return f"call {ins.symbol}: may read/write any memory (barrier for memory ops)"
    return "no operation"
