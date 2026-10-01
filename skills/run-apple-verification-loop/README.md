# Run Apple Verification Loop

Verify Apple-platform changes with the smallest check that proves the change, and prove that the tests actually ran. Use this skill for Tuist,
Xcode, `xcodebuild`, tests, snapshot tests, and runtime or Device Hub QA.

It decides what to build and test and how to prove it. Devices come from
[manage-apple-simulators](../manage-apple-simulators/README.md): each agent task claims its own fresh simulator, so several agents can test on one
Mac at the same time.

## Verification flow

1. Read the repository's testing and QA contract; its wrappers and rules win.
2. Pick the smallest test scope that covers the change and its plausible regressions.
3. Get a device: none for build-only checks; a claimed simulator, reused for the whole task, for tests, snapshots, or running the app.
4. Run with the project's normal DerivedData, serial tests, and `-collect-test-diagnostics never` by default.
5. Prove the tests ran with `check_test_log.py` on the raw log.
6. For snapshot changes, record only the affected filters, inspect every changed image, and rerun with recording off.
7. Keep persistent evidence only when the repository, the user, or a release requires it.
8. Use Device Hub only for interactive QA, in the agent's own window for its own claimed simulator.
9. Report the verification boundary and release the claim at the end of the task.

## Bundled resources

- [`scripts/check_test_log.py`](scripts/check_test_log.py): read a raw `xcodebuild` log and report whether tests executed and passed. It counts
  XCTest and Swift Testing summaries, per-test lines from parallel runs, test-runner crashes, and `** TEST FAILED **`-style markers. Exit `0`
  passed, `1` failed, `2` no executed tests, `3` unreadable log or bad arguments.
- [`scripts/self_test.py`](scripts/self_test.py): fixture tests for the checker, mostly built from real Xcode 27 log lines. Run
  `python3 skills/run-apple-verification-loop/scripts/self_test.py` from a checkout of this repository.
- [`references/evidence-contract.md`](references/evidence-contract.md): what each source of evidence can prove, snapshot and interactive evidence
  rules, and stop conditions.

## Requirements

macOS with Xcode and Python 3.9 or newer (standard library only). Tests, snapshot tests, and runtime QA need
[manage-apple-simulators](../manage-apple-simulators/README.md) installed. Device Hub and Computer Use are needed only for interactive QA.

## Install

Install both skills together:

```sh
npx skills add dominikdrag/ddskills \
  --skill run-apple-verification-loop manage-apple-simulators \
  -g -a codex -y
```

See the executable agent instructions in [SKILL.md](SKILL.md).

[Back to all skills](../../README.md)
