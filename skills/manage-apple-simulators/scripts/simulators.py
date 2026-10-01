#!/usr/bin/env python3
"""Claim, create, boot, release, and clean up Apple simulators and devices for agent tasks.

Every agent task gets its own temporary simulator named "agent-sim <claim-id> <model> <os>"
and deletes it on release. Physical devices are claimed by exact ID and never created or
deleted. Cleanup only touches "agent-sim <claim-id> ..." simulators and shut-down XCTest clones.

Environment overrides (mainly for tests):
  APPLE_SIMULATORS_STATE          state folder (default ~/.local/state/manage-apple-simulators)
  APPLE_SIMULATORS_XCRUN          xcrun executable for every simctl/devicectl call (default xcrun)
  APPLE_SIMULATORS_XCTEST_SET     XCTest clone device set (default ~/Library/Developer/XCTestDevices)
  APPLE_SIMULATORS_LEGACY_LEASES  legacy lane leases, read only
                                  (default ~/.codex/state/apple-verification-lanes)
  APPLE_SIMULATORS_OWNER_PID      same as --owner-pid
  APPLE_SIMULATORS_PS             ps executable (default ps)

Exit codes: 0 ok, 1 unexpected error, 2 usage error or refused, 3 blocked.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

PREFIX = "agent-sim "
AGENT_NAME = re.compile(r"^agent-sim ([0-9a-f]{8}) ")  # the only simulators cleanup may delete
CLONE_NAME = re.compile(r"^Clone [1-9][0-9]* of (.+)$")
UUID_NAME = re.compile(r"^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DEFAULT_MODEL = "iPhone 17 Pro"
CLAIM_HOURS = 12
LOCK_WAIT_SECONDS = 60
BOOT_TIMEOUT_SECONDS = 300
CREATE_TIMEOUT_MINUTES = 30  # above the worst case of create, boot, bootstatus, getenv, and lock waits
MAINTENANCE_DAYS = 7
BUSY_BOOTED_COUNT = 4
INSTALL_HINT = "install runtimes in Xcode > Settings > Components; this script never downloads them"

Claim = Dict[str, Any]
Device = Dict[str, Any]


class Failure(Exception):
    """Expected failure, printed as `<prefix>: <message>` without a traceback."""

    def __init__(self, message: str, code: int = 2, prefix: str = "error") -> None:
        super().__init__(message)
        self.code = code
        self.prefix = prefix


def blocked(message: str) -> Failure:
    return Failure(message, 3, "blocked")


def note(message: str) -> None:
    print(message, file=sys.stderr)


# --- paths, time, files ----------------------------------------------------------------


def setting(name: str, default: str) -> str:
    return os.environ.get(name) or default


def state_dir() -> Path:
    return Path(setting("APPLE_SIMULATORS_STATE", "~/.local/state/manage-apple-simulators")).expanduser()


def claims_dir() -> Path:
    return state_dir() / "claims"


def xctest_set() -> Path:
    return Path(setting("APPLE_SIMULATORS_XCTEST_SET", "~/Library/Developer/XCTestDevices")).expanduser()


def legacy_dir() -> Path:
    return Path(setting("APPLE_SIMULATORS_LEGACY_LEASES", "~/.codex/state/apple-verification-lanes")).expanduser()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(value: Any) -> Optional[datetime]:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else None


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    """Write through a temporary file and os.replace, so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


@contextmanager
def registry_lock() -> Iterator[None]:
    """Hold the registry lock for quick bookkeeping only; never across boots or deletes."""
    state_dir().mkdir(parents=True, exist_ok=True)
    path = state_dir() / "registry.lock"
    with path.open("a+") as handle:
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Failure(f"registry lock still busy after {LOCK_WAIT_SECONDS} s: {path}", 1) from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_claims() -> List[Claim]:
    claims: List[Claim] = []
    for path in sorted(claims_dir().glob("*.json")):
        try:
            claim = read_json(path)
        except (OSError, ValueError) as error:
            note(f"warning: skipping unreadable claim {path}: {error}")
            continue
        if isinstance(claim, dict) and claim.get("id") == path.stem:
            claims.append(claim)
    return claims


def claim_ids_on_disk() -> Set[str]:
    """Every claim file counts, even an unreadable one, so its simulator is never an orphan."""
    try:
        names = os.listdir(claims_dir())
    except FileNotFoundError:
        return set()
    except OSError as error:
        raise Failure(f"cannot read the claims folder {claims_dir()}: {error}") from error
    return {name[:-5] for name in names if name.endswith(".json")}


def save_claim(claim: Claim) -> None:
    write_json(claims_dir() / f"{claim['id']}.json", claim)


def drop_claim(claim_id: str) -> None:
    try:
        (claims_dir() / f"{claim_id}.json").unlink()
    except FileNotFoundError:
        pass


# --- xcrun simctl / devicectl -----------------------------------------------------------


