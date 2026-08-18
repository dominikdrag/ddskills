---
name: run-apple-verification-loop
description: >-
  Reserve and run isolated Apple-platform verification lanes across concurrent repositories or worktrees. Use for xcodebuild, Tuist,
  simulated-device, Device Hub, Computer Use-driven UI testing, Playbook snapshot, or runtime QA work that needs exact simulator ownership,
  isolated DerivedData and evidence, raw logs, record-inspect-compare, and explicit lane handoff.
---

# Run Apple Verification Loop

Use resource ownership instead of global serialization. Separate projects may verify at the same time when every lane owns distinct resources.
Serialize only resources that overlap.

## 1. Read the repository contract

Load the repository's `AGENTS.md` and routed testing, workflow, and agent-QA rules. Repository commands and snapshot gates override generic examples here.

Do not start Xcode or Device Hub work until the lane is reserved. Tuist generation mutates a checkout, so keep it inside the checkout's exclusive lane.

## 2. Discover and reserve exact devices

List available simulated iOS devices and current leases:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py list
```

Choose exact UDIDs. Prefer separate test and runtime-QA devices. Use a dedicated canonical device for snapshots when the repository requires one.

Use a stable owner such as the Codex task ID. Reserve before invoking Tuist, Xcode, snapshots, or Device Hub:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py reserve \
  --owner '<task-id>' \
  --task '<ticket-or-slice>' \
  --role test \
  --udid '<exact-udid>' \
  --repo "$PWD" \
  --workspace "$PWD/<App>.xcworkspace" \
  --derived-data "$PWD/<evidence-dir>/DerivedData" \
  --evidence "$PWD/<evidence-dir>" \
  --device-hub-window '<repo-or-task>-test'
```

The registry is machine-global at `~/.codex/state/apple-verification-lanes`. Set `CODEX_APPLE_LANE_STATE` only for isolated tests of the registry itself.

If a reservation collides, stop and coordinate. Never steal a lease, kill a foreign process, retarget a foreign device, or interact with another lane's Device Hub window.

Save the manifest with the task evidence:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py status \
  --udid '<exact-udid>' --json | tee '<evidence-dir>/lane-manifest.json'
```

Announce the repo/task, exact test and QA UDIDs, workspace, DerivedData, Device Hub window, and evidence directory to collaborating agents.

## 3. Generate and run focused gates

Regenerate only when the repository contract requires it. Do not generate while another lane owns the same workspace.

Start with the smallest relevant scheme. Run `xcodebuild` through the guard so the command cannot silently fall back to a name-based destination or shared DerivedData:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/run_gate.py \
  --owner '<task-id>' \
  --udid '<exact-udid>' \
  --log '<evidence-dir>/<scheme>.raw.log' \
  --require-executed-tests \
  -- xcodebuild test \
    -workspace '<App>.xcworkspace' \
    -scheme '<scheme>' \
    -destination 'platform=iOS Simulator,id=<exact-udid>' \
    -derivedDataPath '<evidence-dir>/DerivedData'
```

Treat the underlying exit code and raw output as authoritative. A formatter summary, an exit-zero skipped gate, or a zero-test run is not proof.
Broaden verification only when the changed contract crosses boundaries.

## 4. Verify snapshots and runtime behavior

For snapshot changes, keep the three phases distinct:

1. Record the narrow filter on the owned canonical device.
2. Inspect every changed image at rendered size.
3. Rerun the same filter with recording disabled and confirm the test executed.

If a repository helper hardcodes a display name, shared DerivedData, or another device, do not use it concurrently.
Prefer an existing exact-lane option; otherwise run the equivalent direct command or deliberately fix the helper in scope.

For Device Hub and runtime app UI QA, use `$computer-use` as the UI driver. The lane scripts still own resource isolation and command gating.
Follow the Computer Use confirmation policy; this skill does not expand authority to take consequential UI actions.

Before the first UI action, use Computer Use to fetch fresh accessibility state for the exact Device Hub window or app surface. Verify Device Hub
Info shows the leased UUID before launch and after every Xcode destination-picker change. Generic labels such as `iPhone 17 Pro` are not proof.
Prefer accessibility-element actions over coordinates. After each action, fetch fresh state before deciding the next action, and never reuse stale
element indices. Use screenshots when accessibility data is incomplete or the claim is visual, but never treat a screenshot alone as proof of
platform behavior or persistence.

Keep Computer Use scoped to the owned Device Hub window, leased simulator, exact binary, and named scenario. Never interact with another lane's
window or device. Stop and coordinate if Computer Use cannot verify the owned window or leased UUID. Keep Playbook and production callback claims
separate.

Read [references/evidence-contract.md](references/evidence-contract.md) whenever snapshots or Device Hub evidence are in scope.

## 5. Review and release

Before declaring success:

- inspect the scoped diff and dirty worktree;
- confirm each intended test executed with nonzero count;
- distinguish intentional record failures from clean comparison results;
- reject empty, loading, partial, wrong-scenario, wrong-binary, or wrong-device evidence;
- record blockers instead of fabricating proof.

Release every owned lane, including failed lanes:

```sh
python3 ~/.codex/skills/run-apple-verification-loop/scripts/lane.py release \
  --owner '<task-id>' --udid '<exact-udid>'
```

Then explicitly tell collaborators the Xcode and Device Hub resources are released.
