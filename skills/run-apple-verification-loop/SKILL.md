---
name: run-apple-verification-loop
description: >-
  Verify Apple-platform changes proportionally and prove the tests actually ran. Use when building or testing an Apple app with Xcode, Tuist, or
  xcodebuild; when recording or checking snapshot tests; or when checking app behavior on a simulator, a physical device, or in Device Hub.
  Gets its devices from $manage-apple-simulators.
---

# Run Apple Verification Loop

Prove each change with the smallest, least stateful check that supports what you report. This skill decides what to build and test and how to prove it;
`$manage-apple-simulators` provides the device.

Resolve `SKILL_DIR` to the directory containing the loaded `SKILL.md`, including when it is a repository-local copy.

## 1. Read the repository contract

Read the repository's testing and QA rules. Its wrappers, commands, review limits, and stopping rules override the examples here. Reuse the existing
project or workspace. Run Tuist generation only when the project is missing or stale, or the repository requires it; generation rewrites the
checkout, so wait while another process builds in it. Before claiming a device, check that the workspace can build: the projects and dependencies
it references exist (for Tuist, `Tuist/.build` from `tuist install`). If they are missing and you may not install or generate, report the check
blocked without claiming.

Done when you know the repository's command for the check and the evidence it requires, and the workspace is ready to build.

## 2. Pick the smallest scope

- Derive the scope from the changed behavior, files, and dependency surface: the smallest test case, suite, filter, or target that exercises the
  change and its plausible regressions.
- Broaden only when the change crosses shared or module boundaries, a targeted failure suggests wider impact, the repository or a release gate
  requires it, or the user asks.
- Run related targets in one invocation when an existing umbrella scheme covers them; keep schemes and coverage as they are.
- Add isolation (fresh DerivedData, evidence folders, a specific device model or OS) only when the result you report needs it.

Done when you can name the scheme, target, or filter and why it covers the change.

## 3. Get a device

- Build-only checks and macOS tests: no claimed device (`-destination 'generic/platform=iOS Simulator'`, or `platform=macOS`).
- Tests, snapshot tests, or the app on a simulator: claim a simulator with `$manage-apple-simulators` (pass `--worktree <repository root>`), and
  run the same `claim` again before each later test run: it returns the same simulator and refreshes its 12-hour expiry. When a parent hands
  you a claim, use it.
- A physical device: claim it by exact ID with `$manage-apple-simulators`.

Pass the claimed device to the repository command: its device-ID option (such as `--device-id <udid>`) or
`-destination "<destination printed by claim>"`. If the command accepts only a device name, claim that model and OS and pass the UDID through
the command's override. If it has no override, run the same `xcodebuild` arguments yourself with the claimed destination, and say so in the report.

Some repository wrappers also check the simulator's name (for example `--expected-device-name 'iPhone 17 Pro'`). Claimed simulators are named
`agent-sim <id> <model> <os>`, so that check fails. Keep the claimed simulator and its name: run the wrapper's `xcodebuild` arguments yourself
with the claimed destination and say so, or report the step blocked.

Done when the command you will run targets your claimed UDID, or needs no device.

## 4. Run

- Use the project's normal DerivedData or the wrapper's cache, and keep it. Clean or replace it only for an explicit clean-room requirement.
- Run tests serially: pass `-parallel-testing-enabled NO` when you compose an `xcodebuild` test command or pass extra arguments through a
  wrapper, unless the wrapper or scheme already runs tests serially. Use `-parallel-testing-enabled YES -parallel-testing-worker-count N` only
  when the user or repository asks for parallel tests.
- Pass `-collect-test-diagnostics never` to composed `xcodebuild test` and `test-without-building` commands. Request diagnostics only to
  investigate a failure (`xcodebuild -help` lists the values). Prefer the wrapper's own option, and pass it once.
- Save the raw output and keep the real exit code: `set -o pipefail` before piping through `tee <log>`.
- A locked build database means another build is using the same DerivedData: wait for it, or work in your own worktree.

## 5. Prove the tests ran

```sh
python3 "$SKILL_DIR/scripts/check_test_log.py" <raw-log>
```

Give it the raw `xcodebuild` output: the wrapper's own raw log when it writes one, not a filtered summary. It reads XCTest and Swift Testing
summaries, per-test lines from parallel runs, test-runner crashes, compile errors, and `** ... **` result markers, and prints one summary line
(`--json` for a report). Exit `0`: tests ran and none failed. `1`: a build failure, a test failure, a crash, or a failed marker. `2`: no test
ran, usually a filter that matched nothing; fix the filter and rerun. `3`: the log could not be read or the arguments were wrong.

Done when the command and the checker both exit `0` with the expected test count, or you have the failure to report.

## 6. Snapshot tests

Claim the model and OS the repository pins, plus `--runtime-build` when its reference images were recorded on one runtime build. To change a
baseline on purpose:

1. Record only the affected filters.
2. Inspect every changed image at rendered size.
3. Rerun those filters with recording off and check that the tests ran.

Set `SNAPSHOT_ARTIFACTS` (as `TEST_RUNNER_SNAPSHOT_ARTIFACTS` under `xcodebuild`) so failure images land in your evidence folder instead of the
simulator's tmp folder. Export reference, failure, and difference images with
`xcrun xcresulttool export attachments --path <xcresult> --output-path <dir> --only-failures`. A repository wrapper may do both and write a
report; read that report before the raw log.

## 7. Keep evidence

Keep evidence outside the checkout or in an ignored folder. Persistent evidence folders, result bundles, and fresh DerivedData are needed only
when the repository, the user, or a release requires them. In that case, and for snapshot or runtime UI results, read
[references/evidence-contract.md](references/evidence-contract.md).

## 8. Runtime and Device Hub QA

Install, launch, and screenshots go through `xcrun devicectl` on your claimed UDID. Before opening Device Hub, read `references/device-hub.md` in
`$manage-apple-simulators`. A direct launch proves the launch only; it does not attach an Xcode Run scheme's StoreKit configuration.

If Computer Use cannot read fresh Device Hub state, report the interactive check as blocked and keep the automated results as they are: they
support build and test results, not UI or device behavior.

## 9. Report and release

Before declaring success, review the scoped diff and the dirty worktree. Report the verification boundary: what was built, which tests ran on
which device (model, OS, runtime build), and what was not checked. Reject partial, stale, wrong-binary, wrong-scenario, or wrong-device evidence.

Release your claims through `$manage-apple-simulators` when the task ends, on success, failure, or interruption; keep them between runs. A claim
handed to you by a parent stays with the parent: report its status instead of releasing it.

Done when the report names the boundary and states that your Apple devices are released, or that none were claimed.
