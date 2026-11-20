#!/bin/sh
# Start backend (:8000) and frontend (:5173). Ctrl+C stops both.
cd "$(dirname "$0")"
[ -d backend/.venv ] || (python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt)
[ -d frontend/node_modules ] || (cd frontend && npm install)
(cd backend && .venv/bin/uvicorn main:app --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT INT TERM
cd frontend && npm run dev
