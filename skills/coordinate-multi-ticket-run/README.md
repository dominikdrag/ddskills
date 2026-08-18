# Coordinate Multi-Ticket Run

Coordinate an approved dependency-ordered ticket graph from its current frontier to evidence-backed completion. Codex handles semantic decisions and
delegation while `scripts/workflow.py` validates graph scheduling, assignment ownership, phase transitions, closure gates, and recovery.

Agent instructions live in [SKILL.md](SKILL.md). Load detailed references only when their branch is active:

- [workflow state](references/workflow-state.md) for state shape and commands;
- [role policy](references/role-policy.md) and [ticket coordinator](references/ticket-coordinator.md) for the active ticket;
- [leaf agents](references/leaf-agents.md) when bounded delegation is useful;
- [acceptance checker](references/acceptance-checker.md) at the closure gate;
- [recovery](references/recovery.md) after interruption.

## Verify

```sh
python3 scripts/workflow.py validate --state scripts/fixtures/successful-completion.json --closure 001
python3 scripts/workflow.py next --state scripts/fixtures/interrupted-recovery.json
python3 scripts/self_test.py
python3 scripts/self_test.py --dry-run
```

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill coordinate-multi-ticket-run \
  -g -a codex -y
```

[Back to all skills](../../README.md)
