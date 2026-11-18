---
name: implement-spec-tickets
description: >-
  Implement an approved spec's dependency-ordered tickets in Claude Code: one Workflow per ticket (implement, verify, up to three
  cross-model review rounds negotiated by a Claude agent, gate), commits and tracker updates by the main session, progress notes and
  resumable run state. Use when a spec with several tickets is ready to build, or to resume such a run.
---

# Implement Spec Tickets

Drive a ticket set from its first unblocked ticket to a hand-back, one ticket at a time. You are the **main loop**: the only writer of git
history and the issue tracker, and the only one who talks to the user. Every ticket runs as one Workflow of `scripts/ticket-workflow.js`
with arguments you compute from the run state, so the run is **dynamic**: each launch reflects what the previous ticket left behind. Load
the `workflow-authoring` skill before the first launch. [references/lessons.md](references/lessons.md) gives the evidence behind each rule.

## Run state

`RUN` is a folder that survives reboots and compaction: a gitignored folder inside the worktree (for example
`<worktree>/claude-tmp/<run-name>`), never a session scratchpad. Its layout, `state.json` and `ticket.md` are in
[references/run-files.md](references/run-files.md). `state.json` is the **source of truth**:

- Before any status claim, and after any compaction or restart, re-read it with `decisions.md`, `for-user.md` and the tracker's human-only
  tickets.
- After a restart, reconcile it with git: a ticket marked running whose commit (the line that closes it) is already on the branch is
  committed. Finish its tracker and state updates rather than launching it again.

## 1. Pin the run

Work in a dedicated worktree whose `git status` is clean apart from `RUN`. Every diff, review and commit then holds only ticket work. Files
the tickets need from elsewhere (uncommitted boards, say) are read by absolute path or committed first with the user's approval.

Read the spec and every ticket with its blocker relations, the repository's agent, testing and review-budget rules, and the documents the
spec names. Write:

- `RUN/project.md`: the exact commands for generation, focused tests, the full suite, the build-cache path, format and lint, and how to make
  a screenshot montage, plus the architecture rules agents follow. When the project has them, add snapshot record/compare, string and
  localization checks, and the simulator claim. Agents read this file, not the repository's rule files.
- `RUN/decisions.md`: settled answers, the stop-and-ask list (areas where agents return a question instead of choosing), the review settings
  (round limit, auto-fix scope) and any explicit user override of the repository's review budget.
- `RUN/reviewer.env`: `REVIEW_MODEL`, `REVIEW_EFFORT` and `REVIEW_CWD` (the worktree).
- `RUN/state.json`: ticket order, human-only tickets, and per ticket:
  - effort: `medium` for a clear, contained ticket; `high` for schema, persistence, concurrency, notifications, privacy or cross-module work;
  - the `ui`, `copyCheck` and `fullSnapshots` flags.

Done when every ticket has an order slot, an effort and its flags, and every open question is listed.

## 2. Ask once, up front

Put every open question to the user in one bundle: up to four per `AskUserQuestion` call, your recommendation first, each answerable without
the transcript. Cover:

- the reviewer model and effort, unless the user already named them;
- whatever the tickets leave open;
- files the tickets depend on that live outside the worktree;
- the auto-fix scope;
- when tracker tickets count as done;
- how to handle drift on the target branch.

Write the answers to `decisions.md`. Questions that arise mid-run follow the same rule: ask in this session, never through another session.

## 3. Set up

1. Copy the skill's `scripts/` to `RUN/bin/` and `references/review-negotiation.md` to `RUN/`.
2. Bootstrap the build tooling. When the project tests on a simulator, claim one for the whole run: one label, re-claimed before each ticket,
   keeping any extra services a ticket needs (such as Health).
3. Run a **baseline**: the full suite, plus a snapshot compare when the project has snapshots. Record executed-test counts and durations in
   `state.json`. If a full snapshot compare takes over ten minutes, set `fullSnapshots` on every few tickets and on the closing run, and
   gate the rest on a filtered compare.
4. Keep the computer awake for the run: the host's keep-awake tool, or `caffeinate -i` as a tracked background task.
5. Start `RUN/bin/watchdog.sh 25 RUN <source folders>` as a tracked background task. It exits when nothing changed for 25 minutes; when it
   fires, find the stalled stage, then re-arm it.
6. Smoke tests:
   - `RUN/bin/reviewer.sh smoke <empty folder outside the worktree>` must print three PASS lines (schema output, thread memory, read-only in
     force). Every review depends on them.
   - A one-agent Workflow dry run whose agent reports its model id must show the model you pass.
7. Comment on the spec issue that the run started, with the branch and base commit.

Done when the baseline counts are in `state.json` and both smoke tests passed.

## 4. Run each ticket

