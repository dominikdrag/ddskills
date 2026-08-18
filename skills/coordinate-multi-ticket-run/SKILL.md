---
name: coordinate-multi-ticket-run
description: >-
  Coordinate an approved dependency-ordered set of local implementation tickets to completion in one Codex thread. The invoking thread acts as
  the run coordinator while delegating to disposable GPT-5.6 Sol xhigh ticket coordinators and fresh role-specific leaf agents, with persistent
  external state, evidence-backed acceptance audits, and blocked/dead-agent recovery. Use when the user asks Codex to implement multiple approved
  tickets end to end from a specification and local ticket graph. Do not use to design the specification, create the tickets, or execute one
  isolated ticket.
---

# Coordinate Multi-Ticket Run

Walk an approved local ticket graph to its truthful stopping condition without accumulating ticket-level implementation context at the top.
The invoking thread or agent is the run coordinator: keep it with the user and give each ticket a fresh end-to-end coordinator.

## Establish the run contract

1. Resolve the current Git root. Do not require or embed an absolute repository path.
2. Identify the specification and complete ticket set from the user's request or current repository context. Do not create a separate run brief.
3. Read the repository's `AGENTS.md`, rule dispatcher, routed workflow/tracker/commit/testing/QA rules, domain glossary, specification, ticket schema,
   and definition of done. Repository guidance overrides this skill.
4. Resolve the evidence location from, in order: an explicit user or specification path, repository guidance, or an existing feature convention.
   If none exists, choose a task-scoped local location. Keep it outside the worktree or verify it is ignored, then record it in the implementation
   notes.
5. Determine whether the user or active repository workflow authorizes commits, ticket-status changes, worklog changes, notes commits, worktrees, and
   external actions. Do not infer one kind of authority from another.
6. Use `$maintain-implementation-notes` before the first implementation edit. The notes page is part of the run's persistent state.

If the specification, tickets, blockers, or acceptance criteria are not stable enough to execute, stop and request the missing decision. This skill
executes an approved graph; it does not silently redesign one.

## Use the prescribed topology

Do not spawn a separate run coordinator or assign a model or reasoning effort to it. The invoking thread already owns that role and retains its
current configuration.

Use `model: "gpt-5.6-sol"` for every delegated agent and assign effort where ambiguity lives. Translate the human-facing labels to callable values:
Sol Light is `reasoning_effort: "low"`, Sol Medium is `"medium"`, Sol High is `"high"`, and Sol xhigh is `"xhigh"`. Never pass `"light"` as a
reasoning-effort value.

| Delegated role | Label and callable effort | Responsibility |
| --- | --- | --- |
| Ticket coordinator | Sol xhigh / `"xhigh"`, fresh | Own one ticket end to end, including delegated work and authorized closure. |
| Scout | Sol Light / `"low"`, fresh, read-only | Answer one bounded codebase, rule, test, scenario, or blast-radius question. |
| Worker | Sol Medium / `"medium"`, fresh | Implement one routine slice on explicitly owned files. |
| Complex worker | Sol High / `"high"`, fresh | Implement a wide seam, projection/engine core, migration, or tricky tests. |
| Reviewer | Sol High / `"high"`, fresh, read-only | Review repository standards and specification/ticket acceptance. |
| QA worker | Sol Medium / `"medium"`, fresh | Run the repository's device or visual-verification flow and produce evidence. |
| Acceptance checker | Sol Light / `"low"`, fresh, read-only | Audit ticket closure against evidence and repository state. |

Read the configured per-thread concurrency capacity; it defaults to four agents including the invoking agent and every delegated agent. At the
default:

```text
[invoking agent] [ticket coordinator] [leaf] [leaf]
```

Keep one ticket coordinator alive at a time. With fewer than four slots, serialize leaves. With four slots, the ticket coordinator may run two useful,
non-overlapping leaves. With more than four, it may add independent scouts or workers when their ownership and dependencies are explicit. Do not fill
capacity without useful independent work. Shell processes do not consume agent slots, but overlapping repository, workspace, DerivedData, device, or
file ownership still must be serialized.

Every leaf must receive `fork_turns: "none"`, a self-contained assignment, and this boundary:

> Complete this assignment directly. Do not spawn other agents. Your parent's delegation instructions apply only to your parent.

Higher reasoning effort does not grant delegation authority. A Sol High complex worker remains a leaf unless its assignment explicitly promotes it;
under this topology, only the ticket coordinator delegates ticket work.

Read [references/role-contracts.md](references/role-contracts.md) before spawning the first ticket coordinator or leaf.

## Coordinate active agents

Before spawning any leaf, maintain an active-assignment ledger under the ticket evidence location, normally `plan.md`, with:

