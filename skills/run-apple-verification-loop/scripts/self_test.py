#!/usr/bin/env python3
"""Fixture tests for check_test_log.py.

Fixture lines come from real Xcode 27 xcodebuild logs, trimmed to the lines the
checker reads; paths and project-specific messages are removed. XCTest failures
use the real form "with N failures (0 unexpected)": assertion and snapshot
failures are not "unexpected". Lines whose real form was not available (XCTest
skips, parallel clone lines) follow the same xcodebuild formats.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CHECKER = Path(__file__).resolve().parent / "check_test_log.py"

XCTEST_ONLY = """\
Test Suite 'Selected tests' started at 2026-09-13 11:39:53.941.
Test Suite 'AppFeatureTests.xctest' started at 2026-09-13 11:39:53.945.
Test Suite 'AppRootViewModelTests' started at 2026-09-13 11:39:53.945.
Test Case '-[AppFeatureTests.AppRootViewModelTests test_onAppear_showsIntroWhenRequired]' started.
Test Case '-[AppFeatureTests.AppRootViewModelTests test_onAppear_showsIntroWhenRequired]' passed (0.001 seconds).
Test Suite 'AppRootViewModelTests' passed at 2026-09-13 11:39:53.993.
\t Executed 6 tests, with 0 failures (0 unexpected) in 0.045 (0.048) seconds
Test Suite 'IntroFlowViewModelTests' started at 2026-09-13 11:39:53.993.
Test Suite 'IntroFlowViewModelTests' passed at 2026-09-13 11:39:54.001.
\t Executed 7 tests, with 0 failures (0 unexpected) in 0.006 (0.008) seconds
Test Suite 'AppFeatureTests.xctest' passed at 2026-09-13 11:39:54.002.
\t Executed 13 tests, with 0 failures (0 unexpected) in 0.051 (0.056) seconds
Test Suite 'Selected tests' passed at 2026-09-13 11:39:54.002.
\t Executed 13 tests, with 0 failures (0 unexpected) in 0.051 (0.061) seconds

** TEST SUCCEEDED **
"""

EMPTY_XCTEST_BUNDLE = """\
Test Suite 'Selected tests' started at 2026-09-13 12:30:22.866.
Test Suite 'DatabaseTests.xctest' started at 2026-09-13 12:30:22.866.
Test Suite 'DatabaseTests.xctest' passed at 2026-09-13 12:30:22.866.
\t Executed 0 tests, with 0 failures (0 unexpected) in 0.000 (0.000) seconds
Test Suite 'Selected tests' passed at 2026-09-13 12:30:22.867.
\t Executed 0 tests, with 0 failures (0 unexpected) in 0.000 (0.001) seconds
◇ Test run started.
↳ Testing Library Version: 2084
↳ Target Platform: arm64-apple-ios17.0-simulator
"""

SWIFT_TESTING_ONLY = EMPTY_XCTEST_BUNDLE + """\
◇ Suite "DynamicFetch" started.
✔ Suite "DynamicFetch" passed after 0.311 seconds.
✔ Test run with 7 tests in 1 suite passed after 0.311 seconds.

** TEST SUCCEEDED **
"""

SWIFT_TESTING_FAILURE_BODY = EMPTY_XCTEST_BUNDLE + """\
◇ Suite "BottomConfirmSection" started.
◇ Test "summary text shows singular when count is one" started.
✔ Test "summary text shows singular when count is one" passed after 0.001 seconds.
◇ Test "accessibility label correctly pluralizes dose count" started.
◇ Test case passing 2 arguments count → 1, expectedLabel → "Confirm logging 1 dose" to "accessibility label correctly pluralizes dose count" started.
✘ Test "accessibility label correctly pluralizes dose count" recorded an issue with 2 arguments count → 1, expectedLabel → "Confirm logging 1 dose" at BottomConfirmSectionTests.swift:158:6: Caught error
✘ Suite "BottomConfirmSection" failed after 0.289 seconds with 3 issues.
✘ Test run with 10 tests in 1 suite failed after 0.290 seconds with 3 issues.
"""

SWIFT_TESTING_FAILURE = SWIFT_TESTING_FAILURE_BODY + """\

Failing tests:
\t-[BottomConfirmSectionTests accessibilityLabelPluralization(count:expectedLabel:)]