def xcrun(*args: str, timeout: float = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = [setting("APPLE_SIMULATORS_XCRUN", "xcrun"), *args]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        raise Failure(f"command not found: {command[0]}", 1) from None
    except subprocess.TimeoutExpired:
        raise Failure(f"timed out after {timeout:.0f} s: xcrun {' '.join(args)}", 1) from None
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise Failure(f"xcrun {' '.join(args)} failed: {detail}", 1)
    return result


def set_args(device_set: Optional[Path]) -> List[str]:
    return ["--set", str(device_set)] if device_set else []


def simctl_list(kind: str, device_set: Optional[Path] = None) -> Dict[str, Any]:
    output = xcrun("simctl", *set_args(device_set), "list", "-j", kind).stdout
    try:
        payload = json.loads(output)
    except ValueError:
        raise Failure(f"simctl list {kind} returned invalid JSON", 1) from None
    return payload if isinstance(payload, dict) else {}


def list_devices(device_set: Optional[Path] = None) -> List[Device]:
    devices: List[Device] = []
    groups = simctl_list("devices", device_set).get("devices")
    for runtime, entries in (groups.items() if isinstance(groups, dict) else []):
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, dict) and isinstance(entry.get("udid"), str):
                devices.append({**entry, "name": str(entry.get("name", "")), "runtime": runtime})
    return devices


def clone_devices() -> List[Device]:
    """XCTest clones (`Clone <N> of <source>`) in the XCTest device set; [] if the set does not exist."""
    if not xctest_set().is_dir():
        return []
    clones = []
    for device in list_devices(xctest_set()):
        match = CLONE_NAME.match(device["name"])
        if match:
            clones.append({**device, "source": match.group(1)})
    return clones


def is_booted(device: Device) -> bool:
    return str(device.get("state", "")).lower() == "booted"


def claim_id_of(name: str) -> str:
    match = AGENT_NAME.match(name)
    return match.group(1) if match else ""


def remove_simulator(udid: str, device_set: Optional[Path] = None, shutdown: bool = True) -> None:
    """Shut down and delete one simulator. Warn instead of failing, so one stuck device never blocks the rest."""
    try:
        if shutdown:
            xcrun("simctl", *set_args(device_set), "shutdown", udid, check=False)
        result = xcrun("simctl", *set_args(device_set), "delete", udid, check=False)
    except Failure as error:
        note(f"warning: could not remove simulator {udid}: {error}")
        return
    detail = (result.stderr or result.stdout).strip()
    if result.returncode != 0 and "Invalid device" not in detail:
        note(f"warning: could not delete simulator {udid}: {detail}")


def boot(udid: str) -> None:
    result = xcrun("simctl", "boot", udid, check=False)
    if result.returncode != 0 and "current state: Booted" not in result.stderr + result.stdout:
        raise Failure(f"could not boot {udid}: {(result.stderr or result.stdout).strip()}", 1)
    xcrun("simctl", "bootstatus", udid, "-b", timeout=BOOT_TIMEOUT_SECONDS)


def read_runtime_build(udid: str) -> Optional[str]:
    result = xcrun("simctl", "getenv", udid, "SIMULATOR_RUNTIME_BUILD_VERSION", check=False)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def destroy(claim: Claim, devices: List[Device], clones: List[Device]) -> None:
    """Delete a temporary claim's simulator and its XCTest clones; anything else is left alone.

    The simulator is found by the UDID the claim records, so a renamed simulator is still deleted. Only a claim
    interrupted before `simctl create` printed a UDID falls back to the name. Clones match the claim's own name.
    """
    name = str(claim.get("name") or "")
    if claim.get("kind") != "simulator" or not claim.get("temporary") or not AGENT_NAME.match(name):
        return
    udid = claim.get("udid")
    for clone in clones:
        if clone["source"] == name:
            remove_simulator(clone["udid"], xctest_set())
    for device in devices:
        if (device["udid"] == udid) if udid else (device["name"] == name):
            remove_simulator(device["udid"])


def booted_count() -> Optional[int]:
    try:
        return sum(1 for device in list_devices() + clone_devices() if is_booted(device))
    except Failure:
        return None


def version_key(version: Any) -> Tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", str(version)))


def version_matches(version: Any, wanted: str) -> bool:
    return str(version) == wanted or str(version).startswith(wanted + ".")


