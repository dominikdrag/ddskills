---
name: coordinate-multi-ticket-run
description: >-
  Coordinate approved local ticket graphs end to end. Use when implementation starts from an existing specification with multiple dependency-ordered
  tickets and needs delegated delivery, evidence-gated acceptance, or interrupted-run recovery.
---

# Coordinate Multi-Ticket Run

Walk an approved graph from its current **frontier** to truthful closure. Use four anchors throughout the run:

- **frontier**: the next executable ticket;
- **ledger**: assignment ownership and dependencies;
- **gate**: evidence required for closure;
- **reconcile**: compare normalized state with repository truth.

The invoking thread is the run coordinator. The bundled workflow engine owns deterministic routing; agents retain semantic judgment, permissions,
collaboration calls, and user communication.

## Step 1: Establish the run

1. Resolve the Git root and inspect the current worktree.
2. Read `AGENTS.md`, its routed rules, domain glossary, ticket schema, testing and QA contracts, and definition of done. Repository guidance takes priority.
3. Identify the approved specification and complete ticket graph. A missing product decision or unstable blocker/criterion is the stopping condition.
4. Resolve the evidence location from explicit guidance or repository convention. Otherwise use a task-scoped location outside the worktree or verify that
   the repository ignores it.
5. Record separate authority for commits, ticket/worklog/notes changes, worktrees, and external actions.
6. Use `$maintain-implementation-notes` before the first implementation edit.
7. Read [the workflow state contract](references/workflow-state.md). Create `<evidence>/run.json` as a projection of the actual tickets, repository
   statuses, assignments, and evidence. Source artifacts remain authoritative; the state file owns orchestration.
8. Resolve this skill's directory and run `python3 <skill-dir>/scripts/workflow.py validate --state <evidence>/run.json`.

**Complete when:** the approved graph is fully projected and validation exits `0`, or the unresolved product decision is recorded for the user.

## Step 2: Route the frontier

Run `workflow.py next` and execute exactly the returned action:

- `spawn_ticket_coordinator`: follow Step 3 for the named ticket.
- `wait_ticket_coordinator`: remain available to the user and wait or forward relevant direction.
- `spawn_acceptance_checker`: follow Step 4 for the named ticket.
- `return_acceptance_gaps`: send the named gaps to the live coordinator and use the allowed follow-up phase.
- `reject_closure`: repair the reported evidence or state gaps while the ticket remains open.
- `close_ticket`: follow the closure gate in Step 4.
- `respawn_ticket_coordinator`: read [the recovery contract](references/recovery.md) and resume from the recovered frontier.
- `run_blocked`: record blockers in implementation notes; ask one concise question when user input can advance the run.
- `run_complete`: audit the specification's full definition of done and report completion.
- `invalid_state`: reconcile the projection with source artifacts before further delegation or closure.

The **spawn gate** is: add the complete assignment to the ledger, or replace its interrupted predecessor during recovery; run `workflow.py validate`;
then spawn only after validation exits `0`. Apply it before every collaboration call that creates an agent.

Every spawn in this workflow must pass `fork_turns: "none"` explicitly. This applies to ticket coordinators, scouts, workers, reviewers, QA workers,
recovery coordinators, acceptance checkers, and final auditors. Do not omit the parameter: the collaboration tool's default can inherit the full parent
conversation. Override `"none"` only when the user explicitly requests inherited conversation history or the binding run contract requires it, and
record the reason in the ledger before spawning.

Because agents start with fresh task context, make each assignment self-contained. Include the objective; canonical specification, ticket, notes,
state, workflow, evidence, and repository paths; frontier and dependency state; current commits and verification state; owned and protected paths or
seams; allowed edits, commits, device or external actions; lane requirements; safety boundaries; named recipients; and the required report shape.
Fresh agents still receive platform and repository scaffolding, but do not assume they know any task-specific decision from the parent conversation.
After each action, validate `run.json` again.

**Complete when:** the returned action has been executed and structural validation exits `0`; `run_complete` and `run_blocked` are terminal routing outcomes.

## Step 3: Dispatch one ticket

Keep exactly one fresh ticket coordinator active. Read the configured capacity and reserve one slot for the invoking agent and one for the coordinator;
use remaining slots only for independent, ownership-safe leaves. Serialize repository, Apple-tooling, and device ownership where required.

Before spawning:

1. Pass the spawn gate with the coordinator's canonical target, role, deliverable, owned paths or seams, dependencies, recipient, and status.
2. Transition the named ticket to `coordinating`, confirm the event, and validate the resulting state.
3. Read [the role policy](references/role-policy.md) and [ticket coordinator contract](references/ticket-coordinator.md), then spawn with
   `fork_turns: "none"`, every placeholder resolved, and every authority boundary stated explicitly.

The run coordinator owns `run.json` between tickets; the active ticket coordinator owns assignment and evidence updates during its ticket. When useful,
the ticket coordinator reads [leaf agent contracts](references/leaf-agents.md) and delegates only validated, non-overlapping assignments. For Apple build,
test, Simulator, Device Hub, Playbook snapshot, or runtime QA work, use `$run-apple-verification-loop` and release the lane on every outcome.

**Complete when:** the ticket reaches `acceptance`, an interruption is persisted with `workflow.py interrupt`, or an explicit blocker is recorded in both
source artifacts and `run.json`.

## Step 4: Pass the closure gate

For `spawn_acceptance_checker`, read [the acceptance checker contract](references/acceptance-checker.md), pass the spawn gate with its active assignment,
and spawn a fresh read-only checker with `fork_turns: "none"`. The checker inspects the actual ticket, run state, evidence, notes, tests, diff or commits,
repository state, and Apple lane release.

After its report, mark the checker assignment `done`, record every observation or gap, and run
`workflow.py validate --state <state> --closure <ticket>`. Route a failing audit to `gap` with every observed gap. Route a passing audit to
`ready_to_close`.

For `close_ticket`, start from the recorded passing audit: inspect the actual scoped diff or commits, confirm preservation of unrelated dirty state,
corroborate acceptance observations, and execute the guarded transition. The engine rechecks every closure gate during and after closure.

**Complete when:** the ticket is `closed` with closure validation exiting `0`, or every observed gap is recorded and routed to an owned follow-up.

## Preserve recoverable truth

Persist ticket/worklog state, implementation notes, scoped commits, raw logs, screenshots, `run.json`, JSONL events, and Apple lane manifests. Recover from
those artifacts rather than inherited conversation, agent context, or completion labels. Recovery assignments remain self-contained and use
`fork_turns: "none"`. Perform authorized bookkeeping after the closure gate passes. Ticket coordinators own
authorized green implementation commits; the run coordinator owns missing notes or bookkeeping commits.

Report each ticket in two or three lines: changed scope or hashes, evidence location, open questions, and next frontier. End when the specification's
definition of done is observed or every remaining ticket is explicitly blocked and recorded.