** TEST FAILED **
"""

XCTEST_FAILURE_BODY = """\
Test Suite 'Selected tests' started at 2026-09-13 11:39:53.941.
Test Case '-[AppFeatureTests.IntroFlowViewModelTests test_replay_skipRecordsNothing]' started.
Test Case '-[AppFeatureTests.IntroFlowViewModelTests test_replay_skipRecordsNothing]' failed (0.002 seconds).
Test Suite 'IntroFlowViewModelTests' failed at 2026-09-13 11:39:54.001.
\t Executed 7 tests, with 1 failure (0 unexpected) in 0.006 (0.008) seconds
Test Suite 'Selected tests' failed at 2026-09-13 11:39:54.002.
\t Executed 13 tests, with 1 failure (0 unexpected) in 0.051 (0.061) seconds
"""

XCTEST_FAILURE = XCTEST_FAILURE_BODY + "\n** TEST FAILED **\n"

XCTEST_SKIPPED = """\
Test Suite 'Selected tests' passed at 2026-09-13 11:39:54.002.
\t Executed 13 tests, with 2 tests skipped and 0 failures (0 unexpected) in 0.051 (0.061) seconds

** TEST SUCCEEDED **
"""

XCTEST_ALL_SKIPPED = """\
Test Suite 'Selected tests' passed at 2026-09-13 11:39:54.002.
\t Executed 1 test, with 1 test skipped and 0 failures (0 unexpected) in 0.000 (0.001) seconds

** TEST SUCCEEDED **
"""

PARALLEL_CLONES = """\
Test case 'AppRootViewModelTests.test_onAppear_showsIntroWhenRequired()' passed on 'Clone 1 of agent-sim 3f2a9c1d iPhone 17 Pro 27.0 - DoseWise (72588)' (0.001 seconds)
Test case 'AppRootViewModelTests.test_completeIntro_landsOnTodayWithoutMedicationHandoff()' passed on 'Clone 2 of agent-sim 3f2a9c1d iPhone 17 Pro 27.0 - DoseWise (72590)' (0.011 seconds)
Test case 'IntroFlowViewModelTests.test_replay_skipRecordsNothing()' passed on 'Clone 1 of agent-sim 3f2a9c1d iPhone 17 Pro 27.0 - DoseWise (72588)' (0.001 seconds)
Test case 'IntroFlowViewModelTests.test_replay_skipRecordsNothing()' passed on 'Clone 2 of agent-sim 3f2a9c1d iPhone 17 Pro 27.0 - DoseWise (72590)' (0.001 seconds)
Test case 'IntroFlowViewModelTests.test_skipIsOfferedEverywhereExceptSendOff()' skipped on 'Clone 2 of agent-sim 3f2a9c1d iPhone 17 Pro 27.0 - DoseWise (72590)' (0.000 seconds)

** TEST SUCCEEDED **
"""

PARALLEL_CLONES_FAILURE = """\
Test case 'AppRootViewModelTests.test_onAppear_showsIntroWhenRequired()' passed on 'Clone 1 of agent-sim 3f2a9c1d iPhone 17 Pro 27.0 - DoseWise (72588)' (0.001 seconds)
Test case 'IntroFlowViewModelTests.test_replay_skipRecordsNothing()' failed on 'Clone 2 of agent-sim 3f2a9c1d iPhone 17 Pro 27.0 - DoseWise (72590)' (0.004 seconds)

** TEST FAILED **
"""

ZERO_TESTS = EMPTY_XCTEST_BUNDLE + """\
◇ Suite "Adherence Analytics UI" started.
✔ Suite "Adherence Analytics UI" passed after 0.001 seconds.
✔ Test run with 0 tests in 1 suite passed after 0.002 seconds.

** TEST SUCCEEDED **
"""

TEST_BUILD_FAILURE = """\
Example.swift:12:14: error: missing argument for parameter 'value' in call

Testing failed:
\tMissing argument for parameter 'value' in call
\tTesting cancelled because the build failed.

** TEST FAILED **


The following build commands failed:
\tTesting workspace Example with scheme SettingsFeature
(3 failures)
"""

BUILD_FAILURE = """\
Example.swift:12:14: error: missing argument for parameter 'value' in call

