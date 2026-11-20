"""FastAPI application. All compiler logic lives in core/; this file is only the HTTP layer.

Run:  uvicorn main:app --reload --port 8000   (from backend/)
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api_schemas import (
    AnalyzeResponse, ConfigModel, ExperimentRequest, OptimizeResponse, ParseResponse, SaveConfigRequest,
    SourceRequest, ValidateRequest, ValidationModel,
)
from core.config import FusionConfig
from core.parser import parse_program
from core.pipeline import PipelineError, analyze, run_caif
from core.validator import validate
from examples.sample_programs import SAMPLES
from experiments.experiment_runner import render_markdown, run_suite
from experiments.results import list_runs, load_configs, load_run, save_config

app = FastAPI(title="CAIF - Compiler-Assisted Instruction Fusion (educational prototype)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)


def _cfg(m: ConfigModel) -> FusionConfig:
    return FusionConfig(**m.model_dump())


def _pipeline_error(e: PipelineError):
    raise HTTPException(status_code=422, detail={"message": "The program has errors", "errors": e.errors})


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "caif-backend", "samples": len(SAMPLES)}


@app.get("/api/examples")
def examples():
    return SAMPLES


@app.post("/api/parse", response_model=ParseResponse)
def parse(req: SourceRequest):
    r = parse_program(req.source, req.config.default_size)
    return {
        "ok": r.ok,
        "instructions": [dict(i.to_dict(), position=k) for k, i in enumerate(r.instructions)],
        "errors": [e.__dict__ for e in r.errors],
        "blocks": r.blocks,
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_ep(req: SourceRequest):
    try:
        a = analyze(req.source, _cfg(req.config))
    except PipelineError as e:
        _pipeline_error(e)
    for k in ("_seq", "_graph", "_cands"):
        a.pop(k, None)
    return a


@app.post("/api/optimize", response_model=OptimizeResponse)
def optimize_ep(req: SourceRequest):
    try:
        return run_caif(req.source, _cfg(req.config))
    except PipelineError as e:
        _pipeline_error(e)


@app.post("/api/validate", response_model=ValidationModel)
def validate_ep(req: ValidateRequest):
    r = parse_program(req.source, req.config.default_size)
    if not r.ok:
        _pipeline_error(PipelineError([e.__dict__ for e in r.errors]))
    by_id = {i.id: i for i in r.instructions}
    unknown = [x for x in req.order if x not in by_id]
    if unknown:
        raise HTTPException(status_code=422, detail={"message": f"Unknown instruction IDs: {unknown}", "errors": []})
    return validate(r.instructions, [by_id[x] for x in req.order]).to_dict()


@app.post("/api/experiments/run")
def experiments_run(req: ExperimentRequest):
    allowed = set(FusionConfig().to_dict())
    bad = set(req.overrides) - allowed
    if bad:
        raise HTTPException(status_code=422, detail={"message": f"Unknown config keys: {sorted(bad)}", "errors": []})
    errs = FusionConfig(**req.overrides).validate()
    if errs:
        raise HTTPException(status_code=422, detail={"message": "; ".join(errs), "errors": []})
    return run_suite(req.overrides, req.label, req.sweep)


@app.get("/api/experiments/results")
def experiments_results():
    return list_runs()


@app.get("/api/experiments/{run_id}")
def experiment_get(run_id: str):
    run = load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"message": f"Experiment '{run_id}' not found", "errors": []})
    return run


@app.get("/api/report/{run_id}")
def report(run_id: str):
    run = load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"message": f"Experiment '{run_id}' not found", "errors": []})
    return {"id": run_id, "markdown": render_markdown(run)}


@app.get("/api/configs")
def configs():
    return load_configs()


@app.post("/api/configs")
def configs_save(req: SaveConfigRequest):
    return save_config(req.name, req.config.model_dump())
