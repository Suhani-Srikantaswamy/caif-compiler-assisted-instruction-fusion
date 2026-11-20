"""Stage 2 - Parser: text program -> list[Instruction].

Syntax (one instruction per line, case-insensitive opcodes/registers)::

    ; comment   (also // comment)
    loop:                       block label on its own line -> new basic block
    L1: LOAD R1, [A+0]          optional instruction ID before the colon
    LOAD.4 R5, [R3+8]           .1/.2/.4/.8 suffix = access size in bytes
    STORE [B+0], R2
    ADD R1, R2, R3   |  ADD R1, R2, 4     (SUB, MUL identical)
    MOV R1, R2       |  MOV R1, 7
    ADDR R3, A, 16              R3 = &A + 16  (offset optional, default 0)
    CMP R1, R2       |  CMP R1, 0          writes FLAGS
    BR target  |  BEQ target  |  BNE target   (terminate the basic block)
    CALL foo                    opaque call: may read/write any memory
    NOP

The parser never silently drops a line: every problem becomes a ParseError.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .instruction import (
    FLAGS, NUM_REGISTERS, OPCODES, VALID_SIZES, Category, Instruction, MemKind,
    MemOperand, explain,
)

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REG_LIKE_RE = re.compile(r"^[Rr](\d+)$")
INT_RE = re.compile(r"^[+-]?(0[xX][0-9a-fA-F]+|\d+)$")
MEM_RE = re.compile(r"^\[\s*([^\]+\-\s]+)\s*(?:([+-])\s*([^\]\s]+))?\s*\]$")
MAX_OFFSET = 1 << 20

USAGE = {
    "LOAD": "LOAD Rd, [BASE+OFFSET]",
    "STORE": "STORE [BASE+OFFSET], Rs",
    "ADD": "ADD Rd, Rs1, Rs2|imm",
    "SUB": "SUB Rd, Rs1, Rs2|imm",
    "MUL": "MUL Rd, Rs1, Rs2|imm",
    "MOV": "MOV Rd, Rs|imm",
    "ADDR": "ADDR Rd, SYMBOL[, offset]",
    "CMP": "CMP Rs1, Rs2|imm",
    "BR": "BR label",
    "BEQ": "BEQ label",
    "BNE": "BNE label",
    "CALL": "CALL name",
    "NOP": "NOP",
}


@dataclass
class ParseError:
    line: int
    message: str
    text: str = ""


@dataclass
class ParseResult:
    instructions: list[Instruction] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    default_size: int = 8

    @property
    def ok(self) -> bool:
        return not self.errors


class _LineError(Exception):
    pass


def _strip_comment(line: str) -> str:
    for marker in (";", "//"):
        pos = line.find(marker)
        if pos != -1:
            line = line[:pos]
    return line.strip()


def _split_operands(s: str) -> list[str]:
    """Split on commas that are not inside [...]."""
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _parse_int(tok: str, what: str) -> int:
    if not INT_RE.match(tok):
        raise _LineError(f"Invalid {what} '{tok}': expected an integer (e.g. 8, -4, 0x10)")
    return int(tok, 16) if tok.lstrip("+-").startswith(("0x", "0X")) else int(tok, 10)


def _parse_reg(tok: str, role: str) -> str:
    m = REG_LIKE_RE.match(tok)
    if not m:
        raise _LineError(f"Invalid register '{tok}' for {role}: registers are R0..R{NUM_REGISTERS - 1}")
    n = int(m.group(1))
    if n >= NUM_REGISTERS:
        raise _LineError(f"Invalid register '{tok}': only R0..R{NUM_REGISTERS - 1} exist")
    return f"R{n}"


def _is_reg_token(tok: str) -> bool:
    return bool(REG_LIKE_RE.match(tok))


def _parse_reg_or_imm(tok: str, role: str) -> tuple[str | None, int | None]:
    if _is_reg_token(tok):
        return _parse_reg(tok, role), None
    if INT_RE.match(tok):
        return None, _parse_int(tok, "immediate")
    raise _LineError(f"Invalid operand '{tok}' for {role}: expected a register (R0..R31) or an integer")


def _parse_mem(tok: str, size: int) -> MemOperand:
    m = MEM_RE.match(tok.strip())
    if not m:
        raise _LineError(
            f"Incorrect memory address syntax '{tok}': expected [BASE], [BASE+OFFSET] or [BASE-OFFSET]")
    base, sign, off_tok = m.group(1), m.group(2), m.group(3)
    offset = 0
    if sign:
        if not INT_RE.match(off_tok) or off_tok.startswith(("+", "-")):
            raise _LineError(f"Invalid memory offset '{off_tok}' in '{tok}': offset must be an integer constant")
        offset = _parse_int(off_tok, "memory offset")
        if sign == "-":
            offset = -offset
    if abs(offset) > MAX_OFFSET:
        raise _LineError(f"Invalid memory offset {offset}: magnitude must be <= {MAX_OFFSET}")
    if _is_reg_token(base):
        return MemOperand(_parse_reg(base, "memory base"), True, offset, size)
    if not IDENT_RE.match(base) or base.upper() == FLAGS:
        raise _LineError(f"Invalid memory base '{base}': use a symbol name (e.g. A) or a register (e.g. R3)")
    if offset < 0:
        raise _LineError(
            f"Invalid memory offset {offset} for symbol '{base}': a symbol names the start of an object, "
            "so its offset cannot be negative")
    return MemOperand(base, False, offset, size)


def _expect(ops: list[str], n: int, opcode: str) -> None:
    if len(ops) < n:
        raise _LineError(f"Missing operands for {opcode}: expected `{USAGE[opcode]}`, got {len(ops)} operand(s)")
    if len(ops) > n:
        raise _LineError(f"Too many operands for {opcode}: expected `{USAGE[opcode]}`, got {len(ops)}")


def _build(opcode: str, size_suffix: int | None, ops: list[str], default_size: int) -> dict:
    """Return the fields of an Instruction for one opcode + operand list."""
    spec = OPCODES[opcode]
    f: dict = {"opcode": opcode, "category": spec.category, "sources": [], "immediates": []}
    if size_suffix is not None and spec.category not in (Category.LOAD, Category.STORE):
        raise _LineError(f"Size suffix is only allowed on LOAD/STORE, not {opcode}")
    size = size_suffix or default_size

    if opcode == "LOAD":
        _expect(ops, 2, opcode)
        f["dest"] = _parse_reg(ops[0], "LOAD destination")
        mem = _parse_mem(ops[1], size)
        f["mem"], f["mem_kind"] = mem, MemKind.READ
        if mem.base_is_register:
            f["sources"] = [mem.base]
    elif opcode == "STORE":
        _expect(ops, 2, opcode)
        mem = _parse_mem(ops[0], size)
        value = _parse_reg(ops[1], "STORE value")
        f["mem"], f["mem_kind"] = mem, MemKind.WRITE
        f["sources"] = ([mem.base] if mem.base_is_register else []) + [value]
    elif opcode in ("ADD", "SUB", "MUL"):
        _expect(ops, 3, opcode)
        f["dest"] = _parse_reg(ops[0], f"{opcode} destination")
        f["sources"] = [_parse_reg(ops[1], f"{opcode} first source")]
        reg, imm = _parse_reg_or_imm(ops[2], f"{opcode} second source")
        if reg:
            f["sources"].append(reg)
        else:
            f["immediates"].append(imm)
    elif opcode == "MOV":
        _expect(ops, 2, opcode)
        f["dest"] = _parse_reg(ops[0], "MOV destination")
        reg, imm = _parse_reg_or_imm(ops[1], "MOV source")
        if reg:
            f["sources"].append(reg)
        else:
            f["immediates"].append(imm)
    elif opcode == "ADDR":
        if len(ops) == 2:
            ops = ops + ["0"]
        _expect(ops, 3, opcode)
        f["dest"] = _parse_reg(ops[0], "ADDR destination")
        if _is_reg_token(ops[1]) or not IDENT_RE.match(ops[1]):
            raise _LineError(f"ADDR expects a symbol name as its second operand, got '{ops[1]}'")
        f["symbol"] = ops[1]
        off = _parse_int(ops[2], "ADDR offset")
        if off < 0:
            raise _LineError(f"Invalid ADDR offset {off}: offsets into a symbol cannot be negative")
        f["immediates"].append(off)
    elif opcode == "CMP":
        _expect(ops, 2, opcode)
        f["dest"] = FLAGS
        f["sources"] = [_parse_reg(ops[0], "CMP first operand")]
        reg, imm = _parse_reg_or_imm(ops[1], "CMP second operand")
        if reg:
            f["sources"].append(reg)
        else:
            f["immediates"].append(imm)
    elif opcode in ("BR", "BEQ", "BNE"):
        _expect(ops, 1, opcode)
        if not IDENT_RE.match(ops[0]):
            raise _LineError(f"Invalid branch target '{ops[0]}'")
        f["symbol"] = ops[0]
        if opcode != "BR":
            f["sources"] = [FLAGS]
    elif opcode == "CALL":
        _expect(ops, 1, opcode)
        if not IDENT_RE.match(ops[0]):
            raise _LineError(f"Invalid function name '{ops[0]}'")
        f["symbol"] = ops[0]
        f["mem_kind"] = MemKind.READ_WRITE
    elif opcode == "NOP":
        _expect(ops, 0, opcode)
    return f


def canonical_text(ins: Instruction) -> str:
    op = ins.opcode
    sfx = lambda: f".{ins.mem.size}"  # noqa: E731
    if op == "LOAD":
        return f"LOAD{sfx()} {ins.dest}, {ins.mem.text()}"
    if op == "STORE":
        return f"STORE{sfx()} {ins.mem.text()}, {ins.sources[-1]}"
    if op in ("ADD", "SUB", "MUL"):
        rhs = ins.sources[1] if len(ins.sources) > 1 else str(ins.immediates[0])
        return f"{op} {ins.dest}, {ins.sources[0]}, {rhs}"
    if op == "MOV":
        return f"MOV {ins.dest}, {ins.sources[0] if ins.sources else ins.immediates[0]}"
    if op == "ADDR":
        return f"ADDR {ins.dest}, {ins.symbol}, {ins.immediates[0]}"
    if op == "CMP":
        rhs = ins.sources[1] if len(ins.sources) > 1 else str(ins.immediates[0])
        return f"CMP {ins.sources[0]}, {rhs}"
    if op in ("BR", "BEQ", "BNE", "CALL"):
        return f"{op} {ins.symbol}"
    return op


def parse_program(source: str, default_size: int = 8) -> ParseResult:
    """Parse a whole program. Collects *all* errors instead of stopping at the first."""
    result = ParseResult(default_size=default_size)
    if default_size not in VALID_SIZES:
        result.errors.append(ParseError(0, f"Default access size must be one of {VALID_SIZES}"))
        return result

    pending: list[tuple[int, str | None, str, str]] = []   # (line, id, body, raw)
    labels: dict[str, int] = {}
    block_starts: dict[int, str] = {}   # index-into-pending -> label name
    ids_seen: dict[str, int] = {}

    for lineno, raw in enumerate(source.splitlines(), start=1):
        line = _strip_comment(raw)
        if not line:
            continue
        ins_id = None
        if ":" in line:
            head, _, rest = line.partition(":")
            head, rest = head.strip(), rest.strip()
            if not IDENT_RE.match(head):
                result.errors.append(ParseError(lineno, f"Invalid label or instruction ID '{head}'", raw.strip()))
                continue
            if not rest:   # block label on its own line
                if head in labels:
                    result.errors.append(ParseError(lineno, f"Duplicate block label '{head}' (first defined on line {labels[head]})", raw.strip()))
                else:
                    labels[head] = lineno
                    block_starts[len(pending)] = head
                continue
            ins_id, line = head, rest
            if ins_id in ids_seen:
                result.errors.append(ParseError(
                    lineno, f"Duplicate instruction ID '{ins_id}' (already used on line {ids_seen[ins_id]})", raw.strip()))
                continue
            ids_seen[ins_id] = lineno
        pending.append((lineno, ins_id, line, raw.strip()))

    # Assign basic blocks: new block at each label and after each terminator.
    used_ids = set(ids_seen) | set(labels)
    auto_n = 0
    block_no = 0

    def fresh_block_name() -> str:
        # Auto-generated block names must never collide with a user label (audit fix:
        # a label called "B0" used to merge two different blocks into one).
        nonlocal block_no
        while f"B{block_no}" in labels:
            block_no += 1
        return f"B{block_no}"

    current_block = block_starts.get(0) or fresh_block_name()
    instructions: list[Instruction] = []
    prev_terminator = False
    for k, (lineno, ins_id, body, raw) in enumerate(pending):
        if k in block_starts:
            current_block = block_starts[k]
        elif prev_terminator:
            block_no += 1
            current_block = fresh_block_name()
        prev_terminator = False

        parts = body.split(None, 1)
        mnemonic = parts[0].upper()
        operand_str = parts[1] if len(parts) > 1 else ""
        size_suffix = None
        if "." in mnemonic:
            mnemonic, _, sfx = mnemonic.partition(".")
            if not sfx.isdigit() or int(sfx) not in VALID_SIZES:
                result.errors.append(ParseError(lineno, f"Invalid access-size suffix '.{sfx}': use one of .1 .2 .4 .8", raw))
                continue
            size_suffix = int(sfx)
        if mnemonic not in OPCODES:
            result.errors.append(ParseError(
                lineno, f"Invalid opcode '{parts[0]}'. Supported: {', '.join(OPCODES)}", raw))
            continue
        try:
            fields = _build(mnemonic, size_suffix, _split_operands(operand_str), default_size)
        except _LineError as e:
            result.errors.append(ParseError(lineno, str(e), raw))
            continue

        if ins_id is None:
            auto_n += 1
            while f"I{auto_n}" in used_ids:
                auto_n += 1
            ins_id = f"I{auto_n}"
            used_ids.add(ins_id)
        ins = Instruction(id=ins_id, index=len(instructions), line=lineno, text="", block=current_block, **fields)
        ins.text = canonical_text(ins)
        ins.explanation = explain(ins)
        instructions.append(ins)
        prev_terminator = ins.is_terminator

    for ins in instructions:
        if ins.is_terminator and ins.symbol not in labels:
            result.errors.append(ParseError(ins.line, f"Branch target '{ins.symbol}' is not defined as a label", ins.text))

    if not instructions and not result.errors:
        result.errors.append(ParseError(0, "The program is empty: enter at least one instruction"))

    result.instructions = instructions
    seen = []
    for ins in instructions:
        if ins.block not in seen:
            seen.append(ins.block)
    result.blocks = seen
    return result
