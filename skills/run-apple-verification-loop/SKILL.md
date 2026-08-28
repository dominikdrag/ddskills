---
name: run-apple-verification-loop
description: >-
  Run proportional Apple-platform verification for Xcode, Tuist, tests, snapshots, and runtime QA. Reuse the repository's normal destination and
  existing DerivedData by default; reserve an exact isolated device lane only when contention, device-specific behavior, runtime evidence, or an
  explicit request makes it necessary.
---

# Run Apple Verification Loop

Start with the smallest, least stateful verification that can prove the claim. Escalate to an isolated lane only when the verification actually
needs exact resource ownership or reproducible device evidence.

## 1. Read the repository contract

Load the repository's `AGENTS.md` and routed testing, workflow, and agent-QA rules. Repository commands and snapshot gates override generic examples
here.

Do not run Tuist generation merely because verification started. Reuse the existing project or workspace unless it is missing, stale, or the
repository contract requires regeneration. If generation is necessary, remember that it mutates the checkout and serialize it only when another
process is actually using the same checkout.

## 2. Use the lightweight path by default

For an ordinary compile, unit-test, or targeted integration-test check:

- Run the repository's smallest relevant verification command unchanged when possible.
- Reuse the normal Xcode DerivedData location or an already-established repository path. Do not create a task-specific evidence directory, pass a
  fresh `-derivedDataPath`, add a `-resultBundlePath`, or persist copied logs by default.
- Do not clean or delete existing DerivedData as part of routine verification.
- Do not discover, boot, reserve, or pin a simulator merely because the command uses Xcode. Let the repository command or Xcode use its established
  destination.
- Do not add a simulator UUID, device model, or OS version unless the command cannot run without one or the claim depends on that target. If a
  destination becomes necessary, choose the least specific suitable destination first; selecting a destination does not by itself require fresh
  DerivedData or a persistent evidence directory.
- Confirm the command's exit status and, for tests, that the intended tests actually executed using terminal output or an existing result bundle.

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

List the selected Xcode's structured device inventory and current leases:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py list
```

Choose an exact CoreDevice UUID; never substitute a display name. For a physical device, the lease separately records its hardware UDID as the
Xcode destination ID.

Reserve the device, workspace, DerivedData, and evidence paths with a stable owner such as the Codex task ID:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py reserve \
  --owner '<task-id>' \
  --task '<ticket-or-slice>' \
  --role test \
  --device-id '<exact-CoreDevice-UUID>' \
  --repo "$PWD" \
  --workspace "$PWD/<App>.xcworkspace" \
  --derived-data "$PWD/<evidence-dir>/DerivedData" \
  --evidence "$PWD/<evidence-dir>"
```

Add `--device-hub-window '<collision-resistant-label>'` only when the lane will interact with Device Hub. The label coordinates ownership; it does
not prove an actual window, identifier, or state.

The machine-global registry is `~/.codex/state/apple-verification-lanes`. Set `CODEX_APPLE_LANE_STATE` only for isolated registry tests. If a
reservation collides, stop and coordinate. Never steal a lease, kill a foreign process, retarget a foreign device, or use another lane's resources.

Save a lane manifest only when persistent evidence is required:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py status \
  --device-id '<exact-CoreDevice-UUID>' --json | tee '<evidence-dir>/lane-manifest.json'
```

## 5. Run guarded commands in an isolated lane

Read the exact destination from the lease and run `xcodebuild` through the guard:

```sh
device_uuid='<exact-CoreDevice-UUID>'
evidence='<evidence-dir>'
destination="$(python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py status \
  --device-id "$device_uuid" --json | jq -r '.xcodeDestination')"

python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py run-xcodebuild \
  --owner '<task-id>' \
  --device-id "$device_uuid" \
  --log "$evidence/<scheme>.raw.log" \
  --require-executed-tests \
  -- xcodebuild test \
    -workspace '<App>.xcworkspace' \
    -scheme '<scheme>' \
    -destination "$destination" \
    -derivedDataPath "$evidence/DerivedData"
```

Omit `--require-executed-tests` for a compile-only command. The guard accepts only the exact leased workspace, destination, DerivedData, and evidence
paths. Treat the underlying exit code and raw output as authoritative.

Use the same lease guard for supported direct operations:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py run-devicectl \
  --owner '<task-id>' \
  --device-id "$device_uuid" \
  --log "$evidence/install.raw.log" \
  -- xcrun devicectl device install app \
    --device "$device_uuid" '<exact-App.app>' \
    --json-output "$evidence/install.json"

python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py run-devicectl \
  --owner '<task-id>' \
  --device-id "$device_uuid" \
  --log "$evidence/launch.raw.log" \
  -- xcrun devicectl device process launch \
    --device "$device_uuid" --terminate-existing '<bundle-id>' \
    --json-output "$evidence/launch.json"
```

A successful structured result proves that operation only. It does not prove visible app state, interaction behavior, persistence, or StoreKit
configuration. A direct launch does not attach an Xcode Run scheme's StoreKit configuration.

## 6. Verify interactive and visual claims proportionally

Read [references/live-smoke.md](references/live-smoke.md) before Device Hub interaction or runtime UI evidence. Device Hub and Computer Use are
required only for claims about visible Device Hub state, destination-picker changes, and user-visible runtime behavior.

Read [references/evidence-contract.md](references/evidence-contract.md) when an isolated lane, snapshot, Device Hub, or runtime evidence is in scope.
For a repository-native snapshot gate whose output does not depend on a fixed destination, keep the lightweight path and existing DerivedData. For
each snapshot filter:

1. Record with the repository's normal destination, or the owned exact device only when stable device identity is required.
2. Inspect every changed image at rendered size.
3. Rerun the same filter with recording disabled and confirm the test executed.

If Computer Use cannot fetch fresh Device Hub state, record interactive QA as blocked. Continue independent automated gates when their evidence is
still valid; do not promote those results into UI, physical-device, or runtime claims.

## 7. Review and release

Before declaring success, inspect the scoped diff and dirty worktree, confirm intended tests executed, and report the exact verification boundary.
Reject partial, stale, wrong-binary, wrong-scenario, or wrong-device evidence.

If and only if a lane was reserved, release it on success, failure, or interruption:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py release \
  --owner '<task-id>' --device-id '<exact-CoreDevice-UUID>'
```

Then explicitly report that the owned Apple verification resources are released. Do not claim or release a lane when the lightweight path was used.
