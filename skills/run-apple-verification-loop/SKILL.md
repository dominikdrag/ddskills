---
name: run-apple-verification-loop
description: >-
  Run proportional Apple-platform verification for Xcode, Tuist, tests, snapshots, and runtime QA. Reuse the repository's normal destination and
  existing DerivedData by default; keep tests serial unless parallelism is explicitly justified; reserve an exact isolated device lane from a
  bounded shared pool only when contention, device-specific behavior, runtime evidence, or an explicit request makes it necessary.
---

# Run Apple Verification Loop

Start with the smallest, least stateful verification that can prove the claim. Escalate to an isolated lane only when the verification actually
needs exact resource ownership or reproducible device evidence.

## 1. Read the repository contract

Reuse the repository contract and the routed rules relevant to the requested check. Repository commands, review activation and stopping limits override generic examples here. Ordinary focused checks can use the repository commands without loading this full workflow. Use host-required runners with prepared commands; do not expand the verification scope merely to delegate it.

Do not run Tuist generation merely because verification started. Reuse the existing project or workspace unless it is missing, stale, or the
repository contract requires regeneration. If generation is necessary, remember that it mutates the checkout and serialize it only when another
process is actually using the same checkout.

## 2. Use the lightweight path by default

For an ordinary compile, unit-test, or targeted integration-test check:

- Run the repository's smallest relevant verification command unchanged when possible.
- Derive test scope from the changed behavior, files, and dependency surface. Prefer the smallest test case, suite, filter, or test target that
  exercises the change and its plausible regressions.
- Do not run every test target or the full test plan by default. Broaden beyond related tests only when the change crosses shared or module
  boundaries, a targeted failure suggests wider impact, the repository or release gate requires it, or the user explicitly asks for broader testing.
- Reuse the normal Xcode DerivedData location or an established compatible cache. Evidence and cache paths serve different purposes: fresh task logs do not require a fresh cache. Follow the repository's raw-log requirements and command options; add a result bundle only when useful to the claim.
- Do not clean or delete existing DerivedData as part of routine verification.
- Do not discover, boot, reserve, or pin a simulator merely because the command uses Xcode. Let the repository command or Xcode use its established
  destination.
- Do not add a simulator UUID, device model, or OS version unless the command cannot run without one or the claim depends on that target. If a
  destination becomes necessary, choose the least specific suitable destination first; selecting a destination does not by itself require fresh
  DerivedData or a persistent evidence directory.
- Confirm the command's exit status and, for tests, that the intended tests actually executed using terminal output or an existing result bundle.
- Keep simulator testing serial by default. Pass `-parallel-testing-enabled NO` to a composed `xcodebuild` test command unless the user or a
  repository-specific gate explicitly opts into parallel workers and accepts temporary XCTest clones.
- For composed `xcodebuild test` or `test-without-building` commands, default to `-collect-test-diagnostics never` to avoid unneeded collection. Request supported diagnostics explicitly when investigating a failure; check the selected Xcode's help for accepted values. Prefer the repository wrapper's option and do not add the flag twice. Do not assume a fixed collection delay without measurement.
- Combine related test targets in one invocation when an existing umbrella scheme supports their scope. Do not introduce a new scheme or broaden coverage merely to reduce command count.

Avoid hypothetical isolation. Multiple repositories, worktrees, or agents on the machine are not alone a reason to create a lane; there must be an
actual overlapping resource, observed collision, or verification requirement that shared state cannot satisfy.

## 3. Decide whether an isolated lane is necessary

Escalate before running the affected gate when any of these applies:

- The user or repository contract explicitly requires an exact device, isolated DerivedData, persistent raw evidence, or a clean-room result.
- Verification targets a physical device, direct install or launch, Device Hub, interactive runtime behavior, or device-state persistence.
- Snapshot recording, rendered comparison, or visual QA depends on a stable model, OS, scale, or exact runtime destination.
- The failure or acceptance criterion is specific to a simulator model, OS version, architecture, or device identity.
- Another active verification is actually contending for the same checkout, workspace, destination, Device Hub window, or build data, and the work
  cannot be safely serialized or allowed to reuse that state.