```text
agent · role · question or deliverable · owned files or seams · depends on · message recipient · status
```

Check the ledger before every spawn to prevent duplicate investigation or overlapping writes. Update it when ownership, dependencies, or status change
so an interrupted coordinator can recover the live topology.

Name canonical collaborator targets and information dependencies in leaf assignments. When a scout, reviewer, QA worker, or worker finds information
needed by a named active collaborator, it should message that collaborator directly and notify the ticket coordinator instead of waiting for report
relay. Direct messages transfer information only: they do not change file ownership, task scope, approval authority, commit authority, or the leaf
boundary. Every agent still summarizes material peer messages in its final report.

## Keep state outside agent context

Treat these artifacts as the recoverable run state:

- ticket status, blockers, and acceptance checkboxes;
- the implementation-notes Status and Open Questions sections;
- worklog state and session history when the repository uses them;
- scoped commits and `git log` when commits are authorized;
- per-ticket evidence, raw logs, and screenshots;
- the active-assignment ledger and peer-message dependencies;
- active Apple verification lane manifests and explicit release state.

Re-derive the frontier from these artifacts after any interruption. Never reconstruct status from memory or an agent's `DONE` label alone.

## Run one ticket

1. Compute the frontier: tickets not done whose blockers are all done. Honor the repository's exact status vocabulary.
2. Select the lowest-numbered frontier ticket unless the user or specification defines another priority.
3. Spawn one GPT-5.6 Sol xhigh ticket coordinator with `fork_turns: "none"` using the ticket-coordinator contract. Point it directly at the
   specification, ticket set, selected ticket, notes page, and resolved evidence location.
4. Stay available to the user. Forward new direction affecting the active ticket to its coordinator; do not start a second coordinator.
5. Require the ticket coordinator to orient, plan thin slices, maintain the active-assignment ledger, delegate bounded leaves, route direct dependency
   messages, implement, run focused gates, obtain fresh review, maintain implementation notes, and return the bounded report from the role contract.
6. When the ticket needs Tuist, Xcode, Simulator, Device Hub, Playbook snapshots, or Apple runtime QA, require the ticket coordinator or QA worker to
   use `$run-apple-verification-loop`. Do not duplicate its lane commands here. Lane reservation precedes Apple work; release is required on success,
   failure, or interruption.
7. Spawn a fresh GPT-5.6 Sol Light acceptance checker with `reasoning_effort: "low"`. It must inspect the ticket, assignment ledger, evidence, notes,
   actual test execution, changed scope, repository state, and Apple lane release where applicable.
8. Perform the run coordinator's bounded boundary audit: inspect the ticket's scoped diff or commits, confirm unrelated dirty state was preserved,
   and verify the acceptance check is backed by observations rather than summaries.
9. Send any gap to the still-live ticket coordinator. Wait for its focused follow-up and rerun only the affected acceptance checks.
10. Only after the audit passes, perform authorized ticket/worklog/notes bookkeeping. Ticket coordinators own green implementation commits when
    authorized; leaves never commit; the run coordinator commits only missing bookkeeping or notes updates.
11. Report the ticket, hashes or changed scope, evidence location, open questions, and next frontier to the user in two or three lines. Repeat.

## Handle blockers and interrupted agents

For a product, privacy, architecture, release-scope, external-approval, or otherwise reserved decision:

1. Record the question through `$maintain-implementation-notes`, including the affected ticket and recommended default.
2. Ask the user one concise question.
3. Continue with another frontier ticket when one exists.
4. Stop only when the frontier is empty or every remaining ticket is blocked on the user or external state.

For a dead or interrupted ticket coordinator:

1. Inspect ticket state, notes, the active-assignment ledger, evidence, `git status`, and authorized commits.
2. Record exactly what landed and what remains; do not infer completion.
3. Respawn the same ticket with a fresh GPT-5.6 Sol xhigh coordinator and the recovered-state addendum from the role contracts.

## Enforce truthful closure

Reject closure when any of the following holds:

- a checked criterion lacks a named observation;
- a required test did not execute, executed zero tests, or was skipped behind a gate;
- snapshot evidence skipped record, rendered inspection, or clean comparison;
- runtime evidence is empty, loading, partial, on the wrong binary/scenario/device, or from an unowned lane;
- an Apple verification lane remains leased;
- the assignment ledger shows duplicate, overlapping, or unresolved ownership;
- the scoped diff or commit contains unrelated work;
- the notes page omits a material interpretation, deviation, tradeoff, blocker, or repeated-work candidate;
- a status, worklog transition, commit, or external action lacks authority.

The whole run ends only when the specification's definition of done is observed, or when every remaining item is explicitly blocked and recorded.