def resolve_target(model: Optional[str], os_version: Optional[str], build: Optional[str]) -> Tuple[Device, Device]:
    """Pick the device type and newest matching installed iOS runtime, or report blocked."""
    model = model or DEFAULT_MODEL
    types = [entry for entry in simctl_list("devicetypes").get("devicetypes", []) if isinstance(entry, dict)]
    device_type = next((entry for entry in types if str(entry.get("name", "")).lower() == model.lower()), None)
    if device_type is None:
        names = ", ".join(str(entry.get("name")) for entry in types if entry.get("productFamily") in ("iPhone", "iPad"))
        raise blocked(f"no simulator model named {model!r}. Available: {names or 'none'}. {INSTALL_HINT}")
    runtimes = [
        entry
        for entry in simctl_list("runtimes").get("runtimes", [])
        if isinstance(entry, dict)
        and entry.get("isAvailable")
        and (entry.get("platform") == "iOS" or ".SimRuntime.iOS-" in str(entry.get("identifier", "")))
    ]
    matching = [entry for entry in runtimes if not os_version or version_matches(entry.get("version"), os_version)]
    if build:
        matching = [entry for entry in matching if entry.get("buildversion") == build]
    if not matching:
        installed = ", ".join(sorted({f"iOS {r.get('version')} ({r.get('buildversion')})" for r in runtimes}))
        wanted = f"iOS {os_version or '(newest)'}" + (f" build {build}" if build else "")
        raise blocked(f"no installed runtime matches {wanted}. Installed: {installed or 'none'}. {INSTALL_HINT}")
    runtime = max(matching, key=lambda entry: version_key(entry.get("version")))
    supported = runtime.get("supportedDeviceTypes")
    if isinstance(supported, list) and supported:
        if device_type.get("identifier") not in {item.get("identifier") for item in supported if isinstance(item, dict)}:
            raise blocked(f"{device_type.get('name')} is not supported by iOS {runtime.get('version')}")
    return device_type, runtime


