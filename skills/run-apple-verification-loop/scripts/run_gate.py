#!/usr/bin/env python3
"""Run a command only when it matches an owned Apple verification lease."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import lane


def option_value(command: list[str], option: str) -> str | None:
    for index, token in enumerate(command):
        if token == option and index + 1 < len(command):
            return command[index + 1]
        prefix = f"{option}="
        if token.startswith(prefix):
            return token[len(prefix) :]
    return None


def inside(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def validate(args: argparse.Namespace, lease: dict[str, object]) -> list[str]:
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("missing command after --")

    destination = option_value(command, "-destination")
    expected_destination = f"id={args.udid}"
    if destination is None or "platform=iOS Simulator" not in destination or expected_destination not in destination:
        raise ValueError(f"command must target platform=iOS Simulator,{expected_destination}")
    if "name=" in destination:
        raise ValueError("name-based destinations are forbidden in an owned lane")

    derived_data = option_value(command, "-derivedDataPath")
    if derived_data is None or Path(derived_data).expanduser().resolve() != Path(str(lease["derivedData"])):
        raise ValueError(f"-derivedDataPath must equal {lease['derivedData']}")

    workspace = option_value(command, "-workspace")
    if workspace is None or Path(workspace).expanduser().resolve() != Path(str(lease["workspace"])):
        raise ValueError(f"-workspace must equal {lease['workspace']}")
    return command


def test_count(output: str) -> int:
    patterns = (
        r"Executed\s+(\d+)\s+tests?",
        r"Test run with\s+(\d+)\s+tests?\s+passed",
        r"\b(\d+)\s+tests?\s+passed\b",
    )
    counts = [int(match) for pattern in patterns for match in re.findall(pattern, output)]
    return max(counts, default=0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--udid", type=lane.normalized_udid, required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--require-executed-tests", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    path = lane.lease_path(args.udid)
    if not path.exists():
        print(f"error: no active lease for {args.udid}", file=sys.stderr)
        return 2
    lease = lane.read_lease(path)
    if lease["owner"] != args.owner:
        print(f"error: {args.udid} is owned by {lease['owner']}", file=sys.stderr)
        return 2

    log_path = Path(args.log).expanduser().resolve()
    evidence = Path(str(lease["evidence"]))
    if not inside(log_path, evidence):
        print(f"error: log must be inside {evidence}", file=sys.stderr)
        return 2

    try:
        command = validate(args, lease)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    log_path.parent.mkdir(parents=True, exist_ok=True)
    captured: list[str] = []
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=str(lease["repo"]),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line_text in process.stdout:
                captured.append(line_text)
                log_file.write(line_text)
                log_file.flush()
                sys.stdout.write(line_text)
                sys.stdout.flush()
        except KeyboardInterrupt:
            process.send_signal(2)
            process.wait()
            return 130
        return_code = process.wait()

    output = "".join(captured)
    if return_code == 0 and args.require_executed_tests and test_count(output) == 0:
        print("error: command exited zero but no executed tests were found", file=sys.stderr)
        return 86
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
