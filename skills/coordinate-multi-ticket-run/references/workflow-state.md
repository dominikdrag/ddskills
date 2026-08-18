# Workflow State Contract

Use this contract to create and maintain the normalized run state consumed by `scripts/workflow.py`. Repository tickets, worklogs, notes, commits,
and evidence remain source artifacts. The state file records their orchestration projection; it does not rewrite repository files.

## Files

Place `run.json` and its compact `events.jsonl` beside the ticket evidence. Keep them outside the worktree or verify that the repository ignores them.
Only the run coordinator or active ticket coordinator may edit `run.json`; leaves report changes to their coordinator.

The state root contains:

- `schemaVersion`: `1`.
- `runId`: stable identifier for this run.
- `eventLog`: path relative to `run.json`, normally `events.jsonl`.
- `tickets`: normalized dependency graph.
- `assignments`: active-assignment ledger.
- `evidence`: ticket-keyed closure evidence.

Every ticket records `id`, optional integer `order`, `blockers`, internal `phase`, and the repository's exact `repositoryStatus`. `order` expresses an
approved priority override; otherwise the engine uses natural ticket-id order.

## Ticket phases

```text
queued -> coordinating -> acceptance -> ready_to_close -> closed
               ^               |
               +----- gap <----+

queued | coordinating | acceptance | gap -> blocked
blocked -> queued | coordinating
```

`closed` is terminal. A `ready_to_close -> closed` transition is rejected until every deterministic closure gate passes, and later validation rejects
any closed ticket whose proof becomes missing or invalid. Mark an active ticket as interrupted instead of changing its phase; the next action will
contain a recovered-state summary for a fresh coordinator. After ledger takeover and artifact reconciliation, that coordinator runs `resume`; the
command verifies sole live ownership, clears the interruption marker, and records a `recovered` event.

## Assignment ledger

Each assignment records:

```json
{
  "agent": "/root/ticket_027/worker",
  "role": "worker",
  "ticket": "027",
  "deliverable": "Implement the duration projection",
  "ownership": [{"kind": "path", "value": "Sources/Duration"}],
  "dependsOn": [],
  "recipient": "/root/ticket_027",
  "status": "active"
}
```

Valid statuses are `pending`, `active`, `done`, and `blocked`. Live path ownership overlaps on equal or ancestor/descendant paths; seam ownership
overlaps on equal values. Add or update the ledger, run `validate`, and only then spawn the assignment. Leaves never edit the ledger.

## Closure evidence

For each ticket, record:

- `criteria`: every checked criterion with a named `observation` and `location`.
- `checks`: required commands with `exitCode`, raw-log `location`, and positive `executedTests` when `requiresExecutedTests` is true.
- `snapshots`: when required, `recorded`, `inspected`, `compared`, `clean`, and `location`.
- `runtime`: when required, `complete`, `binary`, `scenario`, `device`, owned-lane proof, and `location`.
- `appleLane`: when required, `released`.
- `scope`: `reviewed` and whether it contains `unrelatedChanges`.
- `notes`: `reviewed` and any `materialOmissions`.
- `actions`: required bookkeeping or external actions with `authorized` and `performed` facts.
- `unauthorizedActions`: normally empty.

All assignments for the ticket must be `done`. The engine also rejects malformed graphs, missing blockers, cycles, multiple active tickets, invalid
dependencies, and overlapping live ownership.

See `scripts/fixtures/successful-completion.json` for the complete shape. Fixtures are examples only; do not copy their evidence claims into a run.

## Commands

Resolve the script from the selected skill directory:

```sh
python3 <skill-dir>/scripts/workflow.py validate --state <evidence>/run.json
python3 <skill-dir>/scripts/workflow.py next --state <evidence>/run.json
python3 <skill-dir>/scripts/workflow.py recover --state <evidence>/run.json --ticket 027
python3 <skill-dir>/scripts/workflow.py resume --state <evidence>/run.json --ticket 027 --actor /root/ticket_027_recovery
python3 <skill-dir>/scripts/workflow.py transition --state <evidence>/run.json --ticket 027 --to coordinating --actor /root --repository-status 3-in-progress
python3 <skill-dir>/scripts/workflow.py interrupt --state <evidence>/run.json --ticket 027 --actor /root --reason "coordinator stopped"
```

Commands emit one compact JSON object. Plain `validate` checks structure and explicitly returns `closureChecked: false`; pass `--closure <ticket>` to
audit closure. Invalid validation returns exit `2`. A rejected mutating command, including `ready_to_close -> closed` or an invalid recovery claim,
returns exit `3` without changing state or writing an event. `next` returns exit `0` for every valid routing outcome, including `reject_closure`;
callers must route on its `action`. `resume` requires the actor to be the sole pending or active ticket coordinator after ledger takeover. Mutating
commands atomically replace `run.json` and append a sequenced event to the JSONL log.

Use `--pretty` before the subcommand only for human inspection. Keep compact output for agent routing and persisted evidence.
