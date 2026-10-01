# Apple Verification Evidence Contract

Read this when the repository, the user, or a release requires persistent evidence, or when a snapshot or runtime UI result is in scope. Ordinary
repository-native build, test, and deterministic snapshot checks need no evidence folder, result bundle, or fresh DerivedData.

## Authority boundaries

| Source | What it can prove | What it cannot prove |
| --- | --- | --- |
| Claim record (`claim --json`, or `list --mine --json` with your `--label`, from `$manage-apple-simulators`) | Which device this task owns: UDID, destination, model, OS, runtime build, owner, expiry | That the device is ready now, command success, or UI state |
| Structured `xcrun devicectl list devices` result | The device inventory and identity seen by the selected Xcode | Readiness, visible UI, app behavior, or test success |
| Raw `xcodebuild` log and its exit code | The command that ran, its destination, scheme, and build or test result | Visible Device Hub state or user-visible behavior |
| `check_test_log.py` result | That tests executed with a nonzero count, and how many failed, crashed, or were skipped | Correct pixels, interaction behavior, or persistence beyond the tests |
| Successful `devicectl` JSON result (`--json-output`) | That the install, launch, or screenshot on that UDID succeeded | App UI state, StoreKit scheme attachment, or downstream behavior |
| Fresh Computer Use state | The visible state of your own Device Hub window or app, and the device identifier shown there | Source revision, binary provenance, command success, or persistence from one static observation |

Use only the sources the reported result needs. Build, test, snapshot, install, and launch results need no Device Hub observation; interactive
Device Hub and runtime UI results do.

## Metadata for persistent evidence

- Repository, checkout path, and source revision when binary provenance matters
- Selected Xcode (`xcodebuild -version`) when tool provenance matters
- Workspace and scheme
- The claim record: UDID, destination, model, OS, and runtime build
- DerivedData path when the requirement names one
- Raw logs, exit codes, and `check_test_log.py` output for each gate

## Automated gates

- Keep the raw output and the real exit code of every gate.
- Target only your claimed UDID, by ID.
- Run `check_test_log.py` on every test log and keep its output.
- Keep the successful JSON result of each `devicectl` install, launch, or screenshot.
- Run the smallest relevant gate first, then broaden in proportion to risk.
- Keep automated results within their own boundary; they do not prove Device Hub, physical-device, or interactive runtime behavior.

## Snapshot gates

Claim the model and OS the repository pins (add `--runtime-build` when the references were recorded on one build) and keep the repository's
normal DerivedData. A snapshot run alone needs no persistent raw log. For each changed filter, keep:

1. Record-mode output with the expected write count.
2. A list of every changed reference image, each inspected at rendered size.
3. Notes for intentional visual changes and rejected output.
4. Record-off output proving the same tests executed and passed.

When persistent evidence is required, also keep the raw logs and the claim record.

A recording is accepted only after inspection, never because files were written. Reject loading, blank, clipped, dependency-invalid,
wrong-scenario, wrong-device, or stale-binary images.

## Interactive runtime evidence

Store a short case table:

| Case | Setup | Action | Expected | Observed | Evidence | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `<id>` | Exact scenario, binary, device, and state | Control activated by ID | User-visible downstream result | Fresh accessibility and visual observation | Raw command evidence plus before and after UI observations | PASS/FAIL/BLOCKED |

Use Device Hub only in your own window, showing your own claimed device; follow `references/device-hub.md` in `$manage-apple-simulators`.
Fetch fresh state before and after each action, and check the device identifier before acting. For screenshots that need no interaction, use
`xcrun devicectl device capture screenshot --device <udid> --destination <file.png>`. Use screenshots only for results they can support: a static
image does not establish device identity, platform behavior, or persistence.

## Stop conditions

Stop the affected automated gate when:

- the claim is missing or released, or the command targets a different device than the claim (UDID, platform, or a pinned runtime build);
- the command targets a device by name, or a device you did not claim;
- a command fails, a `devicectl` result is unsuccessful, or `check_test_log.py` reports failures, a crash, or no executed tests;
- source, workspace, generated project, or binary provenance needed for the result is stale or unknown.

Stop only the interactive check when:

- Computer Use cannot fetch fresh state for your Device Hub window, your device identifier, the app surface, or the required state;
- Device Hub shows only a generic label, or a device other than your claim;
- UI evidence is partial, loading, stale, wrong-scenario, wrong-binary, or from another agent's device;
- StoreKit behavior was launched outside the configured Xcode scheme.

An interactive blocker does not invalidate independent automated evidence. Report the boundary instead of broadening either result.
