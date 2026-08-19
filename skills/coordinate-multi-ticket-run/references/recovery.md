# Recovery Contract

Read this file and `references/role-policy.md` only when `workflow.py next` returns `respawn_ticket_coordinator`. Spawn a fresh ticket coordinator with
`fork_turns: "none"`, the standard ticket contract, and this addendum. Reconstruct its task context from persisted artifacts and this self-contained
assignment, never by inheriting the interrupted coordinator's conversation:

Before the spawn gate, replace the interrupted coordinator's ledger identity with the fresh coordinator's canonical target while preserving its ticket,
deliverable, ownership, dependencies, recipient, and interruption event. This is a takeover of one assignment, not a second overlapping assignment.

> A previous coordinator reached `<recovered-state>`. Start with `<workflow> recover --state <state> --ticket <ticket-id>`. Reconcile that projection
> against the ticket, notes, ledger, peer-message dependencies, evidence, `git status`, and authorized commits. Preserve valid landed work, verify it
> before relying on it, and identify the first unmet criterion. Then run `<workflow> resume --state <state> --ticket <ticket-id> --actor <fresh-target>`
> to acknowledge takeover before continuing. Treat source artifacts as proof; the prior completion label is only a hint.

**Complete when:** the fresh coordinator owns the reconciled ledger, the first unmet criterion is identified, `resume` exits `0`, and `next` returns
`wait_ticket_coordinator` for that ticket.