** BUILD FAILED **
"""

BUILD_ERROR_ONLY = """\
/repo/Projects/App/Sources/TestExtensions/SnapshotIntegration.swift:1:19: error: Unable to resolve module dependency: \
'SnapshotTesting' (in target 'TestExtensions' from project 'App')
"""

CRASH_RESTART_BODY = EMPTY_XCTEST_BUNDLE + """\
◇ Suite "Adherence Analytics UI" started.
◇ Test "AdherenceStatsCard displays correctly with full data" started.
Swift/arm64-apple-ios-simulator.swiftinterface:3622: Fatal error: Can't unsafeBitCast between types of different sizes

Restarting after unexpected exit, crash, or test timeout; summary will include totals from previous launches.

""" + EMPTY_XCTEST_BUNDLE + """\
◇ Suite "Adherence Analytics UI" started.
✔ Test "AdherencePatternView displays different patterns correctly" passed after 0.238 seconds.
✔ Suite "Adherence Analytics UI" passed after 0.239 seconds.
✔ Test run with 1 test in 1 suite passed after 0.240 seconds.
"""

CRASH_RESTART = CRASH_RESTART_BODY + """\

Failing tests:
\tAdherenceAnalyticsTests.adherenceStatsCardFullData()

** TEST FAILED **
"""

MIXED_MANY_RUNS = """\
\t Executed 6 tests, with 0 failures (0 unexpected) in 0.038 (0.041) seconds
\t Executed 59 tests, with 0 failures (0 unexpected) in 0.351 (0.367) seconds
\t Executed 59 tests, with 0 failures (0 unexpected) in 0.351 (0.369) seconds
✘ Test run with 126 tests in 13 suites failed after 4.193 seconds with 3 issues.
\t Executed 0 tests, with 0 failures (0 unexpected) in 0.000 (0.001) seconds
✔ Test run with 29 tests in 4 suites passed after 0.266 seconds.
✔ Test run with 88 tests in 8 suites passed after 0.042 seconds.

** TEST FAILED **
"""

TWO_PASSING_RUNS = """\
\t Executed 13 tests, with 0 failures (0 unexpected) in 0.052 (0.060) seconds
✔ Test run with 22 tests in 1 suite passed after 0.104 seconds.
✔ Test run with 11 tests in 1 suite passed after 0.007 seconds.

** TEST SUCCEEDED **
"""

SWIFT_TESTING_SHORT_FORMS = """\
✔ Test run with 1 test in 1 suite passed after 0.019 seconds.
✔ Test run with 5 tests passed after 0.002 seconds.
✔ Test run with 3 tests in 2 suites passed after 0.001 seconds with 1 known issue.
"""

TEST_EXECUTE_FAILURE = """\
\t Executed 13 tests, with 0 failures (0 unexpected) in 0.051 (0.061) seconds

