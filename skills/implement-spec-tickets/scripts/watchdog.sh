#!/bin/bash
# Stall watchdog for the main loop, run as a tracked background task.
# Usage: watchdog.sh <minutes> <dir> [dir...]
# Exits with "STALLED" once no file under the given folders changed for <minutes> minutes.
set -uo pipefail
minutes=$1; shift
[ $# -ge 1 ] || { echo "usage: watchdog.sh <minutes> <dir> [dir...]" >&2; exit 2; }
marker=$(mktemp "${TMPDIR:-/tmp}/watchdog.XXXXXX")
trap 'rm -f "$marker"' EXIT
idle=0
while true; do
  sleep 60
  if [ -n "$(find "$@" -type f -newer "$marker" -not -path '*/.git/*' -print -quit 2>/dev/null)" ]; then
    touch "$marker"; idle=0
  else
    idle=$((idle + 1))
  fi
  if [ "$idle" -ge "$minutes" ]; then
    echo "STALLED: nothing under $* changed for $minutes minutes"
    exit 0
  fi
done
