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
