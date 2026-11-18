#!/bin/bash
# Cross-model reviewer through the Codex CLI, always read-only, with a time limit.
# Settings: the environment wins, then <RUN>/reviewer.env (written by the main loop), then defaults:
#   REVIEW_MODEL        reviewer model id (required)
#   REVIEW_EFFORT       reasoning effort (default high)
#   REVIEW_CWD          folder the reviewer reads, the worktree (default: current folder)
#   REVIEW_TIMEOUT_MIN  minutes before a call is killed (default 30)
# Usage:
#   reviewer.sh new       <dir> <round>  prompt <dir>/r<round>.prompt.md        -> <dir>/r<round>.json        new thread (<dir>/thread_id)
#   reviewer.sh next      <dir> <round>  prompt <dir>/r<round>.prompt.md        -> <dir>/r<round>.json        same thread
#   reviewer.sh reply     <dir> <round>  prompt <dir>/r<round>-reply.prompt.md  -> <dir>/r<round>-reply.json  same thread
#   reviewer.sh new-reply <dir> <round>  prompt <dir>/r<round>-reply.prompt.md  -> <dir>/r<round>-reply.json  new thread (fallback)
#   reviewer.sh smoke     <empty-dir>    proves schema output, thread memory and a refused write
# Exit codes: 0 ok, 2 usage, 4 no valid JSON, 124 timed out, other: codex's own.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
self="$here/$(basename "$0")"
for v in REVIEW_MODEL REVIEW_EFFORT REVIEW_CWD REVIEW_TIMEOUT_MIN; do eval "saved_$v=\${$v-__unset__}"; done
[ -f "$here/../reviewer.env" ] && . "$here/../reviewer.env"
for v in REVIEW_MODEL REVIEW_EFFORT REVIEW_CWD REVIEW_TIMEOUT_MIN; do
  eval "s=\$saved_$v"; [ "$s" != "__unset__" ] && eval "$v=\$s"
done
: "${REVIEW_MODEL:?set REVIEW_MODEL in <RUN>/reviewer.env or the environment}"
effort=${REVIEW_EFFORT:-high}
limit=$(( ${REVIEW_TIMEOUT_MIN:-30} * 60 ))
schemas="$here/schemas"