Take the next ticket whose blockers are done in `state.json`: committed (even when the tracker's done step waits for a merge), or, for a
human-only blocker, recorded as completed once the user confirms it. Human-only tickets themselves wait for the user.

1. Write `RUN/<ticket>/ticket.md`, set the ticket In Progress, and record `base` (current `HEAD`) in `state.json`.
2. Re-arm the watchdog, re-claim the simulator if the run claimed one, and launch `Workflow({scriptPath: 'RUN/bin/ticket-workflow.js', args})`. The script's header
   documents `args`.
3. Read the compact result and act on its `status`. The evidence for notes and comments always comes from the stage files in
   `RUN/<ticket>/`, never only from the compact result: montage and device-only list from `verify.json` (or `verify-fix.json`), rounds from
   `rounds/`, gate evidence from `gate.json`, `gate-fix.json` and `gate-2.json`, questions from every stage file. A `copyCheck` ticket with
   no `copy.json` gets "copy check did not run" in its progress note.

| status | You do |
| --- | --- |
| `ready` | Commit, update the tracker and `state.json`, append the result's non-blocking questions, `open_p3` and `unreviewed_fixes` to `for-user.md`, send the progress note, continue. |
| `blocked` | Ask the user now, recommendation first; write the answer to `decisions.md`; relaunch with `resume` set to the returned value. |
| `needs-user` | The review limit was reached. Show every `open` item and every `unreviewed_fixes` entry (review fixes by id; gate fixes as `G1`, `G2` from `gate-fix.json`, with `production_changes`), each with both positions and your recommendation. Write each answer to `decisions.md` under `## <ticket> review answers`, by id. Relaunch with the returned `resume`. |
| `failed` | Checks still fail after one fix. Diagnose from the logs in `RUN/<ticket>/logs/`. Write the diagnosis to `decisions.md` under the ticket, then relaunch with the returned `resume`. Ask the user only when the fix needs a product decision, or after a second `failed` at the same stage. When a ticket deliberately removes tests, lower the baseline in `state.json` with a note in `decisions.md`. |
| `infra` or `budget` | Relaunch with the returned `resume`. After two `infra` results in a row, find the cause first. |

The returned `resume` carries the stage, the round and `roundsDone`; pass it back unchanged. Relaunch as a fresh Workflow. Use `resumeFromRunId` only to finish a launch that died with the tree unchanged. A paused
ticket holds the chain, because later tickets build on it in the same checkout; a ticket with no changes yet may be skipped and taken up
later.

**Commit**, once per ticket, after the gate:

1. `git diff --cached` is empty.
2. Stage the ticket's paths: `git diff --name-only <base>` plus `git ls-files --others --exclude-standard`. Read the list first: everything
   on it must belong to this ticket.
3. `git diff --cached --stat`, and record the staged tree: `git write-tree`.
4. `git commit -F RUN/<ticket>/commit-msg.txt` in the repository's message format, with a body saying why and what, and the line that
   closes the ticket.
5. Compare `HEAD^{tree}` with the recorded tree, and look for hook rewrites left in the worktree. A formatting-only difference is fine
   (re-stage and commit again if the hook rejected the commit). Anything else: re-run the affected checks before recording the ticket.
6. Set the baseline test count in `state.json` to this ticket's gate count.

Push and merge only on the user's word.

**Tracker comment**: the sha, checks with counts and log paths, and the review summary (rounds; accepted, rejected and open findings with both
positions), plus deviations and questions. Tick the acceptance boxes. Mark the ticket done when `decisions.md` says so.

**Progress note** to the user:

- the ticket, sha and test counts;
- review rounds and the findings settled;
- open P3 items and last-round fixes no reviewer saw;
- non-blocking questions from `for-user.md`;
- for UI tickets, the montage file, sent proactively.

## 5. Hand back

1. With every implementation ticket committed (human-only tickets recorded as done or still waiting) and the worktree clean, launch `RUN/bin/closing-workflow.js` with the target branch, the tip sha and
   `sweep: true` when any ticket changed screens. It runs:
   - the full gate on the tip;
   - the screen sweep (second language, large accessibility text size, 12-hour clock) when asked;
   - a report-only review of the whole branch for defects that cross tickets.

   `mismatch` means the tree moved under the checks: find out why, then run it again. When the run stops with a ticket paused (uncommitted
   edits or an unanswered question), skip the closing workflow and list the checks still pending in the hand-back.
2. Re-read the run files and the target branch, and confirm `HEAD` is still the tip the closing checks covered.
3. Write the hand-back:
   - a per-ticket table: sha, tests, rounds, accepted/rejected/open;
   - open disagreements and the decisions you made;
   - the closing results and device-only checks;
   - commits on the branch and drift on the target;
   - one merge question.
4. Release the run's resources, whether the run finished or stopped paused:
   - release the simulator claim, if any;
   - stop the keep-awake task and the watchdog;
   - comment on the spec issue that the run ended.

Done when every ticket that isn't human-only is committed, or paused with a question the user has seen.

## Review rules

Every ticket gets a cross-model review: the reviewer runs through the Codex CLI with the settings in `reviewer.env`, always read-only and
with a time limit. A Claude negotiator judges each finding against the code, accepts, rejects or partly accepts it, replies in the same
reviewer thread until they agree, and applies the agreed fixes. Each later round reviews everything changed since the reviewer last looked.

The limit is three rounds. After the last one:

- open P0 to P2 items, user decisions and unreviewed P0/P1 fixes pause the ticket for the user;
- open P3 items and unreviewed P2/P3 fixes reach the user in the progress note without pausing.

A gate fix that changes production code gets one more review round while rounds remain, and goes to the user otherwise. The negotiator's
protocol is [references/review-negotiation.md](references/review-negotiation.md); the workflow script enforces the limits.
