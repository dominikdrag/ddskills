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


def option_values(command: list[str], option: str) -> list[str]:
    values: list[str] = []
    for index, token in enumerate(command):
        if token == option and index + 1 < len(command):
            values.append(command[index + 1])
        prefix = f"{option}="
        if token.startswith(prefix):
            values.append(token[len(prefix) :])
    return values


def required_option(command: list[str], option: str) -> str:
    values = option_values(command, option)
    if len(values) != 1:
        raise ValueError(f"command must have exactly one {option}")
    return values[0]


def destination_fields(destination: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for component in destination.split(","):
        key, separator, value = component.partition("=")
        if not separator or not key or key in fields:
            raise ValueError(
                "-destination must use unique comma-separated key=value fields"
            )
        fields[key] = value
    return fields


def inside(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def validate(args: argparse.Namespace, lease: dict[str, object]) -> list[str]:
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("missing command after --")
    if Path(command[0]).name != "xcodebuild":
        raise ValueError("guarded command must be xcodebuild")

    destination = required_option(command, "-destination")
    fields = destination_fields(destination)
    expected_platform = str(lease["platform"])
    expected_identifier = str(lease["destinationIdentifier"])
    if set(fields) != {"platform", "id"}:
        raise ValueError("-destination must contain only exact platform and id fields")
    if (
        fields.get("platform") != expected_platform
        or fields.get("id") != expected_identifier
    ):
        raise ValueError(
            f"command must target platform={expected_platform},id={expected_identifier}"
        )

    derived_data = required_option(command, "-derivedDataPath")
    if Path(derived_data).expanduser().resolve() != Path(str(lease["derivedData"])):
        raise ValueError(f"-derivedDataPath must equal {lease['derivedData']}")

    workspace = required_option(command, "-workspace")
    if Path(workspace).expanduser().resolve() != Path(str(lease["workspace"])):
        raise ValueError(f"-workspace must equal {lease['workspace']}")
    return command


def test_count(output: str) -> int:
    patterns = (
        r"Executed\s+(\d+)\s+tests?",
        r"Test run with\s+(\d+)\s+tests?\s+passed",
        r"\b(\d+)\s+tests?\s+passed\b",
    )
    counts = [
        int(match) for pattern in patterns for match in re.findall(pattern, output)
    ]
    return max(counts, default=0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument(
        "--device-id",
        "--udid",
        dest="device_identifier",
        type=lane.uuid_argument,
        required=True,
    )
    parser.add_argument("--log", required=True)
    parser.add_argument("--require-executed-tests", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    path = lane.lease_path(args.device_identifier)
    if not path.exists():
        print(f"error: no active lease for {args.device_identifier}", file=sys.stderr)
        return 2
    lease = lane.read_lease(path)
    if lease["owner"] != args.owner:
        print(
            f"error: {args.device_identifier} is owned by {lease['owner']}",
            file=sys.stderr,
        )
        return 2

    log_path = Path(args.log).expanduser().resolve()
    evidence = Path(str(lease["evidence"]))
    if not inside(log_path, evidence):
        print(f"error: log must be inside {evidence}", file=sys.stderr)
        return 2

    try:
        lane.confirm_leased_device(lease)
        lane.require_device_hub_confirmation(lease, "destination")
        command = validate(args, lease)
    except (OSError, RuntimeError, ValueError) as error:
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
        print(
            "error: command exited zero but no executed tests were found",
            file=sys.stderr,
        )
        return 86
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