valid_json() { python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$1" 2>/dev/null; }

thread_of() {
  python3 - "$1" <<'PY'
import json, sys
for line in open(sys.argv[1], errors="replace"):
    try:
        e = json.loads(line)
    except Exception:
        continue
    if e.get("type") == "thread.started" and e.get("thread_id"):
        print(e["thread_id"]); break
PY
}

# perl alarm kills codex after $limit seconds (macOS has no timeout command); exit 142 becomes 124.
timed() { set +e; perl -e 'alarm shift; exec @ARGV' "$limit" "$@"; local rc=$?; set -e; [ $rc -eq 142 ] && return 124; return $rc; }

start() { # <prompt> <schema> <out> <events> <cwd>
  timed codex exec -m "$REVIEW_MODEL" -c model_reasoning_effort="$effort" -s read-only --skip-git-repo-check \
    -C "$5" --json --output-schema "$2" -o "$3" - < "$1" > "$4"
}

resume() { # <thread> <prompt> <schema> <out> <events> <cwd>
  cd "$6" && timed codex exec resume "$1" -m "$REVIEW_MODEL" -c model_reasoning_effort="$effort" \
    -c sandbox_mode=read-only --skip-git-repo-check --json --output-schema "$3" -o "$4" - < "$2" > "$5"
}

mode=${1:-}
case "$mode" in
  new|next|reply|new-reply)
    [ $# -eq 3 ] || { sed -n '2,17p' "$0"; exit 2; }
    dir=$(cd "$2" && pwd); n=$3; cwd=${REVIEW_CWD:-$PWD}
    case "$mode" in
      reply|new-reply) stem="r$n-reply"; schema="$schemas/reply.json" ;;
      *) stem="r$n"; schema="$schemas/review.json" ;;
    esac
    prompt="$dir/$stem.prompt.md"; out="$dir/$stem.json"; events="$dir/$stem.events.jsonl"
    [ -s "$prompt" ] || { echo "missing prompt $prompt" >&2; exit 2; }
    rm -f "$out"
    rc=0
    if [ "$mode" = new ] || [ "$mode" = new-reply ]; then
      rm -f "$dir/thread_id"
      start "$prompt" "$schema" "$out" "$events" "$cwd" || rc=$?
      thread=$(thread_of "$events" || true)
      if [ -n "$thread" ]; then printf '%s\n' "$thread" > "$dir/thread_id.tmp" && mv "$dir/thread_id.tmp" "$dir/thread_id"; fi
    else
      [ -s "$dir/thread_id" ] || { echo "no thread_id in $dir; use new" >&2; exit 2; }
      resume "$(cat "$dir/thread_id")" "$prompt" "$schema" "$out" "$events" "$cwd" || rc=$?
    fi
    [ $rc -eq 124 ] && { echo "reviewer timed out after ${REVIEW_TIMEOUT_MIN:-30} min (events: $events)" >&2; exit 124; }
    [ $rc -eq 0 ] || { echo "codex exited $rc (events: $events)" >&2; exit $rc; }
    valid_json "$out" || { echo "reviewer returned no valid JSON in $out (events: $events)" >&2; exit 4; }
    [ -s "$dir/thread_id" ] || { echo "no thread id recorded (events: $events)" >&2; exit 4; }
    echo "ok $out thread=$(cat "$dir/thread_id")"
    ;;
  smoke)
    [ $# -eq 2 ] || { sed -n '2,17p' "$0"; exit 2; }
    if [ -e "$2" ] && [ -n "$(ls -A "$2" 2>/dev/null)" ]; then echo "smoke needs an empty or new folder: $2 is not empty" >&2; exit 2; fi
    mkdir -p "$2"; repo=$(cd "$2" && pwd)
    rv=$(mktemp -d "${TMPDIR:-/tmp}/reviewer-smoke.XXXXXX")     # prompts and outputs live outside the folder the reviewer reads
    cd "$repo"
    git init -q . && printf 'first line\n' > a.txt && git add a.txt
    git -c user.name=smoke -c user.email=smoke@example.invalid commit -q --no-verify -m "chore: smoke fixture"
    export REVIEW_CWD="$repo"
    printf 'Codeword: PELICAN. Remember it for later turns.\nReview this repository (git show HEAD). It is a smoke test: report no findings, empty responses.\n' > "$rv/r1.prompt.md"
    "$self" new "$rv" 1 >/dev/null || { echo "FAIL new review call (see $rv)"; exit 1; }
    echo "PASS new thread $(cat "$rv/thread_id") with schema output"
    printf 'Return one response with id "codeword", position "concede", argument set to the codeword from the first message, revised_fix "". No new findings.\n' > "$rv/r1-reply.prompt.md"
    "$self" reply "$rv" 1 >/dev/null || { echo "FAIL reply call (see $rv)"; exit 1; }
    grep -q PELICAN "$rv/r1-reply.json" && echo "PASS resume keeps the thread" || { echo "FAIL resume lost the thread: $(cat "$rv/r1-reply.json")"; exit 1; }
    printf 'Run exactly this shell command: printf hi > written.txt   Then report no findings and empty responses.\n' > "$rv/r2.prompt.md"
    "$self" next "$rv" 2 >/dev/null || { echo "FAIL write-probe call did not complete (see $rv)"; exit 1; }
    [ -e "$repo/written.txt" ] && { echo "FAIL the reviewer wrote a file: read-only is not enforced"; exit 1; }
    if python3 - "$rv/r2.events.jsonl" <<'PY'
import json, sys
# Proof: a write attempt that the sandbox refused, or the reviewer reporting a read-only sandbox.
evidence = False
for line in open(sys.argv[1], errors="replace"):
    try:
        e = json.loads(line)
    except Exception:
        continue
    item = e.get("item") or {}
    text = json.dumps(item).lower()
    if item.get("type") == "command_execution" and "written.txt" in text and (
            item.get("exit_code") not in (0, None) or item.get("status") in ("failed", "declined")):
        evidence = True
    if item.get("type") == "agent_message" and ("read-only" in text or "read only" in text):
        evidence = True
sys.exit(0 if evidence else 1)
PY
    then echo "PASS read-only sandbox in force (write refused or reported read-only)"
    else echo "FAIL inconclusive: no refused write and no read-only report in $rv/r2.events.jsonl"; exit 1
    fi
    ;;
  *) sed -n '2,17p' "$0"; exit 2 ;;
esac
