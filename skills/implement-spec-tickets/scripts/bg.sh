#!/bin/bash
# Run a command in its own session, detached from the caller, so it survives the caller's timeout or kill.
# Usage: bg.sh <prefix> -- <command> [args...]
# Writes <prefix>.pid (the job's process group), <prefix>.log (stdout and stderr) and, when the command ends, <prefix>.exit.
# Refuses to start while an earlier job with the same prefix is alive: poll that one with wait.sh instead.
set -euo pipefail
[ $# -ge 3 ] || { echo "usage: bg.sh <prefix> -- <command> [args...]" >&2; exit 2; }
prefix=$1; shift
[ "$1" = "--" ] && shift
mkdir -p "$(dirname "$prefix")"
alive() { [ -s "$prefix.pid" ] && kill -0 -"$(cat "$prefix.pid")" 2>/dev/null; }
# An atomic claim stops two overlapping launches on one prefix.
if ! mkdir "$prefix.claim" 2>/dev/null; then
  fresh_claim=$(python3 -c 'import os,sys,time; print(int(time.time()-os.path.getmtime(sys.argv[1])<30))' "$prefix.claim" 2>/dev/null || echo 0)
  if alive || [ "$fresh_claim" = 1 ]; then
    echo "STILL RUNNING: poll it with wait.sh $prefix" >&2; exit 5
  fi
  rmdir "$prefix.claim" 2>/dev/null || { echo "unexpected content in $prefix.claim; left as is" >&2; exit 5; }
  mkdir "$prefix.claim" || { echo "could not claim $prefix" >&2; exit 5; }
fi
if alive && [ ! -f "$prefix.exit" ]; then rmdir "$prefix.claim"; echo "STILL RUNNING: poll it with wait.sh $prefix" >&2; exit 5; fi
rm -f "$prefix.exit" "$prefix.exit.tmp" "$prefix.pid"
# python3 setsid gives the job its own session and process group; the inner bash records its pid (= the group id) and exit code.
nohup python3 -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
  /bin/bash -c 'echo $$ >"$0.pid"; rmdir "$0.claim" 2>/dev/null; "$@" >"$0.log" 2>&1; echo $? >"$0.exit.tmp"; mv "$0.exit.tmp" "$0.exit"' "$prefix" "$@" \
  </dev/null >/dev/null 2>&1 &
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$prefix.pid" ] && break; sleep 0.2; done
echo "started pid $(cat "$prefix.pid" 2>/dev/null || echo '?') log=$prefix.log"