def dig(value: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def first_text(*values: Any) -> Optional[str]:
    return next((value for value in values if isinstance(value, str) and value), None)


def parse_core_device(entry: Any) -> Optional[Device]:
    """Read one devicectl entry (new `properties` or deprecated `*Properties` layout); None if malformed."""
    if not isinstance(entry, dict) or not isinstance(entry.get("identifier"), str):
        return None

    def hardware(key: str) -> Optional[str]:
        return first_text(dig(entry, "properties", "hardware", key), dig(entry, "hardwareProperties", key))

    return {
        "identifier": entry["identifier"],
        "udid": hardware("udid"),
        "reality": hardware("reality"),
        "platform": hardware("platform") or "iOS",
        "model": hardware("marketingName") or hardware("productType") or "unknown",
        "name": first_text(dig(entry, "properties", "state", "name"), dig(entry, "deviceProperties", "name")),
        "os": first_text(
            dig(entry, "properties", "software", "osVersionNumber", "stringValue"),
            dig(entry, "deviceProperties", "osVersionNumber"),
        ),
        "build": first_text(
            dig(entry, "properties", "software", "osBuildVersions", "buildVersion", "name"),
            dig(entry, "deviceProperties", "osBuildUpdate"),
        ),
    }


def core_devices() -> List[Device]:
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "devices.json"
        xcrun("devicectl", "list", "devices", "--json-output", str(output), timeout=90)
        try:
            payload = read_json(output)
        except (OSError, ValueError):
            raise Failure("devicectl did not write readable JSON", 1) from None
    entries = dig(payload, "result", "devices")
    if not isinstance(entries, list):
        raise Failure("devicectl JSON has no device list", 1)
    return [device for device in map(parse_core_device, entries) if device]


def legacy_holder(ids: Set[str]) -> Optional[str]:
    """Return the legacy lease file that holds one of these IDs. Read only: never write there."""
    folder = legacy_dir()
    if not folder.is_dir():
        return None
    for path in sorted(folder.glob("*.json")):
        if not UUID_NAME.match(path.stem):
            continue
        if path.stem.upper() in ids:
            return str(path)
        try:
            lease = read_json(path)
        except (OSError, ValueError):
            continue
        fields = ("deviceIdentifier", "udid", "destinationIdentifier")
        if isinstance(lease, dict) and any(str(lease.get(field) or "").upper() in ids for field in fields):
            return str(path)
    return None


# --- owners, identity, abandonment -------------------------------------------------------


PS_WARNED = False


def warn_ps_failed() -> None:
    global PS_WARNED
    if not PS_WARNED:
        PS_WARNED = True
        note("warning: ps failed (a sandbox can block it), so owner processes cannot be checked; "
             "only expired claims count as abandoned")


def ps_fields(pid: int, fields: str) -> Optional[str]:
    """`ps -o <fields> -p <pid>` output: the text, "" when no such process, None when ps itself failed.

    LC_ALL=C and TZ=UTC0 make the start time the same for every caller, whatever its locale or time zone.
    """
    command = [setting("APPLE_SIMULATORS_PS", "ps"), "-o", fields, "-p", str(pid)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False,
                                env={**os.environ, "LC_ALL": "C", "TZ": "UTC0"})
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = result.stdout.strip()
    if result.returncode == 0 and output:
        return output
    if result.returncode == 1 and not output:  # ps ran and found no such process
        return ""
    return None


def parse_lstart(text: str) -> Optional[datetime]:
    """Read a C-locale `ps -o lstart` time such as "Thu Oct  1 12:15:44 2026" (naive, no zone)."""
    parts = text.split()
    if len(parts) != 5 or parts[1] not in MONTHS:
        return None
    try:
        hour, minute, second = (int(part) for part in parts[3].split(":"))
        return datetime(int(parts[4]), MONTHS.index(parts[1]) + 1, int(parts[2]), hour, minute, second)
    except ValueError:
        return None


def start_text(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def start_matches(recorded: Any, actual: datetime) -> bool:
    """Does a recorded owner start time match a process start (aware UTC)?

    Claims record ISO 8601 UTC. Claims written before that recorded ps's local time in an unknown time zone; accept
    those when they differ by a whole quarter hour of at most 14 hours, so no caller's time zone makes them look gone.
    """
    moment = parse_iso(recorded)
    if moment is not None:
        return moment == actual
    local = parse_lstart(str(recorded or ""))
    if local is None:
        return False
    offset = abs((actual.replace(tzinfo=None) - local).total_seconds())
    return offset <= 14 * 3600 and offset % 900 == 0


def owner_alive(owner: Dict[str, Any]) -> Optional[bool]:
    """True if the owner process still runs, False if it ended, None if ps could not tell."""
    try:
        pid = int(owner["pid"])
    except (KeyError, TypeError, ValueError):
        return False
    output = ps_fields(pid, "lstart=")
    if output == "":
        return False
    start = parse_lstart(output) if output else None
    if start is None:
        warn_ps_failed()
        return None
    return start_matches(owner.get("startedAt"), start.replace(tzinfo=timezone.utc))


def is_agent_command(command: str) -> bool:
    name = os.path.basename(command.strip()).lower()
    return name in ("claude", "codex") or name.startswith("codex-")


def detect_owner(explicit: Optional[int]) -> Optional[Dict[str, Any]]:
    """The long-running agent process: --owner-pid, else the nearest claude/codex ancestor."""
    value: Any = explicit if explicit is not None else os.environ.get("APPLE_SIMULATORS_OWNER_PID")
    if value not in (None, ""):
        try:
            pid = int(value)
        except ValueError:
            raise Failure(f"APPLE_SIMULATORS_OWNER_PID is not a process ID: {value!r}") from None
        output = ps_fields(pid, "lstart=,comm=")
        if output == "":
            raise Failure(f"owner process {pid} is not running")
        parts = output.split(None, 5) if output else []
        start = parse_lstart(" ".join(parts[:5]))
        if start is None:
            raise Failure(f"ps failed; cannot check owner process {pid}", 1)
        return {"pid": pid, "startedAt": start_text(start), "command": parts[5].strip() if len(parts) > 5 else ""}
    pid, seen = os.getppid(), set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        output = ps_fields(pid, "ppid=,lstart=,comm=")
        if output is None:
            warn_ps_failed()
            return None
        parts = output.split(None, 6)
        if len(parts) < 7 or not parts[0].isdigit():
            return None
        if is_agent_command(parts[6]):
            start = parse_lstart(" ".join(parts[1:6]))
            return {"pid": pid, "startedAt": start_text(start), "command": parts[6].strip()} if start else None
        pid = int(parts[0])
    return None


def resolve_worktree(value: Optional[str]) -> str:
    if value:
        return str(Path(value).expanduser().resolve())
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return str(Path(result.stdout.strip()).resolve())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return str(Path.cwd().resolve())


def identity(args: argparse.Namespace) -> Tuple[Optional[Dict[str, Any]], str, str]:
    return detect_owner(args.owner_pid), resolve_worktree(args.worktree), args.label or ""


def same_owner(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if str(left.get("pid")) != str(right.get("pid")):
        return False
    if left.get("startedAt") and left.get("startedAt") == right.get("startedAt"):
        return True
    for recorded, other in ((left, right), (right, left)):
        moment = parse_iso(other.get("startedAt"))
        if moment is not None and start_matches(recorded.get("startedAt"), moment):
            return True
    return False


def is_mine(claim: Claim, owner: Optional[Dict[str, Any]], worktree: str, label: str) -> bool:
    return same_owner(claim.get("owner"), owner) and claim.get("worktree") == worktree and claim.get("label", "") == label


def abandon_reason(claim: Claim, now: datetime) -> Optional[str]:
    """Why a claim counts as abandoned, or None. An owner that ps cannot check counts as alive."""
    if claim.get("status") == "creating":
        created = parse_iso(claim.get("createdAt"))
        if created and now - created > timedelta(minutes=CREATE_TIMEOUT_MINUTES):
            return "creation interrupted"
    owner = claim.get("owner")
    if owner and owner_alive(owner) is False:
        return "owner process ended"
    expires = parse_iso(claim.get("expiresAt"))
    if expires is None or expires <= now:
        return "expired"
    return None


def expiry() -> str:
    return iso(utc_now() + timedelta(hours=CLAIM_HOURS))


# --- cleanup ----------------------------------------------------------------------------


def maintenance_due() -> bool:
    try:
        last = parse_iso(read_json(state_dir() / "maintenance.json").get("lastGenericClonePruneAt"))
    except (OSError, ValueError, AttributeError):
        return True
    return last is None or utc_now() - last >= timedelta(days=MAINTENANCE_DAYS)


def run_cleanup(
    apply: bool, older_than_days: int, generic: bool, booted_orphans: bool = True
) -> Dict[str, List[Dict[str, Any]]]:
    """Find, and with apply remove: abandoned claims, orphan agent-sim simulators, stale XCTest clones.

    Without booted_orphans (automatic cleanup), a running orphan is only reported: it may belong to a claim this
    process cannot see, such as one written under another state folder.
    """
    now = utc_now()
    abandoned: List[Tuple[Claim, str]] = []
    with registry_lock():
        live_names = set()
        for claim in load_claims():
            reason = abandon_reason(claim, now)
            if not reason:
                live_names.add(claim.get("name"))
                continue
            abandoned.append((claim, reason))
            if apply and claim.get("status") != "releasing":
                claim["status"] = "releasing"
                save_claim(claim)
    # List devices before reading claim IDs: a claim file is always written before its simulator exists.
    devices, clones = list_devices(), clone_devices()
    known = claim_ids_on_disk()
    orphans = [d for d in devices if AGENT_NAME.match(d["name"]) and claim_id_of(d["name"]) not in known]
    kept_orphans = [] if booted_orphans else [d for d in orphans if is_booted(d)]
    orphans = [d for d in orphans if d not in kept_orphans]
    abandoned_names = {claim.get("name") for claim, _ in abandoned}
    cutoff = time.time() - older_than_days * 86400
    stale: List[Device] = []
    for clone in clones:
        if is_booted(clone) or clone["source"] in abandoned_names:
            continue
        if AGENT_NAME.match(clone["source"]) and clone["source"] not in live_names:
            stale.append({**clone, "reason": "its agent-sim simulator has no live claim"})
            continue
        folder = xctest_set() / clone["udid"]
        if generic and folder.is_dir() and folder.stat().st_mtime < cutoff:
            stale.append({**clone, "reason": f"older than {older_than_days} days"})
    if apply:
        for claim, _ in abandoned:
            destroy(claim, devices, clones)
        for device in orphans:
            remove_simulator(device["udid"])
        for clone in stale:
            remove_simulator(clone["udid"], xctest_set(), shutdown=False)
        with registry_lock():
            for claim, _ in abandoned:
                drop_claim(claim["id"])
            if generic:
                write_json(state_dir() / "maintenance.json", {"schemaVersion": 1, "lastGenericClonePruneAt": iso(now)})
    return {
        "abandonedClaims": [
            {"id": c["id"], "name": c.get("name"), "udid": c.get("udid"), "kind": c.get("kind"), "reason": r}
            for c, r in abandoned
        ],
        "orphanSimulators": [{"udid": d["udid"], "name": d["name"], "state": d.get("state")} for d in orphans],
        "keptBootedOrphans": [{"udid": d["udid"], "name": d["name"]} for d in kept_orphans],
        "clones": [{"udid": c["udid"], "name": c["name"], "reason": c["reason"]} for c in stale],
    }


def describe_cleanup(report: Dict[str, List[Dict[str, Any]]], applied: bool) -> List[str]:
    verb = "removed" if applied else "would remove"
    lines = [f"{verb} abandoned claim {c['id']} ({c['reason']}): {c['name']}" for c in report["abandonedClaims"]]
    lines += [f"{verb} orphan simulator {d['name']} ({d['udid']})" for d in report["orphanSimulators"]]
    lines += [
        f"kept running orphan simulator {d['name']} ({d['udid']}); remove it with cleanup --apply if no agent uses it"
        for d in report.get("keptBootedOrphans", [])
    ]
    lines += [f"{verb} XCTest clone {c['name']} ({c['udid']}): {c['reason']}" for c in report["clones"]]
    return lines


def auto_cleanup() -> Dict[str, List[Dict[str, Any]]]:
    """Housekeeping inside claim and release; a failure here never blocks the caller's own claim or release."""
    try:
        report = run_cleanup(
            apply=True, older_than_days=MAINTENANCE_DAYS, generic=maintenance_due(), booted_orphans=False
        )
    except Failure as error:
        note(f"warning: automatic cleanup skipped: {error}")
        return {"abandonedClaims": [], "orphanSimulators": [], "keptBootedOrphans": [], "clones": []}
    for line in describe_cleanup(report, applied=True):
        note(f"cleanup: {line}")
    return report


# --- claim ------------------------------------------------------------------------------


def base_claim(claim_id: str, kind: str, owner: Optional[Dict[str, Any]], worktree: str, label: str) -> Claim:
    now = utc_now()
    return {
        "schemaVersion": 1, "id": claim_id, "kind": kind, "status": "creating", "name": None, "udid": None,
        "destination": None, "model": None, "deviceTypeIdentifier": None, "os": None, "runtimeIdentifier": None,
        "runtimeBuild": None, "temporary": kind == "simulator", "owner": owner, "worktree": worktree,
        "label": label, "createdAt": iso(now), "expiresAt": expiry(),
    }


def new_claim_id() -> str:
    existing = claim_ids_on_disk()
    while True:
        claim_id = secrets.token_hex(4)
        if claim_id not in existing:
            return claim_id


def spec_matches(claim: Claim, args: argparse.Namespace, target: Optional[Tuple[Device, Device]]) -> bool:
    if args.device_id:
        return claim.get("kind") == "physical" and str(claim.get("udid") or "").upper() == args.device_id.upper()
    if target is None:  # a plain claim means a simulator; physical claims come back only with --device-id
        return claim.get("kind") == "simulator"
    device_type, runtime = target
    if claim.get("kind") != "simulator" or str(claim.get("model", "")).lower() != str(device_type["name"]).lower():
        return False
    if args.os and not version_matches(claim.get("os"), args.os):
        return False
    if not args.os and claim.get("os") != runtime.get("version"):
        return False
    return not args.runtime_build or claim.get("runtimeBuild") == args.runtime_build


def reuse_claim(args: argparse.Namespace, owner: Any, worktree: str, label: str, target: Any) -> Optional[Claim]:
    with registry_lock():
        candidates = [
            claim for claim in load_claims()
            if claim.get("status") == "ready" and is_mine(claim, owner, worktree, label) and spec_matches(claim, args, target)
        ]
        if not candidates:
            return None
        claim = max(candidates, key=lambda item: str(item.get("createdAt", "")))
        claim["expiresAt"] = expiry()
        save_claim(claim)
    if claim["kind"] != "simulator" or args.no_boot:
        return claim
    if not any(device["udid"] == claim.get("udid") for device in list_devices()):
        note(f"note: simulator {claim.get('udid')} of claim {claim['id']} is gone; creating a new one")
        with registry_lock():
            drop_claim(claim["id"])
        return None
    boot(claim["udid"])
    if not claim.get("runtimeBuild"):
        claim["runtimeBuild"] = read_runtime_build(claim["udid"])
        with registry_lock():
            save_claim(claim)
    return claim


def create_simulator(args: argparse.Namespace, owner: Any, worktree: str, label: str, target: Any) -> Claim:
    device_type, runtime = target
    with registry_lock():
        claim = base_claim(new_claim_id(), "simulator", owner, worktree, label)
        claim.update(
            name=f"{PREFIX}{claim['id']} {device_type['name']} {runtime['version']}",
            model=device_type["name"], deviceTypeIdentifier=device_type["identifier"],
            os=runtime["version"], runtimeIdentifier=runtime["identifier"],
        )
        save_claim(claim)
    udid = None
    try:
        output = xcrun("simctl", "create", claim["name"], device_type["identifier"], runtime["identifier"]).stdout
        udid = (output.strip().splitlines() or [""])[-1].strip()
        if not UUID_NAME.match(udid):
            raise Failure(f"simctl create printed no device UDID: {output.strip()!r}", 1)
        claim.update(udid=udid, destination=f"platform=iOS Simulator,id={udid}")
        with registry_lock():
            save_claim(claim)
        if not args.no_boot:
            boot(udid)
            claim["runtimeBuild"] = read_runtime_build(udid)
            if args.runtime_build and claim["runtimeBuild"] != args.runtime_build:
                raise blocked(
                    f"CoreSimulator booted iOS {runtime['version']} build {claim['runtimeBuild']}, not "
                    f"{args.runtime_build} (both builds share {runtime['identifier']} and CoreSimulator picks one); "
                    "the simulator was deleted"
                )
        claim["status"] = "ready"
        with registry_lock():
            save_claim(claim)
    except BaseException:
        try:
            if udid:
                remove_simulator(udid)
            with registry_lock():
                drop_claim(claim["id"])
        except Exception as error:  # keep the original failure visible
            note(f"warning: could not undo claim {claim['id']}: {error}")
        raise
    return claim


def claim_physical(args: argparse.Namespace, owner: Any, worktree: str, label: str) -> Tuple[Claim, bool]:
    wanted = args.device_id.strip().upper()
    device = next((d for d in core_devices() if wanted in {d["identifier"].upper(), (d["udid"] or "").upper()}), None)
    if device is None:
        raise blocked(f"no device with ID {args.device_id}; check `xcrun devicectl list devices`")
    if device["reality"] != "physical":
        raise Failure(
            f"{args.device_id} is a simulator; simulators are created per task, so run claim without "
            "--device-id (use --model/--os instead)"
        )
    if not device["udid"]:
        raise Failure(f"devicectl reports no hardware UDID for {args.device_id}", 1)
    ids = {device["identifier"].upper(), device["udid"].upper()}
    with registry_lock():
        for claim in load_claims():
            if claim.get("kind") != "physical" or str(claim.get("udid") or "").upper() not in ids:
                continue
            if claim.get("status") == "ready" and is_mine(claim, owner, worktree, label):
                claim["expiresAt"] = expiry()
                save_claim(claim)
                return claim, True
            holder = claim.get("owner") or {}
            raise blocked(
                f"{device['name'] or args.device_id} is held by claim {claim['id']} (owner pid {holder.get('pid')}, "
                f"worktree {claim.get('worktree')}, label {claim.get('label')!r})"
            )
        lease = legacy_holder(ids)
        if lease:
            raise blocked(f"{device['name'] or args.device_id} is held by a legacy lane lease: {lease}")
        claim = base_claim(new_claim_id(), "physical", owner, worktree, label)
        claim.update(
            status="ready", name=device["name"], udid=device["udid"], model=device["model"], os=device["os"],
            runtimeBuild=device["build"], destination=f"platform={device['platform']},id={device['udid']}",
        )
        save_claim(claim)
    return claim, False


def print_claim(claim: Claim, reused: bool, as_json: bool) -> None:
    if as_json:
        print(json.dumps({**claim, "reused": reused}, indent=2, sort_keys=True))
        return
    print(f"claim {claim['id']}")
    print(f"udid {claim['udid']}")
    print(f"destination {claim['destination']}")
    print(f"device {claim['model']}, iOS {claim['os']} ({claim.get('runtimeBuild') or 'build not read yet'})")
    print(f"reused {'yes' if reused else 'no'}")
    print(f"expires {claim['expiresAt']}")


def command_claim(args: argparse.Namespace) -> int:
    if args.device_id and (args.model or args.os or args.runtime_build):
        raise Failure("--device-id cannot be combined with --model, --os, or --runtime-build")
    if args.no_boot and args.runtime_build:
        raise Failure("--runtime-build needs a boot to read the build; drop --no-boot")
    owner, worktree, label = identity(args)
    if owner is None:
        note("warning: no claude or codex ancestor process found; claim relies on the 12-hour expiry; "
             "pass --owner-pid, or a --label unique to this task")
    auto_cleanup()
    wants_spec = bool(args.model or args.os or args.runtime_build)
    target = resolve_target(args.model, args.os, args.runtime_build) if wants_spec else None
    claim = reuse_claim(args, owner, worktree, label, target)
    reused = claim is not None
    if claim is None and args.device_id:
        claim, reused = claim_physical(args, owner, worktree, label)
    elif claim is None:
        claim = create_simulator(args, owner, worktree, label, target or resolve_target(None, None, None))
    booted = booted_count()
    if booted is not None and booted > BUSY_BOOTED_COUNT:
        note(f"note: {booted} simulators are booted on this Mac; expect slower boots and tests")
    print_claim(claim, reused, args.json)
    return 0


# --- release, list, cleanup commands ----------------------------------------------------


def command_release(args: argparse.Namespace) -> int:
    owner, worktree, label = identity(args)
    now = utc_now()
    with registry_lock():
        claims = load_claims()
        if args.claim:
            selected = [claim for claim in claims if claim["id"] in set(args.claim)]
            for missing in sorted(set(args.claim) - {claim["id"] for claim in selected}):
                note(f"note: no claim {missing}")
        else:
            selected = [claim for claim in claims if is_mine(claim, owner, worktree, label)]
        for claim in selected:
            other = claim.get("owner")
            if other and not same_owner(other, owner):
                reason = abandon_reason(claim, now)
                if reason is None:
                    raise Failure(
                        f"claim {claim['id']} belongs to process {other.get('pid')} ({other.get('command')}), "
                        "which is still running or cannot be checked; only its owner can release it"
                    )
                note(f"note: releasing claim {claim['id']} of another owner ({reason})")
        for claim in selected:
            claim["status"] = "releasing"
            save_claim(claim)
    if any(claim.get("kind") == "simulator" for claim in selected):
        devices = list_devices()
        try:
            clones = clone_devices()
        except Failure as error:
            note(f"warning: XCTest clones not listed: {error}")
            clones = []
        for claim in selected:
            destroy(claim, devices, clones)
    with registry_lock():
        for claim in selected:
            drop_claim(claim["id"])
    report = auto_cleanup()
    if args.json:
        print(json.dumps({"released": selected, "cleanup": report}, indent=2, sort_keys=True))
    elif not selected:
        print("no claims to release")
    else:
        for claim in selected:
            print(f"released {claim['id']} ({claim.get('name')}, {claim.get('udid')})")
    return 0


def command_list(args: argparse.Namespace) -> int:
    now = utc_now()
    devices, clones = list_devices(), clone_devices()
    known = claim_ids_on_disk()
    claims = load_claims()
    if args.mine:
        owner, worktree, label = identity(args)
        claims = [claim for claim in claims if is_mine(claim, owner, worktree, label)]
    rows = []
    for claim in sorted(claims, key=lambda item: str(item.get("createdAt", ""))):
        owner = claim.get("owner")
        alive = owner_alive(owner) if owner else None
        rows.append({**claim, "ownerAlive": alive, "abandoned": abandon_reason(claim, now) is not None})
    orphans = [
        {"udid": d["udid"], "name": d["name"], "state": d.get("state")}
        for d in devices if AGENT_NAME.match(d["name"]) and claim_id_of(d["name"]) not in known
    ]
    booted = sum(1 for device in devices + clones if is_booted(device))
    if args.json:
        print(json.dumps({"claims": rows, "orphanSimulators": orphans, "bootedSimulators": booted}, indent=2, sort_keys=True))
        return 0
    print(f"{len(rows)} claim{'s' if len(rows) != 1 else ''}")
    for row in rows:
        owner = row.get("owner") or {}
        alive = {True: "alive", False: "gone", None: "unknown"}[row["ownerAlive"]] if owner else "none"
        print(f"{row['id']}  {row.get('kind')}  {row.get('status')}  {row.get('name')}  {row.get('udid')}")
        print(f"  device {row.get('model')}, iOS {row.get('os')} ({row.get('runtimeBuild') or 'build not read yet'})")
        print(f"  owner {owner.get('pid', '-')} {alive}  worktree {row.get('worktree')}  label {row.get('label', '')!r}")
        print(f"  expires {row.get('expiresAt')}  abandoned {'yes' if row['abandoned'] else 'no'}")
    print("orphan agent-sim simulators: " + (", ".join(f"{o['name']} ({o['udid']})" for o in orphans) or "none"))
    print(f"booted simulators: {booted}")
    return 0


def command_cleanup(args: argparse.Namespace) -> int:
    if args.older_than_days < 1:
        raise Failure("--older-than-days must be at least 1")
    report = run_cleanup(apply=args.apply, older_than_days=args.older_than_days, generic=True)
    if args.json:
        print(json.dumps({"apply": args.apply, **report}, indent=2, sort_keys=True))
        return 0
    lines = describe_cleanup(report, applied=args.apply)
    for line in lines or ["nothing to clean up"]:
        print(line)
    if lines and not args.apply:
        print("dry run: pass --apply to do this")
    return 0


# --- command line -----------------------------------------------------------------------


def add_identity(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--owner-pid", type=int, help="agent process that owns the claim (default: nearest claude/codex ancestor)")
    parser.add_argument("--worktree", help="worktree key (default: git top level of the current folder, else the folder)")
    parser.add_argument("--label", default="", help="separates claims of one owner in one worktree (default: empty)")


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = root.add_subparsers(dest="command", metavar="command")
    commands.required = True

    claim = commands.add_parser(
        "claim", help="reuse this task's claim or create and boot a fresh simulator",
        description="Reuse the claim of this owner, worktree, and label, or create and boot a fresh "
        "agent-sim simulator. With --device-id, claim a physical device instead.",
    )
    claim.add_argument("--model", help=f"simulator model name (default {DEFAULT_MODEL!r})")
    claim.add_argument("--os", help="iOS version, e.g. 27.0; 27 means the newest 27.x (default: newest installed)")
    claim.add_argument("--runtime-build", help="required runtime build, e.g. 24A434; checked after boot")
    claim.add_argument("--device-id", help="physical device CoreDevice identifier or hardware UDID")
    claim.add_argument("--no-boot", action="store_true", help="create without booting (not with --runtime-build)")
    claim.add_argument("--json", action="store_true", help="print the claim record as JSON")
    add_identity(claim)
    claim.set_defaults(handler=command_claim)

    release = commands.add_parser(
        "release", help="delete this task's simulators and their XCTest clones, then clean up",
        description="Release claims: delete each claimed simulator and its XCTest clones; for physical "
        "devices only the claim is removed. Default: all claims of this owner, worktree, and label.",
    )
    release.add_argument("--claim", action="append", metavar="ID", help="claim ID to release (repeatable)")
    release.add_argument("--json", action="store_true", help="print released claims as JSON")
    add_identity(release)
    release.set_defaults(handler=command_release)

    listing = commands.add_parser(
        "list", help="show claims, orphan agent-sim simulators, and the booted count (read only)",
        description="Show claims, orphan agent-sim simulators, and how many simulators are booted. Changes nothing.",
    )
    listing.add_argument("--mine", action="store_true", help="only claims of this owner, worktree, and label")
    listing.add_argument("--json", action="store_true", help="print JSON")
    add_identity(listing)
    listing.set_defaults(handler=command_list)

    cleanup = commands.add_parser(
        "cleanup", help="report (or with --apply remove) abandoned claims, orphans, and stale XCTest clones",
        description="Dry run by default. Targets abandoned claims, agent-sim simulators without a claim, and "
        "shut-down XCTest clones whose agent-sim source has no live claim or that are older than N days.",
    )
    cleanup.add_argument("--apply", action="store_true", help="delete what the dry run reports")
    cleanup.add_argument("--older-than-days", type=int, default=MAINTENANCE_DAYS, help="age for generic XCTest clones (default 7)")
    cleanup.add_argument("--json", action="store_true", help="print JSON")
    cleanup.set_defaults(handler=command_cleanup)
    return root


def main(argv: Optional[List[str]] = None) -> int:
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # run the undo path in create_simulator
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(129))  # a closed terminal or PTY
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except Failure as failure:
        print(f"{failure.prefix}: {failure}", file=sys.stderr)
        return failure.code
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
