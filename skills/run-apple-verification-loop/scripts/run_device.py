#!/usr/bin/env python3
"""Run supported devicectl operations only against an exact owned device."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import lane

SUPPORTED_OPERATIONS = {
    ("device", "install", "app"): "install app",
    ("device", "process", "launch"): "process launch",
}


def option_values(command: list[str], *options: str) -> list[str]:
    values: list[str] = []
    for index, token in enumerate(command):
        for option in options:
            if token == option and index + 1 < len(command):
                values.append(command[index + 1])
            elif token.startswith(f"{option}="):
                values.append(token[len(option) + 1 :])
    return values


def inside(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def validate(
    command: list[str], lease: dict[str, object]
) -> tuple[list[str], Path, str]:
    if command and command[0] == "--":
        command = command[1:]
    if command[:2] != ["xcrun", "devicectl"]:
        raise ValueError("command must start with xcrun devicectl")

    operation_key = tuple(command[2:5])
    operation = SUPPORTED_OPERATIONS.get(operation_key)
    if operation is None:
        raise ValueError(
            "only device install app and device process launch are supported"
        )

    identifiers = option_values(command, "--device", "-d")
    if identifiers != [lane.lease_identifier(lease)]:
        raise ValueError("--device must equal the exact leased CoreDevice UUID")

    json_outputs = option_values(command, "--json-output", "-j")
    if len(json_outputs) != 1:
        raise ValueError("command must write one structured --json-output file")
    json_path = Path(json_outputs[0]).expanduser().resolve()
    evidence = Path(str(lease["evidence"]))
    if not inside(json_path, evidence):
        raise ValueError(f"--json-output must be inside {evidence}")
    if operation == "install app":
        app_paths = [
            Path(token).expanduser().resolve()
            for token in command[5:]
            if Path(token).suffix == ".app"
        ]
        derived_data = Path(str(lease["derivedData"]))
        if (
            len(app_paths) != 1
            or not inside(app_paths[0], derived_data)
            or not app_paths[0].is_dir()
        ):
            raise ValueError(
                f"install app must use one existing .app inside {derived_data}"
            )
    return command, json_path, operation


def structured_result_succeeded(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    info = payload.get("info")
    return isinstance(info, dict) and info.get("outcome") == "success"


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
        lane.require_device_hub_confirmation(lease, "runtime")
        command, json_path, operation = validate(list(args.command), lease)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if json_path == log_path:
        print("error: structured JSON and raw log paths must differ", file=sys.stderr)
        return 2

    log_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text("", encoding="utf-8")
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
                log_file.write(line_text)
                log_file.flush()
                sys.stdout.write(line_text)
                sys.stdout.flush()
        except KeyboardInterrupt:
            process.send_signal(2)
            process.wait()
            return 130
        return_code = process.wait()

    if return_code == 0 and not structured_result_succeeded(json_path):
        print(
            f"error: {operation} exited zero without successful structured evidence",
            file=sys.stderr,
        )
        return 87
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
