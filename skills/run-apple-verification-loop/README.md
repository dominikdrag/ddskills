# Run Apple Verification Loop

Reserve isolated Apple-platform verification lanes and produce evidence tied to an exact repository, workspace, simulator, DerivedData path, Device Hub window, and task.

Use this skill for Tuist, Xcode, `xcodebuild`, Simulator, Device Hub, Playbook snapshots, and runtime QA when concurrent repositories or worktrees must not collide.

## Verification flow

1. Read the repository's testing and QA contract.
2. Discover simulated iOS devices and current leases.
3. Reserve the exact UDID and all related lane resources before Apple tooling starts.
4. Run focused gates through the command guard, preserving raw output and the underlying exit code.
5. Verify snapshots with record, rendered inspection, and clean comparison as separate phases.
6. Record runtime evidence with exact binary, scenario, device, action, and observation provenance.
7. Release every lane on success, failure, or interruption.

The workflow rejects name-based simulator destinations, shared DerivedData, zero-test success, stale or partial screenshots, and unreleased leases as proof.

## Bundled tools

- [`scripts/lane.py`](scripts/lane.py): atomically list, reserve, inspect, and release simulator lanes.
- [`scripts/run_gate.py`](scripts/run_gate.py): verify that an `xcodebuild` command matches the owned lane before running it.
- [`scripts/self_test.py`](scripts/self_test.py): forward-test lease collisions, ownership enforcement, isolated concurrency, and exact-command validation.
- [`references/evidence-contract.md`](references/evidence-contract.md): define the required automated, snapshot, and runtime evidence.

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill run-apple-verification-loop \
  -g -a codex -y
```

See the executable agent instructions in [SKILL.md](SKILL.md).

[Back to all skills](../../README.md)
