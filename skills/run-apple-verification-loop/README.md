# Run Apple Verification Loop

Reserve isolated Apple-platform verification lanes and produce evidence tied to an exact repository, workspace, device, DerivedData path, Device Hub window, and task.

Use this skill for Tuist, Xcode, `xcodebuild`, simulators, physical devices, Device Hub, Playbook snapshots, and runtime QA when concurrent repositories
or worktrees must not collide.

## Verification flow

1. Read the repository's testing and QA contract.
2. Discover structured `devicectl` inventory and current leases, with physical and simulated devices clearly labelled.
3. Reserve the exact CoreDevice UUID and all related lane resources before Apple tooling starts.
4. Use fresh Computer Use state in Device Hub to confirm an exact manifest identifier and visible destination/runtime state.
5. Run focused gates through the Xcode command guard, preserving raw output and the underlying exit code.
6. Run supported direct install or launch operations through the `devicectl` guard, preserving structured JSON and raw output.
7. Verify snapshots with record, rendered inspection, and clean comparison as separate phases.
8. Use Computer Use to inspect and operate the exact owned UI, then record runtime evidence with binary, scenario, device, action, and observation
   provenance.
9. Release every lane on success, failure, or interruption.

The workflow rejects devices absent from `devicectl`, missing Device Hub confirmation, name-based or partial destinations, shared DerivedData, zero-test
success, stale or partial screenshots, and unreleased leases as proof.

## UI interaction

Computer Use drives Device Hub and runtime app UI testing. It must stay scoped to the owned Device Hub window, leased device, exact binary, and named
scenario. The workflow reads fresh accessibility state before actions, prefers element-based interaction, refreshes state after actions, and uses
screenshots when accessibility data is incomplete or the claim is visual. Screenshots alone do not prove device identity, platform behavior, or
persistence.

Computer Use's confirmation policy still applies. Lane ownership does not grant permission for unrelated or consequential UI actions.

## Bundled tools

- [`scripts/lane.py`](scripts/lane.py): use structured `devicectl` inventory to atomically list, reserve, confirm Device Hub, inspect, and release lanes.
- [`scripts/run_gate.py`](scripts/run_gate.py): verify that an `xcodebuild` command matches the exact owned Xcode destination before running it.
- [`scripts/run_device.py`](scripts/run_device.py): guard exact-device `devicectl` app installation and process launch commands.
- [`scripts/self_test.py`](scripts/self_test.py): forward-test authority failures, lease collisions, physical/simulated identity, Device Hub confirmation,
  isolated concurrency, exact destinations, supported operations, and the legacy-tool regression guard.
- [`references/evidence-contract.md`](references/evidence-contract.md): define the required automated, snapshot, and runtime evidence.

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill run-apple-verification-loop \
  -g -a codex -y
```

See the executable agent instructions in [SKILL.md](SKILL.md).

[Back to all skills](../../README.md)
