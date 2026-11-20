"""Pydantic request/response models for the HTTP API."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConfigModel(BaseModel):
    target: Literal["ConsSBR", "ConsSBR64", "Cons"] = "ConsSBR64"
    window_bytes: int = Field(64, ge=1, le=4096)
    allow_load_pairs: bool = True
    allow_store_pairs: bool = True
    require_same_size: bool = False
    max_instruction_distance: Optional[int] = Field(None, ge=1)
    default_size: Literal[1, 2, 4, 8] = 8


class SourceRequest(BaseModel):
    source: str = Field(..., max_length=100_000)
    config: ConfigModel = ConfigModel()


class ValidateRequest(SourceRequest):
    order: list[str] = Field(..., description="Proposed instruction order, as instruction IDs")


class ExperimentRequest(BaseModel):
    label: str = Field("", max_length=80)
    overrides: dict[str, Any] = Field(default_factory=dict)
    sweep: bool = True


class SaveConfigRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    config: ConfigModel


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class MemOperandModel(_Open):
    base: str
    base_is_register: bool
    offset: int
    size: int


class InstructionModel(_Open):
    id: str
    index: int
    position: int
    line: int
    opcode: str
    category: str
    text: str
    dest: Optional[str]
    sources: list[str]
    immediates: list[int]
    mem: Optional[MemOperandModel]
    mem_kind: str
    symbol: Optional[str]
    block: str
    explanation: str
    depends_on: list[str]


class ParseErrorModel(BaseModel):
    line: int
    message: str
    text: str = ""


class ParseResponse(BaseModel):
    ok: bool
    instructions: list[InstructionModel]
    errors: list[ParseErrorModel]
    blocks: list[str]


class EdgeModel(BaseModel):
    src: str
    dst: str
    type: str
    subtype: str
    reason: str


class GraphModel(BaseModel):
    nodes: list[str]
    edges: list[EdgeModel]
    counts: dict[str, int]


class ConditionModel(BaseModel):
    name: str
    passed: bool
    detail: str


class CandidateModel(_Open):
    head: str
    tail: str
    head_pos: int
    tail_pos: int
    kind: str
    compatible: bool
    consecutive: bool
    fusion_class: Optional[str]
    byte_distance: Optional[int]
    span_bytes: Optional[int]
    instruction_distance: int
    rearrangement_useful: bool
    conditions: list[ConditionModel]


class AnalyzeResponse(_Open):
    instructions: list[InstructionModel]
    blocks: list[str]
    memory: dict[str, dict[str, Any]]
    graph: GraphModel
    candidates: list[CandidateModel]
    catalyst_reports: dict[str, dict[str, Any]]


class CheckModel(BaseModel):
    name: str
    passed: bool
    details: str


class ValidationModel(BaseModel):
    valid: bool
    checks: list[CheckModel]
    errors: list[str]


class StepModel(_Open):
    number: int
    action: str
    head: str
    tail: str
    pair: dict[str, Any]
    catalyst: Optional[dict[str, Any]]
    before: list[str]
    after: list[str]
    moved: list[str]
    explanation: list[str]


class OptimizeResponse(AnalyzeResponse):
    config: ConfigModel
    status: str
    optimized: list[InstructionModel]
    optimized_graph: GraphModel
    steps: list[StepModel]
    pairs: list[list[str]]
    proposed_order: list[str]
    validation: ValidationModel
    opportunities_before: list[CandidateModel]
    opportunities_after: list[CandidateModel]
    metrics: dict[str, Any]
