# CAIF: Compiler-Assisted Instruction Fusion (educational implementation)

An implementation of the central idea of **"Compiler-Assisted Instruction Fusion"**
(Reddy, Singh, Perais, Ros, Jimborean, CGO 2026,
[PDF](https://webs.um.es/aros/papers/pdfs/rrreddy-cgo26.pdf)).

The compiler finds memory operations that simple hardware *could* fuse but that are not
adjacent. It proves with dependence and alias analysis that the second one (the TAIL) and
the instructions computing its address or value can be moved up, then rearranges the code
so the pair becomes **consecutive**. Every result is re-checked from the original program by a
validator (a static commutation check plus interpreter-based differential testing) before it is accepted.

> **Scope.** This project uses a *simulated teaching ISA* (not RISC-V), runs in Python
> rather than inside LLVM, and reports *potential* consecutive fusion opportunities. It does
> not measure hardware fusion or speedup. Numbers reported in the paper are shown separately
> and are labelled as such.

## Quick start (macOS)

Requirements: Python 3.11+ (tested with 3.14), Node.js 18+ (tested with 18.20), npm.

```bash
git clone https://github.com/Suhani-Srikantaswamy/caif-compiler-assisted-instruction-fusion.git
cd caif-compiler-assisted-instruction-fusion

# 1. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --port 8000          # leave running  (API docs: http://127.0.0.1:8000/docs)

# 2. Frontend (new terminal)
cd ../frontend
npm install
npm run dev                                     # open http://localhost:5173
```

Or start both at once:

* `./start.sh`: runs both in the current terminal. Ctrl+C stops them.
* `./run_detached.sh`: runs both in the background, so they keep running after the
  terminal closes. Logs go to `logs/backend.log` and `logs/frontend.log`. Stop them with
  `./stop.sh`.

If the app shows *"Cannot reach the backend"*, the backend isn't running. Start it again
with one of the commands above.

### Tests

```bash
cd backend  && .venv/bin/python -m pytest       # backend tests
cd ../frontend && npm test                      # frontend tests
npm run typecheck                               # TypeScript
npm run build                                   # production build
```

### Experiments

```bash
cd backend && .venv/bin/python -m experiments.experiment_runner
```

This runs all 13 sample programs, writes `data/experiments/<id>.json` and `.csv`, and
regenerates `documentation/results.md`. The same runner is available from the **Results**
page.

### Optional LLVM demo

```bash
./llvm_demo/run_demo.sh      # uses Apple clang: LLVM IR + AArch64 clustering / ldp pairing
```

## Using the app

1. **Instruction Input**: pick a sample, or type a program, then **Parse** or **Run CAIF optimization**.
2. **Fusion Analysis**: every candidate pair, each compatibility condition, the catalyst
   table, and why a move was accepted or rejected.
3. **Dependency Graph**: an interactive graph of RAW / ADDRESS / WAR / WAW / MEMORY edges.
   Select a pair to colour its HEAD, TAIL, catalyst, required chain and blocking edges.
4. **Optimization**: original and optimized sequences side by side, the validator report,
   and a step-by-step replay.
5. **Results & Experiments**: metrics for the current program, the experiment suite with
   charts and downloads, and the paper's reported results in a separate section.

## Repository layout

```
backend/
  main.py, api_schemas.py        FastAPI + Pydantic (HTTP layer only)
  core/                          compiler logic: instruction, parser, dataflow, alias_analyzer,
                                 dependency_analyzer, fusion_detector, catalyst_analyzer,
                                 optimizer, validator, metrics, config, pipeline
  examples/sample_programs.py    13 workloads with written specifications
  experiments/                   runner + JSON/CSV storage
  tests/                         pytest suites
frontend/src/                    pages/, components/, graphs/, charts/, services/, state/, types/, lib/, data/
data/experiments/                saved experiment runs
documentation/                   project_report.md (A–J), architecture, algorithm, implementation, limitations, results
llvm_demo/                       small real-LLVM exploration
```

Start with [documentation/project_report.md](documentation/project_report.md). The technical audit
(bugs found, fixes, what was verified) is in [documentation/audit_report.md](documentation/audit_report.md).