- Release-grade provenance requires raw logs and an exact reproducible destination, and ordinary cached verification would not support the claim.

State the concrete reason for escalation. Do not create an isolated lane as a precaution when the lightweight path can prove the result.

## 4. Reserve an exact lane only after escalation

Resolve `SKILL_DIR` to the directory containing the loaded `SKILL.md`, including when it is a repository-local copy. Do not assume a particular global installation path. Reuse a valid reservation supplied by the parent instead of reserving the same resources again.

List the selected Xcode's structured device inventory and current leases:

```sh
python3 "$SKILL_DIR/scripts/lane.py" list
```

The inventory labels simulators as `pooled` or `outside-pool`. Configure the machine once with at most three existing simulators; this command does
not create devices:

```sh
python3 "$SKILL_DIR/scripts/lane.py" pool \
  --device-id '<existing-simulator-uuid>' \
  --device-id '<existing-simulator-uuid>' \
  --device-id '<existing-simulator-uuid>'
```

Choose an exact pooled CoreDevice UUID; never substitute a display name. Simulator reservations outside the configured pool fail closed. Physical
devices remain eligible without entering the simulator pool; their lease separately records the hardware UDID as the Xcode destination ID.

Reserve the device, workspace, DerivedData, and evidence paths with a stable owner such as the Codex task ID:

```sh
python3 "$SKILL_DIR/scripts/lane.py" reserve \
  --owner '<task-id>' \
  --task '<ticket-or-slice>' \
  --role test \
  --device-id '<exact-CoreDevice-UUID>' \
  --repo "$PWD" \
  --workspace "$PWD/<App>.xcworkspace" \
  --derived-data '<owned-compatible-cache>' \
  --evidence "$PWD/<evidence-dir>"
```

Add `--device-hub-window '<collision-resistant-label>'` only when the lane will interact with Device Hub. The label coordinates ownership; it does
not prove an actual window, identifier, or state.

The machine-global registry is `~/.codex/state/apple-verification-lanes`, shared by every agent on the machine regardless of where the skill is installed. Set `CODEX_APPLE_LANE_STATE` only for isolated registry tests. If a
reservation collides, stop and coordinate. Never steal a lease, kill a foreign process, retarget a foreign device, or use another lane's resources.

Save a lane manifest only when persistent evidence is required:

```sh
python3 "$SKILL_DIR/scripts/lane.py" status \
  --device-id '<exact-CoreDevice-UUID>' --json | tee '<evidence-dir>/lane-manifest.json'
```

## 5. Run guarded commands in an isolated lane

Read the exact destination from the lease and run `xcodebuild` through the guard:

```sh
device_uuid='<exact-CoreDevice-UUID>'
evidence='<evidence-dir>'
destination="$(python3 "$SKILL_DIR/scripts/lane.py" status \
  --device-id "$device_uuid" --json | jq -r '.xcodeDestination')"

python3 "$SKILL_DIR/scripts/lane.py" run-xcodebuild \
  --owner '<task-id>' \
  --device-id "$device_uuid" \
  --log "$evidence/<scheme>.raw.log" \
  --require-executed-tests \
  -- xcodebuild test \
    -workspace '<App>.xcworkspace' \
    -scheme '<scheme>' \
    -destination "$destination" \
    -derivedDataPath '<cache-path-from-lease>' -collect-test-diagnostics never
```

Omit `--require-executed-tests` for a compile-only command. The guard accepts only the exact leased workspace, destination, DerivedData, and evidence
paths. Treat the underlying exit code and raw output as authoritative.

The guard adds `-parallel-testing-enabled NO` when a test command omits it. Use `--allow-parallel-testing` only for a deliberate exception whose
worker count and clone cost are understood; it is not a routine speed toggle.

Use the same lease guard for supported direct operations:

