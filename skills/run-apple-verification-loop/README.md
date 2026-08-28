# Run Apple Verification Loop

Run proportional Apple-platform verification while reusing normal build data and destinations unless exact isolation is genuinely required.

Use this skill for Tuist, Xcode, `xcodebuild`, simulators, physical devices, Device Hub, snapshots, and runtime QA. Ordinary compile and test checks
reuse the repository's normal command, destination, and DerivedData. Exact lanes are reserved only for actual contention, device-specific behavior,
runtime or visual evidence, release-grade provenance, or an explicit request.

## Verification flow

1. Read the repository's testing and QA contract.
2. Run the smallest repository-native gate with existing build data and its established destination.
3. Escalate only when the claim needs exact ownership, stable device identity, or persistent evidence.
4. If escalated, atomically reserve the exact CoreDevice UUID and task-specific paths.
5. Run isolated Xcode and supported direct-device commands through the lease guard.
6. Use fresh Device Hub and Computer Use state only for interactive UI claims that require it.
7. Release every reserved lane on success, failure, or interruption.

The deterministic kernel applies only after escalation. It rejects absent devices, lease collisions, name-based or partial destinations, shared
DerivedData, unsupported direct-device operations, unsuccessful structured results, and zero-test success. UI evidence remains a separate
observation boundary rather than a value an agent can type into a manifest.

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
