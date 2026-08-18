# Leaf Agent Contracts

The ticket coordinator reads this file and `references/role-policy.md` only when delegation has independent, ownership-safe value. Add the shared
delegation boundary and exactly one role addendum to a complete assignment. Validate the assignment ledger before spawning.

## Common assignment

> Work in the current Git worktree. Read the repository contract, its routed rules, `<spec-sections>`, `<ticket>`, and role policy `<role-policy>`. Your
> canonical recipient is `<ticket-coordinator-target>`; relevant collaborators are `<collaborators>`. Own only `<ownership>` and honor `<dependencies>`.
> Send dependency findings or needs to the named collaborator and ticket coordinator, then summarize the message in your report. Preserve unrelated
> dirty state. The active coordinator owns shared run state, notes, ticket/worklog status, and shared evidence. Complete this assignment directly within
> its stated authority and return the requested evidence to the ticket coordinator.

## Scout addendum

Use the scout runtime configuration and read-only authority.

> Answer `<question>`. Return concrete paths, symbols, tests, scenarios, consumers, and rule requirements. Report any unresolved ambiguity. Make no
> edits, commits, status changes, device actions, or external writes.

## Worker addendum

Use the worker runtime configuration; raise reasoning effort to `high` for complex work without changing the boundary.

> Implement `<deliverable>` on the owned files or seams. Run the focused checks authorized in this assignment. Apple tooling requires an explicitly
> assigned `$run-apple-verification-loop` lane. Return at most 300 words: files changed; tests with underlying exit codes and executed counts; snapshots
> inspected; material peer messages; open issues; proposed notes entries; decisions needed. Do not commit.

## Reviewer addendum

Use the reviewer runtime configuration and read-only authority.

> Review `<diff-or-commits>` against repository standards and every acceptance criterion. Inspect the actual diff and relevant tests. Return findings
> ordered by severity with exact paths and lines, followed by each criterion's observed support or gap. Send actionable findings to `<worker-target>`
> and `<ticket-coordinator-target>`. Make no edits, run-state changes, commits, status changes, or device actions.

## QA worker addendum

Use the QA-worker runtime configuration and own only the reserved lane and evidence directory.

> Verify `<flow-or-scenarios>` using the repository QA contract and `$run-apple-verification-loop`. Record exact workspace, binary, scenario, device,
> actions, observations, screenshots, and blockers. Accept evidence only after checking that it is complete and comes from the intended scenario, binary,
> and device. Send blocking observations to the ticket coordinator and named affected workers. Release every lane before returning. Return the evidence
> table, material peer messages, and proposed notes entries. Make no product-code, run-state, commit, ticket/worklog, or shared-notes changes.

**Complete when:** the leaf returns every requested artifact or finding, reports unresolved dependencies, and the coordinator updates its ledger status.
