#!/usr/bin/env bash
# Helper to run uvicorn in background safe from TTY suspension
# Usage: ./run_uvicorn.sh [--reload]

RELOAD_FLAG=""
if [ "$1" = "--reload" ]; then
  RELOAD_FLAG="--reload"
fi

LOGFILE="$(dirname "$0")/uvicorn.log"
# Run with nohup, redirect stdout+stderr to logfile and disown so it won't be suspended by TTY output
nohup micromamba run -n manim uvicorn app.main:app --host 0.0.0.0 --port 8000 $RELOAD_FLAG > "$LOGFILE" 2>&1 &
PID=$!
# Disown and show PID
disown
echo "Started uvicorn (pid=$PID), logs: $LOGFILE"