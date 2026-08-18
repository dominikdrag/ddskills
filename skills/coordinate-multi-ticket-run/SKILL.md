---
name: coordinate-multi-ticket-run
description: >-
  Coordinate an approved dependency-ordered set of local implementation tickets to completion in one Codex thread. Use a deterministic workflow
  state for graph scheduling, assignment ownership, evidence gates, recovery, and truthful closure while the invoking thread delegates fresh
  role-specific agents. Use when the user asks Codex to implement multiple approved tickets end to end from a specification and local ticket graph.
  Do not use to design the specification, create tickets, or execute one isolated ticket.
---

# Coordinate Multi-Ticket Run

Walk an approved ticket graph to its truthful stopping condition. Keep the invoking thread as run coordinator and give each ticket a fresh end-to-end
coordinator. Use the bundled workflow engine for deterministic decisions; retain semantic judgment, permissions, collaboration calls, and user
communication in the agents.

## Establish the run

1. Resolve the Git root and inspect the current worktree.
2. Identify the approved specification and complete ticket set. Do not create a separate run brief.
3. Read `AGENTS.md`, its dispatcher, routed workflow/tracker/commit/testing/QA rules, domain glossary, ticket schema, and definition of done. Repository
   guidance overrides this skill.
4. Resolve the evidence location from explicit user/specification guidance, repository guidance, or existing convention. Otherwise choose a
   task-scoped location outside the worktree or verify it is ignored.
5. Determine separate authority for commits, ticket/worklog/notes changes, worktrees, and external actions. Never infer one from another.
6. Use `$maintain-implementation-notes` before the first implementation edit.
7. Read [references/workflow-state.md](references/workflow-state.md). Create `<evidence>/run.json` as the normalized projection of the actual tickets,
   repository statuses, assignments, and evidence. Repository artifacts remain authoritative facts; the workflow state owns deterministic orchestration.
8. Resolve this skill's directory and run `python3 <skill-dir>/scripts/workflow.py validate --state <evidence>/run.json`.

Stop for a missing product decision when the graph, blockers, or acceptance criteria are not stable enough to execute. This skill executes an
approved graph; it does not silently redesign one.

## Use the agent topology

Do not spawn another run coordinator or change the invoking agent's configuration. Read the configured concurrency capacity and keep one fresh ticket
coordinator alive at a time. At the default four-agent capacity, reserve one slot for the invoking agent, one for the ticket coordinator, and at most
two for useful non-overlapping leaves. Serialize work when capacity, repository ownership, Apple tooling, or device ownership requires it; shell
processes do not consume agent slots.

Read [references/role-contracts.md](references/role-contracts.md) before the first spawn. Use its exact model, effort, fresh-context, ownership,
authority, messaging, and no-leaf-delegation contracts. Do not fill concurrency without independent work.

The run coordinator owns `run.json` between tickets. The active ticket coordinator may update assignments and evidence during its ticket. Leaves never
edit the shared state, implementation notes, ticket status, or another agent's evidence.

Before every spawn:

1. Add the complete assignment to `run.json`, including canonical target, role, deliverable, owned paths or seams, dependencies, recipient, and status.
2. Run `workflow.py validate`.
3. Spawn only when validation exits `0`; an ownership or dependency error blocks the spawn.

## Drive the workflow

Run `workflow.py next` and obey its compact action:

- `spawn_ticket_coordinator`: transition the named ticket to `coordinating`, then spawn it with the role contract.
- `wait_ticket_coordinator`: stay available to the user and wait or forward relevant direction.
- `spawn_acceptance_checker`: spawn a fresh read-only checker after transitioning the ticket to `acceptance`.
- `return_acceptance_gaps`: send the named gaps to the live coordinator and transition only through an allowed follow-up phase.
- `reject_closure`: keep the ticket open and repair the reported evidence or state gaps.
- `close_ticket`: inspect the actual scoped diff or commits, confirm unrelated dirty state was preserved, and corroborate acceptance with observations;
  then transition to `closed`, where the engine rechecks every closure gate.
- `respawn_ticket_coordinator`: use the returned recovered state plus the recovered-coordinator role addendum.
- `run_blocked`: record blockers in implementation notes and ask one concise question only when user input can unblock work.
- `run_complete`: perform the final definition-of-done audit and report completion.
- `invalid_state`: fix the state or source-artifact projection before any further spawn or closure.

When a coordinator finishes implementation, transition to `acceptance`. A fresh acceptance checker must inspect the actual ticket, run state, evidence,
notes, tests, diff or commits, repository state, and Apple lane release. Transition a failing audit to `gap`; transition a passing audit to
`ready_to_close` only after recording its observations. Plain `validate` proves structure only; the checker must use `validate --closure <ticket>`.

When Apple build, test, Simulator, Device Hub, Playbook snapshot, or runtime QA is required, use `$run-apple-verification-loop`. Reserve the lane before
Apple work and release it on success, failure, or interruption.

## Preserve recoverable truth

Keep ticket/worklog state, implementation notes, scoped commits, raw logs, screenshots, `run.json`, its JSONL events, and Apple lane manifests as the
recoverable run. Use `workflow.py interrupt` when an active coordinator dies, then use `next` or `recover`; never reconstruct status from context or a
`DONE` label.

Only perform authorized bookkeeping after acceptance and the boundary audit pass. Ticket coordinators own authorized green implementation commits;
leaves never commit, and the run coordinator commits only missing notes or bookkeeping. Report each ticket in two or three lines with changed scope
or hashes, evidence location, open questions, and the next frontier. End only when the specification's definition of done is observed or every
remaining ticket is explicitly blocked and recorded.
