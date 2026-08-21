---
name: run-apple-verification-loop
description: >-
  Reserve and run isolated Apple-platform verification lanes across concurrent repositories or worktrees. Use for xcodebuild, Tuist,
  simulated-device, physical-device, Device Hub, snapshot, or runtime QA work that needs exact device ownership, isolated DerivedData and evidence,
  guarded commands, raw logs, record-inspect-compare, and explicit lane handoff.
---

# Run Apple Verification Loop

Use deterministic guards for resource ownership and command targeting. Use judgment and fresh UI observation for claims that only Device Hub or the
running app can prove.

## 1. Read the repository contract

Load the repository's `AGENTS.md` and routed testing, workflow, and agent-QA rules. Repository commands and snapshot gates override generic examples
here.

Reserve the lane before Tuist generation, Xcode work, Device Hub interaction, or runtime work. Tuist generation mutates a checkout, so keep it inside
the checkout's exclusive lane.

## 2. Discover and reserve an exact device

List the selected Xcode's structured device inventory and current leases:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py list
```

The helper accepts only structured `xcrun devicectl list devices` output. Inventory boot and connection fields are descriptive snapshots, not fresh
readiness proof. Choose an exact CoreDevice UUID; never substitute a display name. For a physical device, the lease separately records its hardware
UDID as the Xcode destination ID.

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

Save the manifest with the task evidence:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py status \
  --device-id '<exact-CoreDevice-UUID>' --json | tee '<evidence-dir>/lane-manifest.json'
```

## 3. Run automated Xcode gates

Automated compile, test, and snapshot commands do not require a Device Hub UI read. Their authority comes from the exact lease, a live structured
identity recheck, the guarded Xcode destination, isolated DerivedData, raw output, exit status, and executed-test evidence when applicable.

Read the destination from the lease and run `xcodebuild` through the guard:

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

Omit `--require-executed-tests` for a compile-only command. The guard accepts only `xcodebuild`, the exact platform and destination ID, the leased
workspace, isolated DerivedData, and a log inside the evidence directory. Treat the underlying exit code and raw output as authoritative.

## 4. Run supported direct device operations

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

## 5. Verify interactive UI only when the claim needs it

Read [references/live-smoke.md](references/live-smoke.md) before Device Hub interaction or runtime UI evidence. Device Hub and Computer Use are
required for claims about the visible Device Hub window, exact displayed identifier/state, destination-picker changes, and user-visible runtime
behavior. They are not prerequisites for automated compile, test, or snapshot gates.

If Computer Use cannot fetch fresh Device Hub state, record interactive QA as blocked. Continue independent automated gates when their evidence is
still valid; do not promote those results into UI, physical-device, or runtime claims.

## 6. Verify snapshots and runtime evidence

Read [references/evidence-contract.md](references/evidence-contract.md) whenever snapshots, Device Hub, or runtime evidence are in scope.

For each snapshot filter:

1. Record on the owned exact device.
2. Inspect every changed image at rendered size.
3. Rerun the same filter with recording disabled and confirm the test executed.

If a repository helper hardcodes a display name, shared DerivedData, or another device, do not use it concurrently. Prefer an exact-lane option or
run the equivalent guarded command.

## 7. Review and release

Before declaring success, inspect the scoped diff and dirty worktree, confirm intended tests executed, distinguish record failures from clean
comparison results, and reject partial, stale, wrong-binary, wrong-scenario, or wrong-device evidence.

Release every owned lane on success, failure, or interruption:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py release \
  --owner '<task-id>' --device-id '<exact-CoreDevice-UUID>'
```

Then explicitly report that the owned Apple verification resources are released.
