---
name: run-apple-verification-loop
description: >-
  Reserve and run isolated Apple-platform verification lanes across concurrent repositories or worktrees. Use for xcodebuild, Tuist,
  simulated-device, physical-device, Device Hub, Computer Use-driven UI testing, Playbook snapshot, or runtime QA work that needs exact device
  ownership, isolated DerivedData and evidence, guarded destinations, raw logs, record-inspect-compare, and explicit lane handoff.
---

# Run Apple Verification Loop

Use resource ownership instead of global serialization. Separate projects may verify at the same time when every lane owns distinct resources.
Serialize only resources that overlap.

## 1. Read the repository contract

Load the repository's `AGENTS.md` and routed testing, workflow, and agent-QA rules. Repository commands and snapshot gates override generic examples
here.

Do not start Tuist, Xcode, Device Hub, or runtime work until the lane is reserved. Tuist generation mutates a checkout, so keep it inside the
checkout's exclusive lane.

## 2. Discover and reserve an exact device

List the iOS devices known to the selected Xcode and the current leases:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py list
```

The helper uses structured `xcrun devicectl list devices` output and has no alternate discovery path. It labels each result `simulator` or
`physical`. Treat its boot and connection fields as reported inventory only, not fresh readiness proof.

Choose the exact CoreDevice identifier UUID. A simulator normally uses that UUID as its Xcode destination ID. A physical device can have a
different hardware UDID for Xcode; the lease manifest records both and builds the exact `xcodeDestination`. Never substitute a display name.

Prefer separate test and runtime-QA devices. Use a dedicated canonical simulator for snapshots when the repository requires one. Reserve with a
stable owner such as the Codex task ID:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py reserve \
  --owner '<task-id>' \
  --task '<ticket-or-slice>' \
  --role test \
  --device-id '<exact-CoreDevice-UUID>' \
  --repo "$PWD" \
  --workspace "$PWD/<App>.xcworkspace" \
  --derived-data "$PWD/<evidence-dir>/DerivedData" \
  --evidence "$PWD/<evidence-dir>" \
  --device-hub-window '<repo-or-task>-test'
```

Reservation rechecks the UUID through `devicectl` and fails if the exact iOS device is absent, ambiguous, or has incomplete identity data. The
Device Hub window value is a collision-resistant coordination label, not device proof.

The machine-global registry is `~/.codex/state/apple-verification-lanes`. Set `CODEX_APPLE_LANE_STATE` only for isolated registry tests. If a
reservation collides, stop and coordinate. Never steal a lease, kill a foreign process, retarget a foreign device, or use another lane's Device Hub
window.

Save the manifest with the evidence and announce the repo/task, CoreDevice UUID, device kind, Xcode destination, workspace, DerivedData, Device Hub
window, and evidence directory:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py status \
  --device-id '<exact-CoreDevice-UUID>' --json | tee '<evidence-dir>/lane-manifest.json'
```

## 3. Confirm Device Hub before destination work

Device Hub is the required UI authority for boot or connection state, Xcode destination changes, and runtime UI ownership. Target the installed app
through Computer Use as `com.apple.dt.Devices`. `devicectl` can report cached/best-available state and supports selected operations, but the installed
command surface does not provide simulator boot/start control.

Use `$computer-use` to fetch fresh accessibility state before every action. In the owned Device Hub window, verify an exact identifier from the
lease manifest, perform any needed boot or device-preparation action, then fetch fresh state again. Generic labels such as `iPhone 17 Pro` are not proof.
Prefer accessibility-element actions; use screenshots when accessibility data is incomplete or the claim is visual. Never reuse stale element
indices.

Only after fresh Device Hub state shows an exact identifier from the lease and the required state, record the destination confirmation:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py confirm-device-hub \
  --owner '<task-id>' \
  --device-id '<exact-CoreDevice-UUID>' \
  --device-hub-window '<repo-or-task>-test' \
  --purpose destination \
  --observed-device-id '<exact-visible-UUID-or-hardware-UDID>' \
  --observed-state '<exact-visible-state>'
```

Reconfirm after every Xcode destination-picker change. If Computer Use cannot read the exact window, identifier, or current state, stop. Do not infer
them from a screenshot, display name, or `devicectl`'s reported state.

## 4. Generate and run focused gates

Regenerate only when the repository contract requires it. Do not generate while another lane owns the same workspace.

Start with the smallest relevant scheme. Read the guarded destination from the lease and run `xcodebuild` through the helper. It rechecks live
`devicectl` identity, requires the Device Hub destination confirmation, rejects names and partial IDs, and enforces the exact workspace and isolated
DerivedData:

```sh
device_uuid='<exact-CoreDevice-UUID>'
evidence='<evidence-dir>'
destination="$(python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py status \
  --device-id "$device_uuid" --json | jq -r '.xcodeDestination')"

python3 ~/.codex/skills/run-apple-verification-loop/scripts/run_gate.py \
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

Treat the underlying exit code and raw output as authoritative. A formatter summary, an exit-zero skipped gate, or a zero-test run is not proof.
Broaden verification only when the changed contract crosses boundaries.

## 5. Install, launch, and inspect runtime UI

Before runtime work, repeat the fresh Computer Use check and record a `runtime` Device Hub confirmation. Use the same confirmation command as above
with `--purpose runtime`.

For supported direct operations, use the guard so the exact leased CoreDevice UUID and structured evidence path cannot be replaced by a name:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/run_device.py \
  --owner '<task-id>' \
  --device-id "$device_uuid" \
  --log "$evidence/install.raw.log" \
  -- xcrun devicectl device install app \
    --device "$device_uuid" '<exact-App.app>' \
    --json-output "$evidence/install.json"

python3 ~/.codex/skills/run-apple-verification-loop/scripts/run_device.py \
  --owner '<task-id>' \
  --device-id "$device_uuid" \
  --log "$evidence/launch.raw.log" \
  -- xcrun devicectl device process launch \
    --device "$device_uuid" --terminate-existing '<bundle-id>' \
    --json-output "$evidence/launch.json"
```

The helper permits only those installed-command shapes, preserves raw output and exit status, and requires successful structured JSON. A direct
launch does not attach an Xcode scheme's StoreKit configuration; use the configured Xcode Run scheme for StoreKit behavior.

Keep Computer Use scoped to the owned Device Hub window, leased device, exact binary, and named scenario. Follow the Computer Use confirmation
policy; lane ownership does not authorize unrelated or consequential UI actions. Fetch fresh state after each action before deciding the next one.

## 6. Verify snapshots and runtime evidence

For snapshot changes, keep the phases distinct:

1. Record the narrow filter on the owned canonical device.
2. Inspect every changed image at rendered size.
3. Rerun the same filter with recording disabled and confirm the test executed.

If a repository helper hardcodes a display name, shared DerivedData, or another device, do not use it concurrently. Prefer an existing exact-lane
option; otherwise run the equivalent guarded command or deliberately fix the helper in scope.

Read [references/evidence-contract.md](references/evidence-contract.md) whenever snapshots or Device Hub evidence are in scope. Keep Playbook and
production callback claims separate.

## 7. Review and release

Before declaring success:

- inspect the scoped diff and dirty worktree;
- confirm each intended test executed with nonzero count;
- distinguish intentional record failures from clean comparison results;
- reject empty, loading, partial, wrong-scenario, wrong-binary, or wrong-device evidence;
- record blockers instead of fabricating proof.

Release every owned lane, including failed lanes:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py release \
  --owner '<task-id>' --device-id '<exact-CoreDevice-UUID>'
```

Then explicitly tell collaborators the Xcode and Device Hub resources are released.
