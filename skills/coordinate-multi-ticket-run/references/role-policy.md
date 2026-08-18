# Role Policy

Read this policy immediately before spawning any delegated role. Resolve every placeholder and pass the repository's current authority boundaries,
configured capacity, canonical collaborator targets, normalized state path, and workflow script path.

## Runtime configuration

| Role | Model | Reasoning effort | Context | Scope |
| --- | --- | --- | --- | --- |
| Ticket coordinator | `gpt-5.6-sol` | `high` | `fork_turns: "none"` | One ticket end to end |
| Scout | `gpt-5.6-sol` | `low` | `fork_turns: "none"` | Read-only discovery |
| Worker | `gpt-5.6-sol` | `medium`; `high` for complex work | `fork_turns: "none"` | Owned implementation |
| Reviewer | `gpt-5.6-sol` | `medium` | `fork_turns: "none"` | Read-only review |
| QA worker | `gpt-5.6-sol` | `low` | `fork_turns: "none"` | Owned verification lane |
| Acceptance checker | `gpt-5.6-sol` | `low` | `fork_turns: "none"` | Read-only closure audit |

## Shared delegation boundary

- Give each agent a complete assignment, canonical recipient, relevant collaborators, explicit ownership, declared dependencies, and exact authority.
- Treat messaging as information transfer; ownership and authority change only through the assignment ledger.
- The active coordinator is the sole editor of `run.json`, implementation notes, ticket/worklog status, and shared evidence.
- Leaves finish their assignments directly, preserve unrelated dirty state, and return findings to the ticket coordinator. They do not delegate or commit.
- A role's reasoning effort changes depth, not ownership or authority.
