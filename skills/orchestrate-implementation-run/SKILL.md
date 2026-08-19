---
name: orchestrate-implementation-run
description: >-
  Orchestrate an approved feature or specification as a hub-and-spoke team. Use when it contains several bounded discovery or implementation slices
  that can run independently while one coordinator stays user-facing. For an approved dependency-ordered ticket graph, use
  `$coordinate-multi-ticket-run`.
---

# Orchestrate Implementation Run

Use a hub-and-spoke topology: keep the invoking agent as coordinator and every delegated agent as a leaf. Keep the coordinator user-facing and make it
the sole owner of integration, approvals, implementation notes, and closure. Use the coordinator's task plan as the orchestration state unless the
repository contract owns another state artifact.

Run four coordinator phases in order: **Orient → Assign leaves → Implement and integrate → Verify and close**. Supporting skills satisfy steps inside
a phase; only these four completion gates advance the run.

## 1. Orient

1. Read the repository's `AGENTS.md`, routed rules, specification or request, relevant source, tests, and current worktree state.
2. Build an acceptance map from every requested outcome to a checkable observation. Propose independent slices; name known dependencies and unknowns.
3. Resolve edit, commit, status, worktree, device, UI, and external-action authority separately.
4. Resolve the repository's implementation-notes convention and destination. Keep the coordinator as its single writer; leaves return proposed
   entries.
5. Route each material uncertainty to a read-only scout or record it with its affected slice, impact, and recommended default. Ask the user when the
   answer changes product, privacy, architecture, or release scope.

**Complete orientation when:** every requested outcome has an acceptance observation; every proposed slice has its dependencies and unknowns named;
authority and notes ownership are explicit; and every material uncertainty is routed to a scout or recorded as a blocking question.

## 2. Assign leaves

Use one model family and place reasoning where the ambiguity is:

| Role | Default spawn configuration | Use for |
| --- | --- | --- |
| Scout | `model: "gpt-5.6-sol"`, `reasoning_effort: "low"`, `fork_turns: "none"` | One narrow read-only question: locate files, trace a path, find rules, tests, or blast radius. |
| Worker | `model: "gpt-5.6-sol"`, `reasoning_effort: "medium"`, `fork_turns: "none"` | One routine implementation slice with explicit ownership and focused checks. |
| Smart worker | `model: "gpt-5.6-sol"`, `reasoning_effort: "high"`, `fork_turns: "none"` | One difficult or ambiguous implementation seam requiring deeper judgment. |

Default to fresh context. Inherit context only when a material conversation decision cannot be summarized safely. End every assignment with the leaf
boundary:

> Complete this assignment directly and return results to your parent. Remain a leaf: do not spawn other agents.

Give every leaf one self-contained assignment containing:

- deliverable and checkable completion criterion;
- repository root, relevant rules, specification sections, and acceptance observations;
- owned files or seam, read-only or edit scope, and exact authority;
- dependencies, canonical teammate recipients, required checks, evidence location, and return format;
- preservation of unrelated dirty state and proposed implementation-notes entries.

Name information dependencies. Have a leaf message the named teammate and coordinator when it produces or needs dependency information, then summarize
material peer messages in its final report. Messages carry information; the original ownership and authority remain unchanged.

Read the configured concurrency capacity. At four slots, run the coordinator and up to three independent leaves. Spawn only work with disjoint write
ownership.

**Complete assignment when:** every active leaf has the full assignment contract, all write ownership is disjoint, every dependency has a named
recipient, and the coordinator remains available to the user.

## 3. Implement and integrate

1. Send independent read-only scouts in parallel when discovery can reduce implementation risk.
2. Before the first implementation edit, invoke `$maintain-implementation-notes` to create or reuse the resolved page.
3. Convert stable findings into the smallest useful worker assignments. Use a smart worker for a difficult or ambiguous seam.
4. Inspect actual edits, underlying check output, and peer messages as each leaf finishes. Return focused gaps to the owning leaf while it is live.
5. Before replacement, inspect landed work and assign only the remaining scope.
6. Update implementation notes after each material judgment and completed slice.

**Complete integration when:** every slice is integrated and inspected or explicitly blocked; every material peer message is resolved; all focused
checks have observed results; and implementation notes reflect the current decisions, evidence, and blockers.

## 4. Verify and close

Run the smallest relevant checks first and broaden only when the changed contract crosses boundaries. Assign one owner per verification resource and
retain the underlying results.

For any Tuist, Xcode, `xcodebuild`, Simulator, Device Hub, Playbook snapshot, or Apple runtime-QA branch, invoke `$run-apple-verification-loop`.
Require its evidence and lane-release completion criteria before closure.

Close against the acceptance map:

- inspect the scoped diff and current worktree, preserving unrelated changes;
- map every acceptance criterion to an observed result or explicit blocker;
- confirm every required test executed and every Apple lane was released;
- validate the implementation-notes page with `$maintain-implementation-notes`;
- report changed scope or authorized commits, evidence locations, blockers, and exact verification limits.

**Complete the run when:** every acceptance criterion has an observed result or recorded blocker, every required resource is released, the scoped
worktree and notes are current, and no active assignment remains unresolved.
