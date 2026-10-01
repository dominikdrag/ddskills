#!/usr/bin/env python3
"""Check that a raw xcodebuild log proves tests ran and passed.

Usage: check_test_log.py <raw-log | -> [--json]

Counts XCTest summaries ("Executed N tests, with F failures"), Swift Testing
summaries ("Test run with N tests in M suites passed|failed"), per-test lines
("Test case '...' passed|failed|skipped on '...'", used when no summary counted
any test, as in parallel clone runs), result markers ("** TEST FAILED **" and
similar) and test-runner restarts after a crash.

Exit codes:
  0  tests executed and none failed
  1  a test failed, the runner crashed, or a FAILED/INTERRUPTED marker appeared
  2  no executed tests found
  3  the log could not be read or the arguments were wrong
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional

XCTEST_SUMMARY = re.compile(
    r"Executed (\d+) tests?, with (?:(\d+) tests? skipped and )?(\d+) failures?"
    r"(?: \((\d+) unexpected\))?"
)
SWIFT_TESTING_SUMMARY = re.compile(
    r"Test run with (\d+) tests?(?: in (\d+) suites?)? (passed|failed)"
    r"(?: after [\d.]+ seconds?)?(?: with (\d+) issues?)?"
)
TEST_CASE = re.compile(r"Test case '(.+?)' (passed|failed|skipped) on '")
MARKER = re.compile(r"^\*\* ([A-Z][A-Z ]*?) (SUCCEEDED|FAILED|INTERRUPTED) \*\*\s*$")
RESTART = "Restarting after unexpected exit, crash, or test timeout"
# Compiler and xcodebuild errors. Test assertion failures look alike, so these count only when no test reported anything.
BUILD_ERROR = re.compile(r"(?:^|:\d+(?::\d+)?: |\bxcodebuild: )error: (.+)")


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


class UsageError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # exit 3, keep 2 for "no tests"
        self.print_usage(sys.stderr)
        raise UsageError(message)


def analyze(text: str) -> Dict[str, Any]:
    xctest: Optional[Dict[str, int]] = None
    swift: Optional[Dict[str, int]] = None
    cases: Dict[str, set] = {}
    markers: List[str] = []
    restarts = 0
    errors: List[str] = []

    for line in text.splitlines():
        error = BUILD_ERROR.search(line.strip())
        if error:
            errors.append(line.strip())
        if RESTART in line:
            restarts += 1
            continue
        marker = MARKER.match(line.strip())
        if marker:
            markers.append(f"{marker.group(1)} {marker.group(2)}")
            continue
        match = XCTEST_SUMMARY.search(line)
        if match:
            executed = int(match.group(1))
            skipped = int(match.group(2) or 0)
            failures = int(match.group(3))
            unexpected = int(match.group(4)) if match.group(4) else failures
            if xctest is None:
                xctest = {"executed": 0, "skipped": 0, "failures": 0, "unexpected": 0}
            if executed > xctest["executed"]:
                xctest["executed"] = executed
                xctest["skipped"] = skipped
            xctest["failures"] = max(xctest["failures"], failures)
            xctest["unexpected"] = max(xctest["unexpected"], unexpected)
            continue
        match = SWIFT_TESTING_SUMMARY.search(line)
        if match:
            if swift is None:
                swift = {"runs": 0, "tests": 0, "failedRuns": 0, "issues": 0}
            swift["runs"] += 1
            swift["tests"] += int(match.group(1))
            if match.group(3) == "failed":
                swift["failedRuns"] += 1
            swift["issues"] += int(match.group(4) or 0)
            continue
        match = TEST_CASE.search(line)
        if match:
            cases.setdefault(match.group(1), set()).add(match.group(2))

    test_cases: Optional[Dict[str, int]] = None
    if cases:
        test_cases = {
            "unique": len(cases),
            "passed": sum(1 for s in cases.values() if s == {"passed"}),
            "failed": sum(1 for s in cases.values() if "failed" in s),
            "skipped": sum(1 for s in cases.values() if s == {"skipped"}),
        }

    executed = 0
    if xctest:
        executed += xctest["executed"] - xctest["skipped"]
    if swift:
        executed += swift["tests"]
    if executed == 0 and test_cases:
        executed = test_cases["unique"] - test_cases["skipped"]

    reasons: List[str] = []
    build_errors = errors if xctest is None and swift is None and test_cases is None else []
    if build_errors:
        first = build_errors[0] if len(build_errors[0]) <= 200 else build_errors[0][:197] + "..."
        reasons.append(f"no test ran and the log has {plural(len(build_errors), 'error')}, usually a failed build (first: {first})")
    # Gate on every failure: assertion and snapshot failures print "(0 unexpected)"; that count covers only thrown errors.
    if xctest and xctest["failures"] > 0:
        reasons.append(f"XCTest reported {plural(xctest['failures'], 'failure')} ({xctest['unexpected']} unexpected)")
    if swift and swift["failedRuns"] > 0:
        reasons.append(f"Swift Testing reported {plural(swift['failedRuns'], 'failed run')}")
    if test_cases and test_cases["failed"] > 0:
        reasons.append(f"{plural(test_cases['failed'], 'test case')} failed")
    if restarts:
        reasons.append(f"test runner restarted {plural(restarts, 'time')} after a crash or timeout")
    for marker_text in markers:
        if not marker_text.endswith("SUCCEEDED"):
            reasons.append(f"marker ** {marker_text} **")

    if reasons:
        result, exit_code = "failed", 1
    elif executed == 0:
        result, exit_code = "no tests", 2
        reasons.append("no executed tests found")
    else:
        result, exit_code = "passed", 0

    return {
        "result": result,
        "exitCode": exit_code,
        "executed": executed,
        "xctest": xctest,
        "swiftTesting": swift,
        "testCases": test_cases,
        "restarts": restarts,
        "buildErrors": len(build_errors),
        "markers": markers,
        "reasons": reasons,
    }


def summary_line(report: Dict[str, Any]) -> str:
    parts = [f"{report['result']}: {plural(report['executed'], 'test')} executed"]
    xctest = report["xctest"]
    if xctest:
        parts.append(
            f"XCTest {xctest['executed']} executed, {xctest['skipped']} skipped, "
            f"{plural(xctest['failures'], 'failure')} ({xctest['unexpected']} unexpected)"
        )
    swift = report["swiftTesting"]
    if swift:
        parts.append(
            f"Swift Testing {plural(swift['tests'], 'test')} in {plural(swift['runs'], 'run')}, "
            f"{swift['failedRuns']} failed, {plural(swift['issues'], 'issue')}"
        )
    cases = report["testCases"]
    if cases:
        parts.append(
            f"test case lines {cases['unique']} unique, {cases['passed']} passed, "
            f"{cases['failed']} failed, {cases['skipped']} skipped"
        )
    if report["restarts"]:
        parts.append(f"restarts {report['restarts']}")
    if report["buildErrors"]:
        parts.append(f"build errors {report['buildErrors']}")
    parts.append("markers " + (", ".join(report["markers"]) or "none"))
    if report["exitCode"] != 0:
        parts.append("why: " + "; ".join(report["reasons"]))
    return " | ".join(parts)


def read_log(path: str) -> str:
    if path == "-":
        data = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as error:
            raise UsageError(f"cannot read {path}: {error.strerror}") from error
    return data.decode("utf-8", errors="replace")


def main(argv: Optional[List[str]] = None) -> int:
    parser = Parser(
        description="Check that a raw xcodebuild log proves tests ran and passed.",
        epilog="Exit codes: 0 passed, 1 failed, 2 no executed tests, 3 unreadable log or bad arguments.",
    )
    parser.add_argument("log", help="raw xcodebuild log path, or - for stdin")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    try:
        args = parser.parse_args(argv)
        report = analyze(read_log(args.log))
    except UsageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(summary_line(report))
    return report["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