** TEST EXECUTE FAILED **
"""

LINT_ONLY = """\
Linting Swift files in current working directory
Done linting! Found 0 violations, 0 serious in 42 files.
"""

# name, log text, expected exit code, expected report fields
CASES: List[Tuple[str, str, int, Dict[str, Any]]] = [
    ("XCTest only", XCTEST_ONLY, 0, {"executed": 13, "markers": ["TEST SUCCEEDED"], "testCases": None}),
    ("Swift Testing with empty XCTest bundle", SWIFT_TESTING_ONLY, 0,
     {"executed": 7, "swiftTesting": {"runs": 1, "tests": 7, "failedRuns": 0, "issues": 0}}),
    ("Swift Testing failure", SWIFT_TESTING_FAILURE, 1,
     {"executed": 10, "swiftTesting": {"runs": 1, "tests": 10, "failedRuns": 1, "issues": 3}, "testCases": None}),
    ("Swift Testing failure without marker", SWIFT_TESTING_FAILURE_BODY, 1, {"markers": []}),
    ("XCTest failure", XCTEST_FAILURE, 1,
     {"executed": 13, "xctest": {"executed": 13, "skipped": 0, "failures": 1, "unexpected": 0}}),
    ("XCTest failure without marker", XCTEST_FAILURE_BODY, 1, {"markers": []}),
    ("XCTest skipped tests", XCTEST_SKIPPED, 0, {"executed": 11}),
    ("XCTest all tests skipped", XCTEST_ALL_SKIPPED, 2, {"executed": 0}),
    ("parallel clone lines", PARALLEL_CLONES, 0,
     {"executed": 3, "testCases": {"unique": 4, "passed": 3, "failed": 0, "skipped": 1}}),
    ("parallel clone failure", PARALLEL_CLONES_FAILURE, 1,
     {"testCases": {"unique": 2, "passed": 1, "failed": 1, "skipped": 0}}),
    ("zero tests", ZERO_TESTS, 2, {"result": "no tests", "executed": 0}),
    ("test build failure", TEST_BUILD_FAILURE, 1, {"executed": 0, "markers": ["TEST FAILED"], "buildErrors": 1}),
    ("build failure", BUILD_FAILURE, 1, {"markers": ["BUILD FAILED"], "buildErrors": 1}),
    ("build error without marker", BUILD_ERROR_ONLY, 1, {"executed": 0, "markers": [], "buildErrors": 1}),
    ("test failure lines are not build errors", XCTEST_FAILURE, 1, {"buildErrors": 0}),
    ("crash and restart", CRASH_RESTART, 1, {"restarts": 1, "executed": 1}),
    ("crash and restart without marker", CRASH_RESTART_BODY, 1, {"restarts": 1, "markers": []}),
    ("mixed frameworks over many runs", MIXED_MANY_RUNS, 1,
     {"executed": 302, "swiftTesting": {"runs": 3, "tests": 243, "failedRuns": 1, "issues": 3}}),
    ("two passing Swift Testing runs", TWO_PASSING_RUNS, 0, {"executed": 46}),
    ("Swift Testing short forms", SWIFT_TESTING_SHORT_FORMS, 0,
     {"executed": 9, "swiftTesting": {"runs": 3, "tests": 9, "failedRuns": 0, "issues": 0}}),
    ("test execute failure", TEST_EXECUTE_FAILURE, 1, {"markers": ["TEST EXECUTE FAILED"]}),
    ("log without tests", LINT_ONLY, 2, {"executed": 0, "markers": [], "xctest": None, "swiftTesting": None}),
]


def run(args: List[str], stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def check_case(folder: Path, name: str, text: str, code: int, fields: Dict[str, Any]) -> List[str]:
    log = folder / (name.replace(" ", "-") + ".raw.log")
    log.write_text(text, encoding="utf-8")
    problems = []

    plain = run([str(log)])
    if plain.returncode != code:
        problems.append(f"{name}: exit {plain.returncode}, expected {code}: {plain.stdout}{plain.stderr}")
    if len(plain.stdout.strip().splitlines()) != 1:
        problems.append(f"{name}: expected a one-line summary, got {plain.stdout!r}")

    structured = run([str(log), "--json"])
    if structured.returncode != code:
        problems.append(f"{name}: --json exit {structured.returncode}, expected {code}")
    try:
        report = json.loads(structured.stdout)
    except json.JSONDecodeError:
        return problems + [f"{name}: --json output does not parse: {structured.stdout!r}"]
    if report.get("exitCode") != code:
        problems.append(f"{name}: report exitCode {report.get('exitCode')}, expected {code}")
    for key, expected in fields.items():
        if report.get(key) != expected:
            problems.append(f"{name}: {key} = {report.get(key)!r}, expected {expected!r}")
    return problems


def main() -> int:
    problems: List[str] = []
    with tempfile.TemporaryDirectory(prefix="check-test-log-") as temp:
        folder = Path(temp)
        for name, text, code, fields in CASES:
            problems += check_case(folder, name, text, code, fields)

        piped = run(["-"], stdin=SWIFT_TESTING_ONLY)
        if piped.returncode != 0 or not piped.stdout.startswith("passed: 7 tests executed"):
            problems.append(f"stdin: unexpected result {piped.returncode} {piped.stdout!r}")

        missing = run([str(folder / "missing.raw.log")])
        if missing.returncode != 3 or not missing.stderr.startswith("error: cannot read"):
            problems.append(f"missing file: exit {missing.returncode}, stderr {missing.stderr!r}")

        no_args = run([])
        if no_args.returncode != 3:
            problems.append(f"missing argument: exit {no_args.returncode}, expected 3")

    if problems:
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        return 1
    print(f"check_test_log self-test passed: {len(CASES)} fixtures plus stdin and error cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
