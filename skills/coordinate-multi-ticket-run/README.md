# Coordinate Multi-Ticket Run

Coordinate an approved, dependency-ordered ticket graph from its current frontier to evidence-backed completion. The skill is a thin Codex-facing
policy and collaboration layer over a deterministic workflow state machine.

Use this skill when a specification and its implementation tickets are already approved. It is not a planning skill: it does not design the
specification, create tickets, or replace the focused workflow for one isolated ticket.

## Orchestration

The thread or agent that invokes the skill acts as the run coordinator. It remains available to the user, owns the whole-ticket frontier, and starts
one fresh ticket coordinator at a time. The ticket coordinator may delegate bounded, non-overlapping work to leaf agents and then hands the result
back for an independent acceptance audit.

The run coordinator is not a separate spawned agent. The skill does not assign or change its model or reasoning effort; those assignments apply only
to delegated agents. `scripts/workflow.py` validates the ticket graph and assignment ledger, derives the next action, enforces phase transitions,
rejects incomplete closure, records compact events, and derives recovery state. Codex retains repository interpretation, permission decisions, agent
control, semantic review, and user communication.

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
              | GPT-5.6 Sol High / "high"                |
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
| Reviewer | GPT-5.6 Sol Medium, `medium` | Read-only standards and acceptance review |
| QA worker | GPT-5.6 Sol Light, `low` | Runtime or visual verification |

Only the invoking agent and ticket coordinator delegate. Every leaf receives fresh context, a complete assignment, explicit ownership, named
dependencies, and a no-delegation boundary.

## Durable state

The system does not treat agent context or a `DONE` label as proof. It recovers and audits from repository-visible artifacts:

- ticket status, blockers, and acceptance criteria;
- the implementation-notes ledger;
- scoped commits and the current Git state;
- raw test, snapshot, and runtime evidence;
- the normalized `run.json` ticket graph, active-assignment ledger, evidence projection, and compact JSONL events;
- Apple verification lane manifests and release state.

The skill uses [`maintain-implementation-notes`](../maintain-implementation-notes/README.md) throughout the run and delegates Apple-platform
verification to [`run-apple-verification-loop`](../run-apple-verification-loop/README.md). The workflow schema and commands are documented in
[`references/workflow-state.md`](references/workflow-state.md).

## Deterministic verification

From this skill directory:

```sh
python3 scripts/workflow.py validate --state scripts/fixtures/successful-completion.json --closure 001
python3 scripts/workflow.py next --state scripts/fixtures/interrupted-recovery.json
python3 scripts/self_test.py
python3 scripts/self_test.py --dry-run
```

The tests cover dependency frontiers, malformed graphs, invalid transitions, overlapping ownership, missing evidence, interrupted recovery, guarded
closure, compact events, and successful completion.

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill coordinate-multi-ticket-run \
  -g -a codex -y
```

See the executable agent instructions in [SKILL.md](SKILL.md) and the complete assignment templates in [references/role-contracts.md](references/role-contracts.md).

[Back to all skills](../../README.md)
