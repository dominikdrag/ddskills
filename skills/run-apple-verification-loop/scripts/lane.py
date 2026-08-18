#!/usr/bin/env python3
"""Atomically reserve exact Apple verification resources across Codex tasks."""

from __future__ import annotations

import argparse
import fcntl
import getpass
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


STATE_ENV = "CODEX_APPLE_LANE_STATE"
DEFAULT_STATE = Path.home() / ".codex" / "state" / "apple-verification-lanes"


def state_dir() -> Path:
    return Path(os.environ.get(STATE_ENV, DEFAULT_STATE)).expanduser().resolve()


def normalized_udid(value: str) -> str:
    try:
        return str(uuid.UUID(value)).upper()
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid simulator UDID: {value}") from error


def resolved_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def validate_owned_path(path: Path, repo: Path, label: str) -> None:
    forbidden = {Path("/"), Path.home().resolve(), repo.resolve()}
    if path in forbidden:
        raise ValueError(f"{label} must be a task-specific path, not {path}")


def lease_path(udid: str) -> Path:
    return state_dir() / f"{udid}.json"


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
        return json.load(file)


def active_leases() -> list[dict[str, Any]]:
    directory = state_dir()
    if not directory.exists():
        return []
    leases: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            leases.append(read_lease(path))
        except (OSError, json.JSONDecodeError):
            print(f"warning: unreadable lease {path}", file=sys.stderr)
    return leases


def paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def collision(existing: dict[str, Any], proposed: dict[str, Any]) -> str | None:
    checks = (
        ("udid", "simulator UDID"),
        ("derivedData", "DerivedData path"),
        ("deviceHubWindow", "Device Hub window"),
    )
    for key, label in checks:
        if existing[key] == proposed[key]:
            return label
    same_task = all(existing[key] == proposed[key] for key in ("owner", "repo", "task"))
    if existing["workspace"] == proposed["workspace"] and not same_task:
        return "workspace"
    if paths_overlap(Path(existing["evidence"]), Path(proposed["evidence"])):
        return "evidence directory"
    return None


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

    proposed = {
        "schemaVersion": 1,
        "udid": args.udid,
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
        "acquiredAt": datetime.now(timezone.utc).isoformat(),
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
        path = lease_path(args.udid)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(proposed, file, indent=2, sort_keys=True)
            file.write("\n")

    print(json.dumps(proposed, indent=2, sort_keys=True))
    return 0


def release(args: argparse.Namespace) -> int:
    with registry_lock():
        path = lease_path(args.udid)
        if not path.exists():
            print(f"no active lease for {args.udid}", file=sys.stderr)
            return 2
        lease = read_lease(path)
        if lease["owner"] != args.owner:
            print(
                f"release blocked: {args.udid} is owned by {lease['owner']}",
                file=sys.stderr,
            )
            return 2
        path.unlink()
    print(f"released {args.udid} for {args.owner}")
    return 0


def status(args: argparse.Namespace) -> int:
    leases = active_leases()
    if args.udid:
        leases = [lease for lease in leases if lease["udid"] == args.udid]
    if args.json:
        payload: Any = leases[0] if args.udid and leases else leases
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif not leases:
        print("no active Apple verification leases")
    else:
        for lease in leases:
            print(
                f"{lease['udid']}  {lease['role']:<8}  {lease['owner']}  "
                f"{lease['repo']}  {lease['task']}"
            )
    return 0 if leases or not args.udid else 1


def discover_devices() -> tuple[str, list[dict[str, str]]]:
    command = [
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
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "devicectl device discovery failed")
    payload = json.loads(result.stdout)
    devices: list[dict[str, str]] = []
    for device in payload.get("result", {}).get("devices", []):
        properties = device.get("properties", {})
        hardware = properties.get("hardware", {})
        software = properties.get("software", {})
        state = properties.get("state", {})
        if hardware.get("reality") != "simulated" or hardware.get("platform") != "iOS":
            continue
        os_version = software.get("osVersionNumber", {}).get("stringValue", "unknown")
        devices.append(
            {
                "udid": normalized_udid(device["identifier"]),
                "name": state.get("name", hardware.get("marketingName", "unknown")),
                "os": os_version,
                "state": state.get("bootState", "unknown"),
            }
        )
    return "devicectl", sorted(devices, key=lambda item: (item["name"], item["udid"]))


def list_devices(args: argparse.Namespace) -> int:
    source, devices = discover_devices()
    leases = {lease["udid"]: lease for lease in active_leases()}
    if args.json:
        print(json.dumps({"source": source, "devices": devices, "leases": leases}, indent=2, sort_keys=True))
        return 0
    print(f"source: {source}")
    for device in devices:
        lease = leases.get(device["udid"])
        owner = f"leased by {lease['owner']} ({lease['task']})" if lease else "available"
        print(f"{device['udid']}  {device['name']}  iOS {device['os']}  {device['state']}  {owner}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="list simulated iOS devices and leases")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=list_devices)

    reserve_parser = commands.add_parser("reserve", help="atomically reserve a verification lane")
    reserve_parser.add_argument("--owner", required=True)
    reserve_parser.add_argument("--task", required=True)
    reserve_parser.add_argument("--role", choices=("test", "qa", "snapshot"), required=True)
    reserve_parser.add_argument("--udid", type=normalized_udid, required=True)
    reserve_parser.add_argument("--repo", required=True)
    reserve_parser.add_argument("--workspace", required=True)
    reserve_parser.add_argument("--derived-data", required=True)
    reserve_parser.add_argument("--evidence", required=True)
    reserve_parser.add_argument("--device-hub-window", required=True)
    reserve_parser.set_defaults(handler=reserve)

    status_parser = commands.add_parser("status", help="show active leases")
    status_parser.add_argument("--udid", type=normalized_udid)
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(handler=status)

    release_parser = commands.add_parser("release", help="release an owned lane")
    release_parser.add_argument("--owner", required=True)
    release_parser.add_argument("--udid", type=normalized_udid, required=True)
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
