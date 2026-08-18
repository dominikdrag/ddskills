# Acceptance Checker Contract

Read this file and `references/role-policy.md` only after a ticket reaches `acceptance`. Use the acceptance-checker runtime configuration and read-only
authority. Replace every placeholder in this assignment:

> Audit `<ticket>` using `<evidence>`, `<notes>`, normalized state `<state>`, workflow `<workflow>`, the coordinator report, actual diff or commits, and
> current repository state. For every acceptance criterion, report its ticket marking, named observation, evidence location, and pass or gap. Confirm
> required tests executed with positive counts and authoritative exits; snapshot record-inspect-compare completion; runtime provenance; Apple lane
> release; changed-path scope; assignment ownership and unresolved dependencies; authorized status, worklog, and commit changes; and preservation of
> unrelated dirty state. Reconcile the normalized projection against source artifacts. Send every observed gap to `<ticket-coordinator-target>`. List
> every criterion lacking sufficient evidence and every uncommitted or unrelated change. Return findings to the run coordinator so it can mark this
> assignment complete, record the observations, and run `<workflow> validate --state <state> --closure <ticket-id>`. Make no edits, commits, status
> changes, or device actions.

**Complete when:** every criterion and deterministic closure gate has an observed pass or named gap, and every gap has been sent to its owning coordinator.
