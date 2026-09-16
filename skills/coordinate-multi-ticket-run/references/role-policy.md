# Role Policy

Read this policy immediately before spawning any delegated role. Resolve every placeholder and pass the repository's current authority boundaries,
configured capacity, canonical collaborator targets, normalized state path, and workflow script path.

## Runtime configuration

Use the user's or host's configured model by default; omit a model override unless an explicit preference or repository rule selects one. Check available models and supported reasoning efforts before applying an override. The effort labels below express relative depth; use the closest supported setting when the host differs.

| Role | Model | Reasoning effort | Context | Scope |
| --- | --- | --- | --- | --- |
| Ticket coordinator | Configured default | `high` | `fork_turns: "none"` | One ticket end to end |
| Scout | Configured default | `low` | `fork_turns: "none"` | Read-only discovery |
| Worker | Configured default | `medium`; `high` for complex work | `fork_turns: "none"` | Owned implementation |
| Reviewer | Configured default | `medium` | `fork_turns: "none"` | Read-only review |
| QA worker | Configured default | `low` | `fork_turns: "none"` | Owned verification lane |
| Acceptance checker | Configured default | `low` | `fork_turns: "none"` | Read-only closure audit |

Pass `fork_turns: "none"` explicitly on every `spawn_agent` call. Never rely on the collaboration tool's default. The setting covers ordinary,
replacement, recovery, and final-audit agents. Override it only when the user explicitly requests inherited conversation history or the binding run
contract requires it; record that exception and its reason in the assignment ledger before spawning.

`"none"` removes parent task conversation, so the assignment must carry every task-specific fact the agent needs: objective, canonical paths, current
frontier and dependencies, commits and evidence state, ownership and protected paths, permitted actions, verification or Apple-lane requirements,
safety boundaries, collaborators and recipient, and report format. Do not use a positive turn count as a shortcut: a long orchestration turn can contain
the entire run even when the number looks small.

## Shared delegation boundary

- Give each agent a complete assignment, canonical recipient, relevant collaborators, explicit ownership, declared dependencies, and exact authority.
- Treat messaging as information transfer; ownership and authority change only through the assignment ledger.
- The active coordinator is the sole editor of `run.json`, implementation notes, ticket/worklog status, and shared evidence.
- Leaves finish their assignments directly, preserve unrelated dirty state, and return findings to the ticket coordinator. They do not delegate or commit.
- A role's reasoning effort changes depth, not ownership or authority.
