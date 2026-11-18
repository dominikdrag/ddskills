#!/bin/bash
# Wait for a bg.sh job. Usage: wait.sh <prefix>[.exit] [seconds, default 100]
#   DONE exit=<code>  the job ended; prints the log tail; returns 0
#   RUNNING           still running after <seconds>; returns 3; call again
#   DIED              the job is gone without an exit code (killed); returns 4; read the log and start it again
set -uo pipefail
prefix=${1%.exit}; secs=${2:-100}
waited=0
while :; do
  if [ -f "$prefix.exit" ]; then
    echo "DONE exit=$(cat "$prefix.exit") log=$prefix.log"
    tail -n 25 "$prefix.log" 2>/dev/null
    exit 0
  fi
  # alive while any process of the job's group remains (the group id is the recorded pid)
  if [ ! -s "$prefix.pid" ] || ! kill -0 -"$(cat "$prefix.pid")" 2>/dev/null; then
    sleep 1
    [ -f "$prefix.exit" ] && continue
    echo "DIED: no exit code and no live process. log=$prefix.log"
    tail -n 25 "$prefix.log" 2>/dev/null
    exit 4
  fi
  [ "$waited" -ge "$secs" ] && break
  sleep 5; waited=$((waited + 5))
done
echo "RUNNING after ${secs}s, call wait.sh again. log=$prefix.log"
tail -n 3 "$prefix.log" 2>/dev/null
exit 3
