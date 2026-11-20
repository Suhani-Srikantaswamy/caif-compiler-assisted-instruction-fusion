#!/bin/sh
# Start the CAIF backend (:8000) and frontend (:5173) as detached background
# processes that keep running after the terminal (or editor session) closes.
# Logs: logs/backend.log, logs/frontend.log     Stop with: ./stop.sh
cd "$(dirname "$0")"
mkdir -p logs
if lsof -ti tcp:8000 >/dev/null 2>&1; then echo "backend already running on :8000"
else
  (cd backend && nohup .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 > ../logs/backend.log 2>&1 &)
  echo "backend started  -> http://127.0.0.1:8000  (log: logs/backend.log)"
fi
if lsof -ti tcp:5173 >/dev/null 2>&1; then echo "frontend already running on :5173"
else
  (cd frontend && nohup npx vite --port 5173 --strictPort > ../logs/frontend.log 2>&1 &)
  echo "frontend started -> http://localhost:5173 (log: logs/frontend.log)"
fi
