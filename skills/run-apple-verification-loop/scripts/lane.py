#!/usr/bin/env python3
"""Atomically reserve exact Apple verification resources across Codex tasks."""

from __future__ import annotations

import argparse
import fcntl
import getpass
import json
import os
import re
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

STATE_ENV = "CODEX_APPLE_LANE_STATE"
DEFAULT_STATE = Path.home() / ".codex" / "state" / "apple-verification-lanes"
DEVICECTL_COMMAND = (
    "xcrun",
    "devicectl",
    "list",
    "devices",
    "--json-output",
    "-",
    "--quiet",
    "--timeout",
    "10",
    "--omit-deprecated-fields-in-json",
)
SUPPORTED_REALITIES = {"physical": "physical", "simulated": "simulator"}
SUPPORTED_DEVICE_OPERATIONS = {
    ("device", "install", "app"): "install app",
    ("device", "process", "launch"): "process launch",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_dir() -> Path:
    return Path(os.environ.get(STATE_ENV, DEFAULT_STATE)).expanduser().resolve()


def normalized_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value)).upper()
    except ValueError as error:
        raise ValueError(f"invalid CoreDevice identifier UUID: {value}") from error


def uuid_argument(value: str) -> str:
    try:
        return normalized_uuid(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def resolved_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def validate_owned_path(path: Path, repo: Path, label: str) -> None:
    forbidden = {Path("/"), Path.home().resolve(), repo.resolve()}
    if path in forbidden:
        raise ValueError(f"{label} must be a task-specific path, not {path}")


def lease_path(device_identifier: str) -> Path:
    return state_dir() / f"{device_identifier}.json"


def lease_identifier(lease: dict[str, Any]) -> str:
    identifier = lease.get("deviceIdentifier", lease.get("udid"))
    if not isinstance(identifier, str):
        raise ValueError("lease has no device identifier")
    return normalized_uuid(identifier)


@contextmanager
def registry_lock() -> Iterator[None]:
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / ".registry.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield


def read_lease(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid lease document: {path}")
    return payload


def active_leases() -> list[dict[str, Any]]:
    directory = state_dir()
    if not directory.exists():
        return []
    leases: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            leases.append(read_lease(path))
        except (OSError, ValueError) as error:
            raise RuntimeError(
                f"unreadable lease blocks the registry: {path}"
            ) from error
    return leases


def paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def collision(existing: dict[str, Any], proposed: dict[str, Any]) -> str | None:
    if lease_identifier(existing) == lease_identifier(proposed):
        return "device identifier"
    if existing["derivedData"] == proposed["derivedData"]:
        return "DerivedData path"
    existing_window = existing.get("deviceHubWindow")
    proposed_window = proposed.get("deviceHubWindow")
    if existing_window and proposed_window and existing_window == proposed_window:
        return "Device Hub window"
    same_task = all(existing[key] == proposed[key] for key in ("owner", "repo", "task"))
    if existing["workspace"] == proposed["workspace"] and not same_task:
        return "workspace"
    if paths_overlap(Path(existing["evidence"]), Path(proposed["evidence"])):
        return "evidence directory"
    return None


def parse_device(raw: dict[str, Any]) -> dict[str, str] | None:
    properties = raw.get("properties")
    if not isinstance(properties, dict):
        return None
    hardware = properties.get("hardware", {})
    if not isinstance(hardware, dict):
        raise ValueError("devicectl device has malformed hardware properties")
    if (
        hardware.get("platform") != "iOS"
        or hardware.get("reality") not in SUPPORTED_REALITIES
    ):
        return None

    identifier = normalized_uuid(str(raw.get("identifier", "")))
    destination_identifier = str(hardware.get("udid", "")).strip()
    if not destination_identifier:
        raise ValueError(f"devicectl device {identifier} has no hardware UDID")

    kind = SUPPORTED_REALITIES[hardware["reality"]]
    if kind == "simulator":
        destination_identifier = normalized_uuid(destination_identifier)
        if destination_identifier != identifier:
            raise ValueError(
                f"simulator identifier mismatch: CoreDevice {identifier}, "
                f"hardware {destination_identifier}"
            )

    state = properties.get("state", {})
    software = properties.get("software", {})
    connection = properties.get("connection", {})
    if (
        not isinstance(state, dict)
        or not isinstance(software, dict)
        or not isinstance(connection, dict)
    ):
        raise ValueError(f"devicectl device {identifier} has malformed properties")
    version_number = software.get("osVersionNumber", {})
    if not isinstance(version_number, dict):
        raise ValueError(f"devicectl device {identifier} has a malformed OS version")
    os_version = version_number.get("stringValue", "unknown")
    platform = "iOS Simulator" if kind == "simulator" else "iOS"
    return {
        "identifier": identifier,
        "destinationIdentifier": destination_identifier,
        "kind": kind,
        "name": str(state.get("name", hardware.get("marketingName", "unknown"))),
        "os": str(os_version),
        "platform": platform,
        "reportedBootState": str(state.get("bootState", "unknown")),
        "reportedConnectionState": str(connection.get("state", "unknown")),
    }


def discover_devices() -> tuple[dict[str, Any], list[dict[str, str]]]:
    result = subprocess.run(
        DEVICECTL_COMMAND, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "devicectl device discovery failed")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("devicectl JSON root is not an object")
    info = payload.get("info", {})
    if not isinstance(info, dict):
        raise RuntimeError("devicectl JSON has malformed command information")
    if info.get("outcome") != "success":
        raise RuntimeError("devicectl JSON did not report a successful outcome")
    command_result = payload.get("result", {})
    if not isinstance(command_result, dict):
        raise RuntimeError("devicectl JSON has a malformed result")
    raw_devices = command_result.get("devices")
    if not isinstance(raw_devices, list):
        raise RuntimeError("devicectl JSON has no device inventory")

    if not all(isinstance(raw, dict) for raw in raw_devices):
        raise RuntimeError("devicectl JSON contains a malformed device entry")
    devices = [
        device for raw in raw_devices if (device := parse_device(raw)) is not None
    ]
    source = {
        "command": "xcrun devicectl list devices",
        "jsonVersion": info.get("jsonVersion"),
        "toolVersion": info.get("version"),
    }
    return source, sorted(
        devices, key=lambda item: (item["kind"], item["name"], item["identifier"])
    )


def exact_device(device_identifier: str) -> tuple[dict[str, Any], dict[str, str]]:
    source, devices = discover_devices()
    matches = [
        device for device in devices if device["identifier"] == device_identifier
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"devicectl did not confirm exact iOS device {device_identifier}"
        )
    return source, matches[0]


def recheck_leased_device(lease: dict[str, Any]) -> dict[str, str]:
    identifier = lease_identifier(lease)
    _, device = exact_device(identifier)
    expected = {
        "destinationIdentifier": lease.get("destinationIdentifier"),
        "kind": lease.get("deviceKind"),
        "platform": lease.get("platform"),
    }
    for key, value in expected.items():
        if not isinstance(value, str) or device[key] != value:
            raise RuntimeError(f"devicectl identity changed for {identifier}: {key}")
    return device


def reserve(args: argparse.Namespace) -> int:
    repo = resolved_path(args.repo)
    workspace = resolved_path(args.workspace)
    derived_data = resolved_path(args.derived_data)
    evidence = resolved_path(args.evidence)
    if not repo.is_dir():
        raise ValueError(f"repository does not exist: {repo}")
    if not workspace.exists():
        raise ValueError(f"workspace does not exist: {workspace}")
    validate_owned_path(derived_data, repo, "DerivedData")
    validate_owned_path(evidence, repo, "evidence directory")
    if evidence not in derived_data.parents:
        raise ValueError("DerivedData must be inside the task evidence directory")

    source, device = exact_device(args.device_identifier)
    xcode_destination = (
        f"platform={device['platform']},id={device['destinationIdentifier']}"
    )
    proposed = {
        "schemaVersion": 3,
        "deviceIdentifier": device["identifier"],
        "destinationIdentifier": device["destinationIdentifier"],
        "deviceKind": device["kind"],
        "deviceName": device["name"],
        "osVersion": device["os"],
        "platform": device["platform"],
        "xcodeDestination": xcode_destination,
        "devicectlDiscovery": {**source, "confirmedAt": now()},
        "role": args.role,
        "repo": str(repo),
        "workspace": str(workspace),
        "derivedData": str(derived_data),
        "evidence": str(evidence),
        "deviceHubWindow": args.device_hub_window,
        "task": args.task,
        "owner": args.owner,
        "user": getpass.getuser(),
        "pid": os.getpid(),
        "acquiredAt": now(),
    }

    with registry_lock():
        for existing in active_leases():
            conflict = collision(existing, proposed)
            if conflict:
                print(
                    f"reservation blocked: {conflict} is owned by "
                    f"{existing['owner']} for {existing['repo']} ({existing['task']})",
                    file=sys.stderr,
                )
                return 2
        evidence.mkdir(parents=True, exist_ok=True)
        derived_data.mkdir(parents=True, exist_ok=True)
        path = lease_path(args.device_identifier)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(proposed, file, indent=2, sort_keys=True)
            file.write("\n")

    print(json.dumps(proposed, indent=2, sort_keys=True))
    return 0


def option_values(command: list[str], *options: str) -> list[str]:
    values: list[str] = []
    for index, token in enumerate(command):
        for option in options:
            if token == option and index + 1 < len(command):
                values.append(command[index + 1])
            elif token.startswith(f"{option}="):
                values.append(token[len(option) + 1 :])
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


def command_after_separator(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("missing command after --")
    return command


def owned_lease(owner: str, device_identifier: str) -> dict[str, Any]:
    path = lease_path(device_identifier)
    if not path.exists():
        raise ValueError(f"no active lease for {device_identifier}")
    lease = read_lease(path)
    if lease.get("owner") != owner:
        raise ValueError(f"{device_identifier} is owned by {lease.get('owner')}")
    return lease


def guarded_log_path(value: str, lease: dict[str, Any]) -> Path:
    path = resolved_path(value)
    evidence = Path(str(lease["evidence"]))
    if not inside(path, evidence):
        raise ValueError(f"log must be inside {evidence}")
    return path


def validate_xcodebuild(command: list[str], lease: dict[str, Any]) -> list[str]:
    command = command_after_separator(command)
    if Path(command[0]).name != "xcodebuild":
        raise ValueError("guarded command must be xcodebuild")

    destination = required_option(command, "-destination")
    fields = destination_fields(destination)
    expected = {
        "platform": str(lease["platform"]),
        "id": str(lease["destinationIdentifier"]),
    }
    if fields != expected:
        raise ValueError(
            f"command must target platform={expected['platform']},id={expected['id']}"
        )

    derived_data = resolved_path(required_option(command, "-derivedDataPath"))
    if derived_data != Path(str(lease["derivedData"])):
        raise ValueError(f"-derivedDataPath must equal {lease['derivedData']}")

    workspace = resolved_path(required_option(command, "-workspace"))
    if workspace != Path(str(lease["workspace"])):
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


def validate_devicectl(
    command: list[str], lease: dict[str, Any]
) -> tuple[list[str], Path, str]:
    command = command_after_separator(command)
    if command[:2] != ["xcrun", "devicectl"]:
        raise ValueError("command must start with xcrun devicectl")

    operation = SUPPORTED_DEVICE_OPERATIONS.get(tuple(command[2:5]))
    if operation is None:
        raise ValueError(
            "only device install app and device process launch are supported"
        )

    if option_values(command, "--device", "-d") != [lease_identifier(lease)]:
        raise ValueError("--device must equal the exact leased CoreDevice UUID")

    json_outputs = option_values(command, "--json-output", "-j")
    if len(json_outputs) != 1:
        raise ValueError("command must write one structured --json-output file")
    json_path = resolved_path(json_outputs[0])
    evidence = Path(str(lease["evidence"]))
    if not inside(json_path, evidence):
        raise ValueError(f"--json-output must be inside {evidence}")

    if operation == "install app":
        app_paths = [
            resolved_path(token)
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


def stream_command(
    command: list[str], lease: dict[str, Any], log_path: Path
) -> tuple[int, str]:
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
            return 130, "".join(captured)
        return process.wait(), "".join(captured)


def run_xcodebuild(args: argparse.Namespace) -> int:
    lease = owned_lease(args.owner, args.device_identifier)
    log_path = guarded_log_path(args.log, lease)
    recheck_leased_device(lease)
    command = validate_xcodebuild(list(args.guarded_command), lease)
    return_code, output = stream_command(command, lease, log_path)
    if return_code == 0 and args.require_executed_tests and test_count(output) == 0:
        print(
            "error: command exited zero but no executed tests were found",
            file=sys.stderr,
        )
        return 86
    return return_code


def run_devicectl(args: argparse.Namespace) -> int:
    lease = owned_lease(args.owner, args.device_identifier)
    log_path = guarded_log_path(args.log, lease)
    recheck_leased_device(lease)
    command, json_path, operation = validate_devicectl(
        list(args.guarded_command), lease
    )
    if json_path == log_path:
        raise ValueError("structured JSON and raw log paths must differ")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text("", encoding="utf-8")
    return_code, _ = stream_command(command, lease, log_path)
    if return_code == 0 and not structured_result_succeeded(json_path):
        print(
            f"error: {operation} exited zero without successful structured evidence",
            file=sys.stderr,
        )
        return 87
    return return_code


def release(args: argparse.Namespace) -> int:
    with registry_lock():
        path = lease_path(args.device_identifier)
        if not path.exists():
            print(f"no active lease for {args.device_identifier}", file=sys.stderr)
            return 2
        lease = read_lease(path)
        if lease["owner"] != args.owner:
            print(
                f"release blocked: {args.device_identifier} is owned by "
                f"{lease['owner']}",
                file=sys.stderr,
            )
            return 2
        path.unlink()
    print(f"released {args.device_identifier} for {args.owner}")
    return 0


def status(args: argparse.Namespace) -> int:
    leases = active_leases()
    if args.device_identifier:
        leases = [
            lease
            for lease in leases
            if lease_identifier(lease) == args.device_identifier
        ]
    if args.json:
        payload: Any = leases[0] if args.device_identifier and leases else leases
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif not leases:
        print("no active Apple verification leases")
    else:
        for lease in leases:
            print(
                f"{lease_identifier(lease)}  {lease['role']:<8}  {lease['owner']}  "
                f"{lease['repo']}  {lease['task']}"
            )
    return 0 if leases or not args.device_identifier else 1


def list_devices(args: argparse.Namespace) -> int:
    source, devices = discover_devices()
    leases = {lease_identifier(lease): lease for lease in active_leases()}
    if args.json:
        print(
            json.dumps(
                {"source": source, "devices": devices, "leases": leases},
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(f"source: {source['command']} {source.get('toolVersion', 'unknown')}")
    for device in devices:
        lease = leases.get(device["identifier"])
        owner = (
            f"leased by {lease['owner']} ({lease['task']})" if lease else "available"
        )
        identity = (
            f"{device['identifier']}  {device['kind']:<9}  "
            f"{device['name']}  iOS {device['os']}"
        )
        reported = (
            f"reported={device['reportedBootState']}/"
            f"{device['reportedConnectionState']}"
        )
        print(f"{identity}  {reported}  {owner}")
    return 0


def add_device_identifier(
    parser: argparse.ArgumentParser, *, required: bool = False
) -> None:
    parser.add_argument(
        "--device-id",
        "--udid",
        dest="device_identifier",
        type=uuid_argument,
        required=required,
        help="exact CoreDevice identifier UUID; display names are not accepted",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser(
        "list", help="list devicectl-known iOS devices and leases"
    )
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=list_devices)

    reserve_parser = commands.add_parser(
        "reserve", help="atomically reserve a verification lane"
    )
    reserve_parser.add_argument("--owner", required=True)
    reserve_parser.add_argument("--task", required=True)
    reserve_parser.add_argument(
        "--role", choices=("test", "qa", "snapshot"), required=True
    )
    add_device_identifier(reserve_parser, required=True)
    reserve_parser.add_argument("--repo", required=True)
    reserve_parser.add_argument("--workspace", required=True)
    reserve_parser.add_argument("--derived-data", required=True)
    reserve_parser.add_argument("--evidence", required=True)
    reserve_parser.add_argument(
        "--device-hub-window",
        help="optional coordination label when this lane will use Device Hub",
    )
    reserve_parser.set_defaults(handler=reserve)

    xcodebuild_parser = commands.add_parser(
        "run-xcodebuild", help="run xcodebuild against the exact owned lane"
    )
    xcodebuild_parser.add_argument("--owner", required=True)
    add_device_identifier(xcodebuild_parser, required=True)
    xcodebuild_parser.add_argument("--log", required=True)
    xcodebuild_parser.add_argument("--require-executed-tests", action="store_true")
    xcodebuild_parser.add_argument(
        "guarded_command", metavar="command", nargs=argparse.REMAINDER
    )
    xcodebuild_parser.set_defaults(handler=run_xcodebuild)

    devicectl_parser = commands.add_parser(
        "run-devicectl", help="run a supported devicectl operation on the owned lane"
    )
    devicectl_parser.add_argument("--owner", required=True)
    add_device_identifier(devicectl_parser, required=True)
    devicectl_parser.add_argument("--log", required=True)
    devicectl_parser.add_argument(
        "guarded_command", metavar="command", nargs=argparse.REMAINDER
    )
    devicectl_parser.set_defaults(handler=run_devicectl)

    status_parser = commands.add_parser("status", help="show active leases")
    add_device_identifier(status_parser)
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(handler=status)

    release_parser = commands.add_parser("release", help="release an owned lane")
    release_parser.add_argument("--owner", required=True)
    add_device_identifier(release_parser, required=True)
    release_parser.set_defaults(handler=release)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
