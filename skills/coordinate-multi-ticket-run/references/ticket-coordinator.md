# Ticket Coordinator Contract

Read this file and `references/role-policy.md` immediately before spawning a ticket coordinator. Use the ticket-coordinator runtime configuration and
replace every placeholder in this assignment:

> Coordinate `<ticket-id>` from its current frontier to acceptance. Work in the current Git worktree. Read `AGENTS.md` and its dispatcher first, then
> the routed rules and sources for this work. Read `<spec>`, the complete ticket set `<tickets>`, `<ticket>`, role policy `<role-policy>`, normalized state
> `<state>`, and workflow `<workflow>`. Use `<notes>` through `$maintain-implementation-notes`; keep evidence under `<evidence>`. Reconcile blockers and
> acceptance observations before editing. Maintain the assignment ledger and run `<workflow> validate --state <state>` before each spawn. Own the ticket
> end to end: scout, plan thin slices, delegate bounded ownership-safe leaves, route dependency messages, implement, verify, obtain fresh review, maintain
> notes, and perform authorized commits or status changes. For Apple tooling or runtime QA, use `$run-apple-verification-loop` and release every lane.
> When implementation and focused verification satisfy the ticket, record the required evidence, mark its assignments complete, and transition the
> ticket to `acceptance`. Otherwise persist the exact blocker, gap, or interruption.
> Return at most 300 words covering: ticket; changed files and commit hashes; final phase; criteria met or deferred; tests with underlying exit codes and
> executed counts; snapshots inspected; runtime device, UDID, and lane release; evidence path; final ledger; material peer messages; notes entries; open
> issues and decisions. Address the run coordinator as the data recipient, not the user.

The assignment also names the authorization boundaries, repository-specific restrictions, configured capacity, canonical collaborator targets, and
paths for `<role-policy>`, `<state>`, and `<workflow>`.

**Complete when:** the coordinator returns the structured report and the ticket is in `acceptance`, or persists an explicit blocker or interruption that
the run coordinator can route without reconstructing context.