```sh
python3 "$SKILL_DIR/scripts/lane.py" run-devicectl \
  --owner '<task-id>' \
  --device-id "$device_uuid" \
  --log "$evidence/install.raw.log" \
  -- xcrun devicectl device install app \
    --device "$device_uuid" '<exact-App.app>' \
    --json-output "$evidence/install.json"

python3 "$SKILL_DIR/scripts/lane.py" run-devicectl \
  --owner '<task-id>' \
  --device-id "$device_uuid" \
  --log "$evidence/launch.raw.log" \
  -- xcrun devicectl device process launch \
    --device "$device_uuid" --terminate-existing '<bundle-id>' \
    --json-output "$evidence/launch.json"
```

A successful structured result proves that operation only. It does not prove visible app state, interaction behavior, persistence, or StoreKit
configuration. A direct launch does not attach an Xcode Run scheme's StoreKit configuration.

Direct install and launch need a booted simulator, and `devicectl` cannot boot or shut one down. For that step only, use
`xcrun simctl boot "$device_uuid"`, `xcrun simctl bootstatus "$device_uuid" -b`, and `xcrun simctl shutdown "$device_uuid"`; a simulator's
CoreDevice UUID is its UDID. Never boot or shut down a simulator this task has not leased, because another session may be using it. Use `devicectl`
for every other device operation, and drop this exception once the selected Xcode's `xcrun devicectl device --help` lists boot and shutdown.

## 6. Verify interactive and visual claims proportionally

Read [references/live-smoke.md](references/live-smoke.md) before Device Hub interaction or runtime UI evidence. Device Hub and Computer Use are
required only for claims about visible Device Hub state, destination-picker changes, and user-visible runtime behavior.

Read [references/evidence-contract.md](references/evidence-contract.md) when an isolated lane, snapshot, Device Hub, or runtime evidence is in scope.
For a repository-native snapshot gate whose output does not depend on a fixed destination, keep the lightweight path and existing DerivedData. For existing baselines, compare the requested filters. For an intentional baseline change:

1. Record only the affected filters using the required destination.
2. Inspect every changed image at rendered size.
3. Rerun those filters with recording disabled and confirm the tests executed.

Set `SNAPSHOT_ARTIFACTS` for swift-snapshot-testing (as `TEST_RUNNER_SNAPSHOT_ARTIFACTS` under `xcodebuild`) so newly rendered failure images
land in the evidence directory instead of the simulator's private tmp folder, and export the reference, failure, and difference attachments with
`xcrun xcresulttool export attachments --path <xcresult> --output-path <dir> --only-failures` instead of opening the bundle by hand. A repository
wrapper may already do both and write a report; read that report before the raw log.

If Computer Use cannot fetch fresh Device Hub state, record interactive QA as blocked. Continue independent automated gates when their evidence is
still valid; do not promote those results into UI, physical-device, or runtime claims.

## 7. Review and release

Before declaring success, inspect the scoped diff and dirty worktree, confirm intended tests executed, and report the exact verification boundary.
Reject partial, stale, wrong-binary, wrong-scenario, or wrong-device evidence.

Release reservations created by this task on success, failure or interruption. A parent-supplied reservation remains owned by the parent; return resource status instead of releasing it:

```sh
python3 "$SKILL_DIR/scripts/lane.py" release \
  --owner '<task-id>' --device-id '<exact-CoreDevice-UUID>'
```

Then explicitly report that the owned Apple verification resources are released. Do not claim or release a lane when the lightweight path was used.

After the last lease is released, the guard runs maintenance at most once every seven days. It removes only shutdown `Clone N of …` directories
under `~/Library/Developer/XCTestDevices` that are older than seven days, and skips cleanup while another lease or host test process is active. To
inspect or run the same maintenance manually:

```sh
python3 "$SKILL_DIR/scripts/lane.py" prune-xctest-devices --older-than-days 7
python3 "$SKILL_DIR/scripts/lane.py" prune-xctest-devices --older-than-days 7 --apply
```

The first command is a dry run. The cleanup does not invoke the legacy simulator CLI, does not touch ordinary CoreSimulator devices, and ignores
non-clone XCTest device directories.
