# System architecture

```
          ┌──────────────────────────── frontend (React + TS, Vite :5173) ───────────────────────────┐
          │ Overview │ Input │ Fusion Analysis │ Dependency Graph │ Optimization │ Results │ About    │
          │            AppState (source, config, last result)  ──  services/api.ts (fetch /api/*)   │
          └───────────────────────────────────────────────┬──────────────────────────────────────────┘
                                                          │ JSON over HTTP (Vite proxies /api)
          ┌───────────────────────────── backend (FastAPI :8000, main.py) ───────────────────────────┐
          │  api_schemas.py (Pydantic)        experiments/ (runner, JSON/CSV storage in data/)       │
          │                                                                                          │
          │  core/pipeline.py  ─ wires the stages, no compiler logic of its own                      │
          │     │                                                                                    │
          │     ├─ Stage 2  parser.py            text → Instruction objects (+ errors, basic blocks) │
          │     ├─          dataflow.py          reaching definitions, use-def chains                │
          │     ├─          alias_analyzer.py    abstract addresses, NO/MUST/PARTIAL/MAY alias       │
          │     ├─ Stage 3  fusion_detector.py   pair compatibility, consecutive opportunities       │
          │     ├─ Stage 4  dependency_analyzer  RAW / ADDRESS / WAR / WAW / MEMORY graph            │
          │     ├─ Stage 5  catalyst_analyzer    catalyst, chain, blocking edges, proposed order     │
          │     ├─ Stage 6  optimizer.py         pair selection + safe moves (fixed point)           │
          │     ├─ Stage 7  validator.py         static re-check + differential execution (interp.)   │
          │     └─ Stage 8  metrics.py           before/after counts, percentages, timings           │
          └──────────────────────────────────────────────────────────────────────────────────────────┘
```

## Data flow for `POST /api/optimize`

1. `parse_program` returns `Instruction` objects or a list of errors. Errors produce HTTP 422
   with line numbers.
2. `AddressAnalysis` resolves every memory operand, and `build_dependency_graph` builds
   the edges.
3. `find_candidate_pairs` evaluates every same-kind pair in a block and lists each condition.
4. `analyze_catalyst` runs for every compatible, non-consecutive pair (for display).
5. `optimize` runs the driver. Each attempt recomputes the analyses on the *current*
   sequence and records a `Step`.
6. `validate(original, optimized)` re-derives everything from the original program.
7. `consecutive_opportunities` runs on the original and on the final sequence, and
   `compute_metrics` summarises.

## Module boundaries (why they are separate)

* `instruction.py` holds data only. New opcodes are registered in `OPCODES`.
* `parser.py` knows syntax, not semantics.
* `alias_analyzer.py` and `dependency_analyzer.py` know semantics but never move code.
* `optimizer.py` moves code but trusts nothing it has not checked.
* `validator.py` imports only the alias analysis and the instruction model. It does not use
  the optimizer's dependence graph, so a bug there cannot hide itself.

## Storage

* `data/experiments/exp-YYYYMMDD-HHMMSS-xxxx.{json,csv}`: one file pair per experiment run.
* `data/configs.json`: named, saved fusion configurations.
* `documentation/results.md`: written by `python -m experiments.experiment_runner`.

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/examples` | the 13 sample programs with their specifications |
| POST | `/api/parse` | parse only. Always 200, with an `errors` list |
| POST | `/api/analyze` | stages 2–5 on the original program |
| POST | `/api/optimize` | full pipeline |
| POST | `/api/validate` | validate a user-supplied order (`order: [ids]`) |
| POST | `/api/experiments/run` | run the experiment suite (optional `overrides`) |
| GET | `/api/experiments/results` | history |
| GET | `/api/experiments/{id}` | one run |
| GET | `/api/report/{id}` | Markdown report for one run |
| GET/POST | `/api/configs` | saved configurations |

Interactive API documentation is served at `http://127.0.0.1:8000/docs`.
