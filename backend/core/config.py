"""Fusion target model configuration.

The three targets mirror (in simplified form) the hardware configurations
evaluated in the CAIF paper (Sec. V-B):

* ``ConsSBR``   - fuses consecutive pairs with the Same Base Register whose
                  accesses are *contiguous* in memory.
* ``ConsSBR64`` - fuses consecutive Same-Base-Register pairs whose accesses
                  fall within a ``window_bytes`` region (default 64 B, i.e. a
                  cache line). This is the default target.
* ``Cons``      - also fuses consecutive pairs with Different Base Registers,
                  provided the compiler can prove the distance between them.
                  (In hardware this needs prediction; here it is only an
                  analysis option.)

Helios-style *non-consecutive* fusion is intentionally NOT modelled: the
whole point of CAIF is to make the pairs consecutive in the compiler.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

TARGETS = ("ConsSBR", "ConsSBR64", "Cons")


@dataclass
class FusionConfig:
    target: str = "ConsSBR64"
    window_bytes: int = 64                  # paper: 64-byte range
    allow_load_pairs: bool = True           # LOAD + LOAD
    allow_store_pairs: bool = True          # STORE + STORE
    require_same_size: bool = False
    max_instruction_distance: Optional[int] = None   # None = scan whole basic block (as in the paper)
    default_size: int = 8                   # access size when no .N suffix is given

    def validate(self) -> list[str]:
        errs = []
        if self.target not in TARGETS:
            errs.append(f"Unknown target '{self.target}'. Choose one of {TARGETS}")
        if not (1 <= self.window_bytes <= 4096):
            errs.append("window_bytes must be between 1 and 4096")
        if self.max_instruction_distance is not None and self.max_instruction_distance < 1:
            errs.append("max_instruction_distance must be >= 1 (or null for the whole block)")
        if self.default_size not in (1, 2, 4, 8):
            errs.append("default_size must be 1, 2, 4 or 8")
        if not (self.allow_load_pairs or self.allow_store_pairs):
            errs.append("At least one of LOAD+LOAD or STORE+STORE must be enabled")
        return errs

    @property
    def requires_same_base_register(self) -> bool:
        return self.target in ("ConsSBR", "ConsSBR64")

    @property
    def requires_contiguous(self) -> bool:
        return self.target == "ConsSBR"

    def to_dict(self) -> dict:
        return asdict(self)
