---
name: orchestrate-implementation-run
description: >-
  Coordinate approved local implementation work through focused multi-agent delegation in one Codex thread. Use when a specification, feature, or
  change has independent discovery or implementation slices and the invoking agent should stay available to the user while GPT-5.6 Sol scouts and
  workers execute bounded assignments. Maintain a durable implementation-notes ledger and use isolated Apple verification lanes when Apple tooling,
  simulators, snapshots, or runtime QA are in scope. Do not use for design-only work, a tiny isolated edit, or unapproved external actions.
---

# Orchestrate Implementation Run

Keep the invoking agent as the only coordinator. Delegate substantive, non-overlapping work to leaf agents, integrate their results, and retain
approvals and final judgment in the user-facing thread. Do not create workflow engines, ticket coordinators, or extra run-state files unless the
repository already requires them.

## Establish the run

1. Read the repository's `AGENTS.md`, routed rules, specification or request, relevant source, tests, and current worktree state.
2. Identify acceptance observations, independent slices, dependencies, and authority for edits, commits, status changes, worktrees, and external
   actions. Do not infer one authority from another.
3. Use `$maintain-implementation-notes` before the first implementation edit. The invoking coordinator is the single notes writer; delegated agents
   return proposed entries instead of editing the ledger.
4. Keep a short working plan in the coordinator's task plan. Name each active agent, its deliverable, owned paths or seam, dependencies, and status.
   Do not create a second planning artifact unless repository guidance requires one.
5. Stop for a missing product, privacy, architecture, or release decision that would materially change the work. Record the question and recommended
   default in the implementation notes before asking the user.

## Delegate with three leaf roles

Keep the coordinator's current model and reasoning effort. For delegated work, use one model family and place reasoning where the ambiguity is:

| Role | Default spawn configuration | Use for |
| --- | --- | --- |
| Scout | `model: "gpt-5.6-sol"`, `reasoning_effort: "low"`, `fork_turns: "none"` | One narrow read-only question: locate files, trace a path, find rules, tests, or blast radius. |
| Worker | `model: "gpt-5.6-sol"`, `reasoning_effort: "medium"`, `fork_turns: "none"` | One routine implementation slice with explicit ownership and focused checks. |
| Smart worker | `model: "gpt-5.6-sol"`, `reasoning_effort: "high"`, `fork_turns: "none"` | One difficult or ambiguous implementation seam requiring deeper judgment. |

All delegated agents are leaves. End every assignment with:

> Complete this assignment directly. Do not spawn other agents; your parent's delegation instructions apply only to your parent.

Default to fresh context. Use inherited context only when the assignment depends on material conversation decisions that cannot be summarized safely;
still include the leaf boundary. Every fresh-context assignment must state:

- the concrete question or deliverable and success condition;
- owned files or seam, read-only or edit scope, and forbidden actions;
- repository root, relevant rules, specification sections, and acceptance criteria;
- known dependencies and canonical teammate targets;
- required checks, evidence location, and return format;
- exact commit, status-change, device, and external-action authority;
- the requirement to preserve unrelated dirty state and propose notes entries to the coordinator.

At the default four-agent capacity, the coordinator may run three independent leaves. Use fewer when work overlaps. Do not fill slots for appearance,
duplicate investigations, or assign concurrent writes to the same files or seam.

## Let the team communicate

Name information dependencies in assignments. When an agent produces or needs information for a named teammate, have it message that teammate
directly and notify the coordinator. Direct messages transfer information only; they do not expand ownership, authority, or scope. Require every
agent to summarize material peer messages in its final report.

The coordinator remains available to the user while agents work. Forward new direction to affected agents, cancel or narrow stale assignments, and
avoid starting overlapping replacement work.

## Implement and integrate

1. Send independent read-only scouts in parallel when discovery can reduce implementation risk.
2. Convert findings into the smallest useful worker assignments with disjoint ownership. Use a smart worker only where deeper reasoning pays for
   itself.
3. Inspect actual edits, test output, and peer messages as agents finish. A `DONE` label or successful process exit is not acceptance evidence.
4. Integrate across owned seams in the coordinator. Return focused gaps to the owning agent while it is available; otherwise inspect landed work
   before assigning only the remaining scope to a replacement.
5. Update implementation notes after each material judgment and implementation slice. Record decisions, deviations, trade-offs, open questions,
   repeated-work candidates, status, and observed verification evidence through `$maintain-implementation-notes`.

Delegation never transfers user approval. By default, leaves do not commit, update tickets or worklogs, operate external systems, or take
consequential UI actions. Grant only authority already provided by the user or repository contract, and state it explicitly in the assignment.

## Verify with owned evidence

Run the smallest relevant checks first and broaden only when the changed contract crosses boundaries. Assign one owner per verification resource and
keep raw results needed to prove acceptance.

For Tuist, Xcode, `xcodebuild`, Simulator, Device Hub, Playbook snapshots, or Apple runtime QA, use `$run-apple-verification-loop`. Reserve exact lanes
before Apple work, use isolated DerivedData and evidence, follow record-inspect-compare for snapshots, and release every lane on success, failure, or
interruption. Do not let generic test summaries, skipped gates, or zero-test runs stand as proof.

Before completion, the coordinator must:

- inspect the scoped diff and current worktree, preserving unrelated changes;
- map every acceptance criterion to an observed result or explicit blocker;
- confirm required tests executed and Apple lanes were released;
- validate the implementation-notes page through `$maintain-implementation-notes`;
- report the outcome, changed scope or authorized commits, evidence locations, unresolved questions, and exact verification limits.

End when acceptance is observed or all remaining work is explicitly blocked and recorded. Do not manufacture closure from agent summaries.
