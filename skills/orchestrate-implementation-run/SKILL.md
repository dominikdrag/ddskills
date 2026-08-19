---
name: orchestrate-implementation-run
description: >-
  Orchestrate an approved feature or specification as a lightweight hub-and-spoke team. Use when it contains several bounded discovery or
  implementation slices that can run independently while one coordinator stays user-facing and the task plan is sufficient orchestration state.
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
3. Resolve edit, commit, status, worktree, device, UI, and external-action authority separately. For commits, record the starting `HEAD` and dirty
   paths, whether commits are allowed, the repository's message and staging conventions, and who may create them. Keep the coordinator as the sole
   integration and commit owner unless the repository explicitly establishes another safe ownership model; leaves do not commit by default.
4. Resolve the repository's implementation-notes convention and destination. Keep the coordinator as its single writer; leaves return proposed
   entries.
5. Route each material uncertainty to a read-only scout or record it with its affected slice, impact, and recommended default. Ask the user when the
   answer changes product, privacy, architecture, or release scope.

**Complete orientation when:** every requested outcome has an acceptance observation; every proposed slice has its dependencies and unknowns named;
authority, the commit owner, commit conventions, and notes ownership are explicit; and every material uncertainty is routed to a scout or recorded
as a blocking question.

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

Treat a dependency-changing slice as in flight until the coordinator accepts its integrated result. When commits are authorized, do not assign work
that depends on the changed seam until the prerequisite slice passes focused checks and is committed. Without commit authority, wait for the same
integration and check gate, then name the exact uncommitted dependency in the downstream assignment. An explicit repository ownership model may
allow another commit owner; follow its isolation and handoff rules rather than inventing one for the run.

**Complete assignment when:** every active leaf has the full assignment contract, all write ownership is disjoint, every dependency has a named
recipient, and the coordinator remains available to the user.

## 3. Implement and integrate

1. Send independent read-only scouts in parallel when discovery can reduce implementation risk.
2. Before the first implementation edit, invoke `$maintain-implementation-notes` to create or reuse the resolved page.
3. Convert stable findings into the smallest useful worker assignments. Use a smart worker for a difficult or ambiguous seam.
4. Inspect actual edits, underlying check output, and peer messages as each leaf finishes. Return focused gaps to the owning leaf while it is live.
5. Before replacement, inspect landed work and assign only the remaining scope.
6. Integrate a coherent slice in the coordinator. A leaf report is not a commit boundary: include every change required for one reviewable behavior or
   contract, and exclude incomplete or unrelated work.
7. Run the slice's focused checks. Update implementation notes and plan status with its decisions, scope, observed evidence, and blockers.
8. When commits are authorized, land the accepted slice before assigning dependent work:
   - inspect `git status` against the recorded starting state and identify the exact owned files or patches;
   - stage only that scope, never unrelated dirty state or a broad add whose contents were not inspected;
   - inspect the complete staged diff and run the repository's staged-diff checks before every commit;
   - commit with the repository's convention, then record the hash beside the slice and its check evidence.
9. Keep notes traceable without claiming that a commit contains its own hash. Mark the hash pending in the notes included with the slice, record the
   resulting hash immediately in orchestration status, and add it to the notes in the next authorized slice or a final bookkeeping commit.

Apply these gates explicitly:

- **No commit authority:** do not stage or commit. Keep the accepted slice identifiable in the worktree, record its exact paths and evidence, and
  report it as uncommitted. Downstream work may start only after the integrated predecessor passes its focused checks and the assignment names that
  shared-worktree dependency.
- **Failed checks:** do not commit the slice or unlock dependent work. Record the failure, return the smallest correction to the current owner when
  practical, and rerun the focused gate after the fix.
- **Partial integration:** do not commit a mixture of finished and unfinished behavior. Commit an independently coherent subset only when it is safe
  and reviewable on its own; otherwise keep the whole seam in progress.
- **Shared dependency seam:** when multiple leaves contribute to one seam, stop overlapping writes and serialize integration in the coordinator.
  Run the seam's focused checks on the combined result and create one coherent commit before downstream assignment.

**Complete integration when:** every slice is integrated and inspected or explicitly blocked; every material peer message is resolved; all focused
checks have observed results; every authorized accepted slice is committed before dependent work; and implementation notes and orchestration status
reflect the current decisions, evidence, commit hashes, and blockers.

## 4. Verify and close

Run the smallest relevant checks first and broaden only when the changed contract crosses boundaries. Assign one owner per verification resource and
retain the underlying results.

For any Tuist, Xcode, `xcodebuild`, Simulator, Device Hub, Playbook snapshot, or Apple runtime-QA branch, invoke `$run-apple-verification-loop`.
Require its evidence and lane-release completion criteria before closure.

Close against the acceptance map:

- inspect the commit range from the recorded starting `HEAD`, each committed slice, and the current worktree;
- compare committed paths with `git status`, preserving recorded unrelated changes and identifying any intended scope left uncommitted;
- map every acceptance criterion to an observed result or explicit blocker;
- confirm every required test executed and every Apple lane was released;
- validate the implementation-notes page with `$maintain-implementation-notes` and, when commits are authorized, commit final hash bookkeeping;
- report committed hashes and summaries in order, the checks and evidence for each slice, remaining worktree changes, blockers, and exact verification
  limits. When authority was absent, state that no commits were created and report the exact uncommitted scope instead.

**Complete the run when:** every acceptance criterion has an observed result or recorded blocker, every required resource is released, the scoped
worktree and notes agree with the committed scope, every intended authorized change is committed or explicitly blocked, and no active assignment
remains unresolved.
