from core.config import FusionConfig
from core.parser import parse_program
from core.pipeline import run_caif


def parse_ok(src, size=8):
    r = parse_program(src, size)
    assert r.ok, [e.message for e in r.errors]
    return r.instructions


def run(src, **cfg):
    return run_caif(src, FusionConfig(**cfg))


def order(result):
    return [i["id"] for i in result["optimized"]]
