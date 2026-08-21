# Run Apple Verification Loop

Reserve isolated Apple-platform verification lanes and produce evidence tied to an exact repository, workspace, device, DerivedData path, and task.

Use this skill for Tuist, Xcode, `xcodebuild`, simulators, physical devices, Device Hub, snapshots, and runtime QA when concurrent repositories or
worktrees must not collide.

## Verification flow

1. Read the repository's testing and QA contract.
2. Discover structured `devicectl` inventory with physical and simulated devices clearly labelled.
3. Atomically reserve the exact CoreDevice UUID and task-specific paths.
4. Run automated Xcode and supported direct-device commands through the lease guard.
5. Use fresh Device Hub and Computer Use state only for interactive UI claims that require it.
6. Verify snapshots with record, rendered inspection, and clean comparison as separate phases.
7. Release every lane on success, failure, or interruption.

The deterministic kernel rejects absent devices, lease collisions, name-based or partial destinations, shared DerivedData, unsupported direct-device
operations, unsuccessful structured results, and zero-test success. UI evidence remains a separate observation boundary rather than a value an agent
can type into a manifest.

## Bundled resources

- [`scripts/lane.py`](scripts/lane.py): discover devices; reserve, inspect, and release lanes; guard exact `xcodebuild` and supported `devicectl`
  commands.
- [`scripts/self_test.py`](scripts/self_test.py): forward-test identity, collisions, physical/simulated destinations, command guards, structured
  results, and regression checks.
- [`references/evidence-contract.md`](references/evidence-contract.md): define automated, snapshot, and interactive evidence boundaries.
- [`references/live-smoke.md`](references/live-smoke.md): verify current Device Hub and Computer Use compatibility before interactive QA.

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill run-apple-verification-loop \
  -g -a codex -y
```

See the executable agent instructions in [SKILL.md](SKILL.md).

[Back to all skills](../../README.md)
