# Run Apple Verification Loop

Reserve isolated Apple-platform verification lanes and produce evidence tied to an exact repository, workspace, simulator, DerivedData path, Device Hub window, and task.

Use this skill for Tuist, Xcode, `xcodebuild`, Simulator, Device Hub, Playbook snapshots, and runtime QA when concurrent repositories or worktrees must not collide.

## Verification flow

1. Read the repository's testing and QA contract.
2. Discover simulated iOS devices and current leases.
3. Reserve the exact UDID and all related lane resources before Apple tooling starts.
4. Run focused gates through the command guard, preserving raw output and the underlying exit code.
5. Verify snapshots with record, rendered inspection, and clean comparison as separate phases.
6. Use Computer Use to inspect and operate the exact owned UI, then record runtime evidence with binary, scenario, device, action, and observation
   provenance.
7. Release every lane on success, failure, or interruption.

The workflow rejects name-based simulator destinations, shared DerivedData, zero-test success, stale or partial screenshots, and unreleased leases as proof.

## UI interaction

Computer Use drives Device Hub and runtime app UI testing. It must stay scoped to the owned Device Hub window, leased simulator, exact binary, and
named scenario. The workflow reads fresh accessibility state before actions, prefers element-based interaction, refreshes state after actions, and
uses screenshots when accessibility data is incomplete or the claim is visual. Screenshots alone do not prove platform behavior or persistence.

Computer Use's confirmation policy still applies. Lane ownership does not grant permission for unrelated or consequential UI actions.

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
