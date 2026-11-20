#!/bin/sh
# Stop the CAIF servers started by run_detached.sh (or anything on ports 8000/5173).
for port in 8000 5173; do
  pids=$(lsof -ti tcp:$port 2>/dev/null)
  if [ -n "$pids" ]; then kill $pids && echo "stopped :$port"; else echo ":$port not running"; fi
done
