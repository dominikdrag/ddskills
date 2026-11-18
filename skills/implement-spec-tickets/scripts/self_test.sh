#!/bin/bash
# Offline checks for this skill's helpers. Needs bash, git, node and python3; makes no reviewer calls.
# Usage: scripts/self_test.sh
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/implement-spec-tickets-test.XXXXXX")
trap 'rm -rf "$work"' EXIT
fail() { echo "FAIL $*"; exit 1; }

for s in "$here"/*.sh; do bash -n "$s" || fail "shell syntax: $s"; done
echo "PASS shell syntax"

python3 -c 'import json,sys; [json.load(open(p)) for p in sys.argv[1:]]' "$here"/schemas/*.json || fail "schema JSON"
echo "PASS schemas parse"

# The Workflow runtime runs the script body inside an async function; check it the same way.
{ echo "const agent=async()=>({}),parallel=async(t)=>Promise.all(t.map(f=>f())),phase=()=>{},log=()=>{},args={};"
  echo "async function __body(){"; sed 's/^export const meta/const meta/' "$here/ticket-workflow.js"; echo "}"; } > "$work/wf.mjs"
node --check "$work/wf.mjs" || fail "ticket-workflow.js syntax"
{ echo "const agent=async()=>({}),parallel=async(t)=>Promise.all(t.map(f=>f())),phase=()=>{},log=()=>{},args={};"
  echo "async function __body(){"; sed 's/^export const meta/const meta/' "$here/closing-workflow.js"; echo "}"; } > "$work/cl.mjs"
node --check "$work/cl.mjs" || fail "closing-workflow.js syntax"
echo "PASS workflow script syntax"

node "$here/workflow_logic_test.mjs" >"$work/logic.log" 2>&1 || { cat "$work/logic.log"; fail "workflow control flow"; }
echo "PASS workflow control flow ($(grep -c ^PASS "$work/logic.log") cases)"

"$here/bg.sh" "$work/job" -- /bin/sh -c 'echo hello; exit 7' >/dev/null
"$here/wait.sh" "$work/job" 30 | grep -q 'DONE exit=7' || fail "bg.sh/wait.sh exit code"
grep -q hello "$work/job.log" || fail "bg.sh log"
"$here/bg.sh" "$work/slow" -- sleep 30 >/dev/null
"$here/bg.sh" "$work/slow" -- sleep 30 >/dev/null 2>&1 && fail "bg.sh started a second job on a live prefix"
rc=0; "$here/wait.sh" "$work/slow" 5 >/dev/null || rc=$?; [ $rc -eq 3 ] || fail "wait.sh RUNNING code ($rc)"
kill -9 -"$(cat "$work/slow.pid")"; sleep 1
rc=0; "$here/wait.sh" "$work/slow" 5 >/dev/null || rc=$?; [ $rc -eq 4 ] || fail "wait.sh DIED code ($rc)"
echo "PASS bg.sh and wait.sh (exit code, live-prefix guard, RUNNING, DIED)"

repo="$work/repo"; mkdir -p "$repo"; cd "$repo"
git init -q . && echo a > a.txt && git add a.txt && git -c user.name=t -c user.email=t@example.invalid commit -q --no-verify -m "chore: fixture"
t1=$("$here/snapshot.sh"); echo b > b.txt; t2=$("$here/snapshot.sh")
[ "$(git diff --name-only "$t1" "$t2")" = "b.txt" ] || fail "snapshot.sh misses untracked files"
[ -z "$(git diff --cached --name-only)" ] || fail "snapshot.sh touched the index"
echo "PASS snapshot.sh"
echo "all offline checks passed; run 'reviewer.sh smoke <empty-dir>' to check the reviewer model"
