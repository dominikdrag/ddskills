# Coordinate Multi-Ticket Run

Coordinate an approved, dependency-ordered ticket graph from its current frontier to evidence-backed completion.

Use this skill when a specification and its implementation tickets are already approved. It is not a planning skill: it does not design the
specification, create tickets, or replace the focused workflow for one isolated ticket.

## Orchestration

The thread or agent that invokes the skill acts as the run coordinator. It remains available to the user, owns the whole-ticket frontier, and starts
one fresh ticket coordinator at a time. The ticket coordinator may delegate bounded, non-overlapping work to leaf agents and then hands the result
back for an independent acceptance audit.

The run coordinator is not a separate spawned agent. The skill does not assign or change its model or reasoning effort; those assignments apply only
to delegated agents.

At the default four-agent concurrency limit, the topology is:

```text
User
  |
  v
+--------------------------------------------------------+
| Current thread / invoking agent                        |
| Acts as run coordinator; not separately spawned       |
| Owns frontier, user contact, audit, and recovery       |
+----------------------------+---------------------------+
                             |
                             | one frontier ticket at a time
                             v
              +------------------------------------------+
              | Ticket coordinator                       |
              | GPT-5.6 Sol xhigh / "xhigh"              |
              | Fresh: owns one ticket end to end         |
              +------------------+-----------------------+
                                 |
                    +------------+------------+
                    |                         |
                    v                         v
          +--------------------+    +--------------------+
          | Leaf agent         |    | Leaf agent         |
          | Fresh, no spawning |    | Fresh, no spawning |
          | Scoped ownership   |    | Scoped ownership   |
          +--------------------+    +--------------------+
                    |                         |
                    +------------+------------+
                                 |
                                 v
              +------------------------------------------+
              | Ticket result and evidence               |
              +------------------+-----------------------+
                                 |
                                 v
              +------------------------------------------+
              | Acceptance checker                       |
              | GPT-5.6 Sol Light / "low", read-only     |
              +------------------+-----------------------+
                                 |
                      pass ------+------ gap
                       |                  |
                       v                  v
              close ticket       return focused gap to
              and advance        the ticket coordinator
```

Leaf roles are selected by the work:

| Role | Model and effort | Scope |
| --- | --- | --- |
| Scout | GPT-5.6 Sol Light, `low` | Narrow read-only discovery |
| Worker | GPT-5.6 Sol Medium, `medium` | Routine implementation on owned files |
| Complex worker | GPT-5.6 Sol High, `high` | Difficult implementation or ambiguity |
| Reviewer | GPT-5.6 Sol High, `high` | Read-only standards and acceptance review |
| QA worker | GPT-5.6 Sol Medium, `medium` | Runtime or visual verification |

Only the invoking agent and ticket coordinator delegate. Every leaf receives fresh context, a complete assignment, explicit ownership, named
dependencies, and a no-delegation boundary.

## Durable state

The system does not treat agent context or a `DONE` label as proof. It recovers and audits from repository-visible artifacts:

- ticket status, blockers, and acceptance criteria;
- the implementation-notes ledger;
- scoped commits and the current Git state;
- raw test, snapshot, and runtime evidence;
- the active-assignment ledger;
- Apple verification lane manifests and release state.

The skill uses [`maintain-implementation-notes`](../maintain-implementation-notes/README.md) throughout the run and delegates Apple-platform
verification to [`run-apple-verification-loop`](../run-apple-verification-loop/README.md).

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill coordinate-multi-ticket-run \
  -g -a codex -y
```

See the executable agent instructions in [SKILL.md](SKILL.md) and the complete assignment templates in [references/role-contracts.md](references/role-contracts.md).

[Back to all skills](../../README.md)
