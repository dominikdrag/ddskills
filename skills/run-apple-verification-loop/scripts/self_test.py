#!/usr/bin/env python3
"""Forward-test lease collision, ownership, and exact-command validation."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
LANE = SCRIPT_DIR / "lane.py"
RUN_GATE = SCRIPT_DIR / "run_gate.py"
UDID_A = "11111111-1111-4111-8111-111111111111"
UDID_B = "22222222-2222-4222-8222-222222222222"


def reserve(env: dict[str, str], root: Path, owner: str, udid: str, suffix: str) -> subprocess.Popen[str]:
    repo = root / f"repo-{suffix}"
    workspace = repo / f"App-{suffix}.xcworkspace"
    workspace.mkdir(parents=True)
    evidence = repo / "task-evidence" / suffix
    command = [
        sys.executable,
        str(LANE),
        "reserve",
        "--owner",
        owner,
        "--task",
        suffix,
        "--role",
        "test",
        "--udid",
        udid,
        "--repo",
        str(repo),
        "--workspace",
        str(workspace),
        "--derived-data",
        str(evidence / "DerivedData"),
        "--evidence",
        str(evidence),
        "--device-hub-window",
        f"window-{suffix}",
    ]
    return subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def run(*command: str, env: dict[str, str], expected: int) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    if result.returncode != expected:
        raise AssertionError(
            f"expected {expected}, got {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="apple-lane-test-") as temporary:
        root = Path(temporary)
        env = os.environ.copy()
        env["CODEX_APPLE_LANE_STATE"] = str(root / "state")

        contenders = [
            reserve(env, root, "owner-a", UDID_A, "a"),
            reserve(env, root, "owner-b", UDID_A, "b"),
        ]
        results = [(process.wait(), process.communicate()) for process in contenders]
        if sorted(code for code, _ in results) != [0, 2]:
            raise AssertionError(f"same-UDID race did not yield one winner: {results}")
        winner = "owner-a" if results[0][0] == 0 else "owner-b"
        loser = "owner-b" if winner == "owner-a" else "owner-a"

        run(sys.executable, str(LANE), "release", "--owner", loser, "--udid", UDID_A, env=env, expected=2)
        run(sys.executable, str(LANE), "release", "--owner", winner, "--udid", UDID_A, env=env, expected=0)

        first = reserve(env, root, "owner-a", UDID_A, "a2")
        second = reserve(env, root, "owner-b", UDID_B, "b2")
        if first.wait() != 0 or second.wait() != 0:
            raise AssertionError(f"distinct lanes should reserve concurrently: {first.communicate()} {second.communicate()}")
        first.communicate()
        second.communicate()

        repo = root / "repo-a2"
        evidence = repo / "task-evidence" / "a2"
        gate = run(
            sys.executable,
            str(RUN_GATE),
            "--owner",
            "owner-a",
            "--udid",
            UDID_A,
            "--log",
            str(evidence / "gate.raw.log"),
            "--require-executed-tests",
            "--",
            sys.executable,
            "-c",
            "print('Executed 1 test')",
            "-workspace",
            str(repo / "App-a2.xcworkspace"),
            "-destination",
            f"platform=iOS Simulator,id={UDID_A}",
            "-derivedDataPath",
            str(evidence / "DerivedData"),
            env=env,
            expected=0,
        )
        if "Executed 1 test" not in gate.stdout:
            raise AssertionError("guarded command output was not preserved")

        run(
            sys.executable,
            str(RUN_GATE),
            "--owner",
            "owner-a",
            "--udid",
            UDID_A,
            "--log",
            str(evidence / "name-based.raw.log"),
            "--",
            sys.executable,
            "-c",
            "print('Executed 1 test')",
            "-workspace",
            str(repo / "App-a2.xcworkspace"),
            "-destination",
            "platform=iOS Simulator,name=iPhone 17",
            "-derivedDataPath",
            str(evidence / "DerivedData"),
            env=env,
            expected=2,
        )
        run(
            sys.executable,
            str(RUN_GATE),
            "--owner",
            "owner-a",
            "--udid",
            UDID_A,
            "--log",
            str(evidence / "zero-tests.raw.log"),
            "--require-executed-tests",
            "--",
            sys.executable,
            "-c",
            "print('TEST SUCCEEDED')",
            "-workspace",
            str(repo / "App-a2.xcworkspace"),
            "-destination",
            f"platform=iOS Simulator,id={UDID_A}",
            "-derivedDataPath",
            str(evidence / "DerivedData"),
            env=env,
            expected=86,
        )

        run(sys.executable, str(LANE), "release", "--owner", "owner-a", "--udid", UDID_A, env=env, expected=0)
        run(sys.executable, str(LANE), "release", "--owner", "owner-b", "--udid", UDID_B, env=env, expected=0)

    print("self-test passed: atomic collision, ownership, isolated concurrency, and gate validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
