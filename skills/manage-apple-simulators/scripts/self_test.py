#!/usr/bin/env python3
"""Self-test simulators.py against a fake xcrun and real short-lived owner processes.

No real simulator is created, booted, or deleted. Run: python3 scripts/self_test.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

SCRIPT = Path(__file__).resolve().parent / "simulators.py"
AGENT_NAME = re.compile(r"^agent-sim [0-9a-f]{8} ")
HUMAN_AGENT_NAMES = ["agent-sim playground iPad", "agent-sim test"]  # named by a person; never deleted
KEPT_NAMES = {"iPhone 17 Pro", "My Test Phone", *HUMAN_AGENT_NAMES}
IOS27 = "com.apple.CoreSimulator.SimRuntime.iOS-27-0"
IOS26 = "com.apple.CoreSimulator.SimRuntime.iOS-26-5"
PRO = "com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro"
PHYS_A, PHYS_A_HW = "FF186CEE-D499-5425-A02E-C4642257354E", "00008140-00010D9A2E10801C"
PHYS_B, PHYS_B_HW = "7B69E2C3-E7EB-5052-BA15-B29FD9CDE8ED", "00008030-000A4D291191802E"
SIM_CORE = "1D35B34F-756C-4085-A973-ABB03B5E5BCB"
UNKNOWN = "99999999-9999-4999-8999-999999999999"
OLD = time.time() - 30 * 86400

FAKE_XCRUN = r'''#!/usr/bin/env python3
import fcntl, json, os, shutil, sys, time, uuid
from pathlib import Path

STATE = Path(os.environ["FAKE_XCRUN_STATE"])


def handle(state, args):
    if args[:3] == ["devicectl", "list", "devices"] and "--json-output" in args:
        payload = {"info": {"outcome": "success", "jsonVersion": 5}, "result": {"devices": state["coreDevices"]}}
        Path(args[args.index("--json-output") + 1]).write_text(json.dumps(payload))
        return 0, "", ""
    if args[:1] != ["simctl"]:
        return 64, "", "unexpected xcrun call: %s" % args
    args, set_path = args[1:], None
    if args[:1] == ["--set"]:
        set_path, args = args[1], args[2:]
        if args[:1] == ["list"] and os.environ.get("FAKE_XCRUN_FAIL_SET_LIST"):
            return 1, "", "Invalid device set: %s" % set_path
    devices = state["sets"].setdefault(set_path, {}) if set_path else state["devices"]
    if args[:2] == ["list", "-j"]:
        if args[2] == "devicetypes":
            return 0, json.dumps({"devicetypes": state["devicetypes"]}), ""
        if args[2] == "runtimes":
            return 0, json.dumps({"runtimes": state["runtimes"]}), ""
        groups = {}
        for udid, device in devices.items():
            groups.setdefault(device["runtime"], []).append(
                {"udid": udid, "name": device["name"], "state": device["state"], "isAvailable": True}
            )
        return 0, json.dumps({"devices": groups}), ""
    command, rest = args[0], args[1:]
    if command == "create" and not set_path:
        name, type_id, runtime_id = rest
        if type_id not in [t["identifier"] for t in state["devicetypes"]]:
            return 162, "", "Invalid device type: " + type_id
        udid = str(uuid.uuid4()).upper()
        devices[udid] = {"name": name, "runtime": runtime_id, "state": "Shutdown"}
        return 0, udid + "\n", ""
    device = devices.get(rest[0] if rest else "")
    if device is None:
        return 148, "", "Invalid device: %s" % (rest[:1],)
    if command == "boot":
        if device["state"] == "Booted":
            return 149, "", "Unable to boot device in current state: Booted"
        device["state"] = "Booted"
        return 0, "", ""
    if command == "bootstatus" and "-b" in rest:
        device["state"] = "Booted"
        return 0, "Device already booted\n", ""
    if command == "shutdown":
        if device["state"] != "Booted":
            return 149, "", "Unable to shutdown device in current state: Shutdown"
        device["state"] = "Shutdown"
        return 0, "", ""
    if command == "delete":
        if device["state"] == "Booted":
            return 149, "", "Unable to delete a device in current state: Booted"
        del devices[rest[0]]
        if set_path:
            shutil.rmtree(os.path.join(set_path, rest[0]), ignore_errors=True)
        return 0, "", ""
    if command == "getenv" and rest[1:] == ["SIMULATOR_RUNTIME_BUILD_VERSION"] and device["state"] == "Booted":
        return 0, state["actualBuilds"][device["runtime"]] + "\n", ""
    return 64, "", "unexpected simctl call: %s" % args


if sys.argv[1:3] == ["simctl", "bootstatus"] and os.environ.get("FAKE_BOOT_MARKER"):
    Path(os.environ["FAKE_BOOT_MARKER"]).write_text("booting")  # a slow first boot, for the signal tests
    time.sleep(60)
with open(str(STATE) + ".lock", "a+") as lock:
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    state = json.loads(STATE.read_text())
    state["calls"].append(sys.argv[1:])
    code, out, err = handle(state, sys.argv[1:])
    STATE.write_text(json.dumps(state, indent=1))
sys.stdout.write(out)
sys.stderr.write(err)
raise SystemExit(code)
'''

# Fakes the process tree above the test process from FAKE_PS_TREE (pid -> [ppid, lstart, command]);
# every other pid goes to the real ps.
FAKE_PS = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
fields, pid = args[1], args[3]
tree = json.loads(os.environ["FAKE_PS_TREE"])
if pid in tree:
    ppid, start, command = tree[pid]
    print({"lstart=": start, "lstart=,comm=": start + " " + command,
           "ppid=,lstart=,comm=": ppid + " " + start + " " + command}[fields])
else:
    os.execv("/bin/ps", ["ps"] + args)
'''

# What a sandboxed agent sees: macOS refuses to run the setuid /bin/ps.
PS_DENIED = "#!/bin/sh\necho 'ps: Operation not permitted' >&2\nexit 126\n"


def device_type(name: str, identifier: str, family: str) -> Dict[str, str]:
    return {"name": name, "identifier": identifier, "productFamily": family}


def core_device(identifier: str, hardware: Dict[str, str], name: str, modern: bool) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"identifier": identifier, "hardwareProperties": hardware,
                             "deviceProperties": {"name": name, "osVersionNumber": "27.0", "osBuildUpdate": "24A437"}}
    if modern:
        entry["properties"] = {
            "hardware": hardware, "state": {"name": name},
            "software": {"osVersionNumber": {"stringValue": "27.0"},
                         "osBuildVersions": {"buildVersion": {"name": "24A437"}}},
        }
    return entry


def initial_state() -> Dict[str, Any]:
    types = [
        device_type("iPhone 17 Pro", PRO, "iPhone"),
        device_type("iPhone 17", "com.apple.CoreSimulator.SimDeviceType.iPhone-17", "iPhone"),
        device_type("Apple Watch Ultra 4 (49mm)", "com.apple.CoreSimulator.SimDeviceType.Watch", "Apple Watch"),
    ]
    supported = [{"identifier": t["identifier"], "name": t["name"]} for t in types[:2]]

    def runtime(identifier: str, version: str, build: str, platform: str = "iOS", available: bool = True) -> Dict[str, Any]:
        return {"identifier": identifier, "version": version, "buildversion": build, "platform": platform,
                "isAvailable": available, "supportedDeviceTypes": supported}

    phone = {"platform": "iOS", "reality": "physical", "marketingName": "iPhone 16 Pro Max"}
    return {
        "calls": [],
        "devicetypes": types,
        "runtimes": [
            runtime(IOS26, "26.5", "23F77"),
            runtime(IOS27, "27.0", "24A5390f"),
            runtime(IOS27, "27.0", "24A434"),
            runtime("com.apple.CoreSimulator.SimRuntime.watchOS-27-0", "27.0", "24R5325f", platform="watchOS"),
            runtime("com.apple.CoreSimulator.SimRuntime.iOS-28-0", "28.0", "25A1", available=False),
        ],
        "actualBuilds": {IOS27: "24A434", IOS26: "23F77"},
        "devices": {
            "AAAAAAAA-0000-4000-8000-000000000001": {"name": "iPhone 17 Pro", "runtime": IOS27, "state": "Booted"},
            "AAAAAAAA-0000-4000-8000-000000000002": {"name": "My Test Phone", "runtime": IOS26, "state": "Shutdown"},
            "AAAAAAAA-0000-4000-8000-000000000003": {"name": HUMAN_AGENT_NAMES[1], "runtime": IOS27, "state": "Booted"},
            "AAAAAAAA-0000-4000-8000-000000000004": {"name": HUMAN_AGENT_NAMES[0], "runtime": IOS27, "state": "Shutdown"},
        },
        "sets": {},
        "coreDevices": [
            "not a device",
            {"identifier": 5},
            {"identifier": "BROKEN", "properties": "bad", "hardwareProperties": ["bad"]},
            core_device(PHYS_A, {**phone, "udid": PHYS_A_HW}, "Test iPhone", modern=True),
            core_device(PHYS_B, {**phone, "udid": PHYS_B_HW}, "Leased iPhone", modern=False),
            core_device(SIM_CORE, {"platform": "iOS", "reality": "simulated", "udid": SIM_CORE}, "iPhone 17", modern=True),
        ],
    }


class Harness:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.checks = 0
        self.serial = 100
        self.owners: List[subprocess.Popen] = []
        self.fake_state = root / "fake-xcrun.json"
        self.fake_state.write_text(json.dumps(initial_state()))
        self.xctest = root / "XCTestDevices"
        self.xctest.mkdir()
        self.legacy = root / "legacy-leases"
        self.legacy.mkdir()
        (self.legacy / "0F0F0F0F-1111-4111-8111-111111111111.json").write_text(
            json.dumps({"deviceIdentifier": PHYS_B, "destinationIdentifier": PHYS_B_HW, "owner": "old-task"})
        )
        (self.legacy / "pool.json").write_text(json.dumps({"deviceIdentifiers": [PHYS_A]}))
        self.state = root / "state"
        tools = root / "tools"
        tools.mkdir()
        for name, body in (("xcrun", FAKE_XCRUN), ("ps", FAKE_PS), ("ps-denied", PS_DENIED)):
            (tools / name).write_text(body)
            (tools / name).chmod(0o755)
        self.fake_ps = str(tools / "ps")
        self.ps_denied = str(tools / "ps-denied")
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("APPLE_SIMULATORS_")}
        self.env.update(
            APPLE_SIMULATORS_STATE=str(self.state), APPLE_SIMULATORS_XCRUN=str(tools / "xcrun"),
            APPLE_SIMULATORS_XCTEST_SET=str(self.xctest), APPLE_SIMULATORS_LEGACY_LEASES=str(self.legacy),
            FAKE_XCRUN_STATE=str(self.fake_state),
        )

    def check(self, condition: Any, message: str) -> None:
        self.checks += 1
        if not condition:
            raise AssertionError(message)

    def owner(self) -> int:
        process = subprocess.Popen(["sleep", "600"])
        self.owners.append(process)
        return process.pid

    def kill(self, pid: int) -> None:
        for process in self.owners:
            if process.pid == pid:
                process.kill()
                process.wait()

    def worktree(self, name: str) -> str:
        path = self.root / name
        path.mkdir(exist_ok=True)
        return str(path.resolve())

    def run(self, *args: str, expect: int = 0, env: Any = None) -> subprocess.CompletedProcess:
        result = subprocess.run([sys.executable, str(SCRIPT), *args], env=env or self.env,
                                capture_output=True, text=True, timeout=120, check=False)
        if result.returncode != expect:
            raise AssertionError(f"{' '.join(args)}: expected exit {expect}, got {result.returncode}\n"
                                 f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.checks += 1
        return result

    def run_json(self, *args: str, env: Any = None) -> Any:
        return json.loads(self.run(*args, "--json", env=env).stdout)

    def claim(self, owner: int, worktree: str, *extra: str, env: Any = None) -> Dict[str, Any]:
        return self.run_json("claim", "--owner-pid", str(owner), "--worktree", worktree, *extra, env=env)

    def claim_fails(self, owner: int, worktree: str, code: int, *extra: str) -> str:
        return self.run("claim", "--owner-pid", str(owner), "--worktree", worktree, *extra, expect=code).stderr

    def release(self, owner: int, worktree: str, *extra: str, env: Any = None) -> Dict[str, Any]:
        return self.run_json("release", "--owner-pid", str(owner), "--worktree", worktree, *extra, env=env)

    def fake(self) -> Dict[str, Any]:
        return json.loads(self.fake_state.read_text())

    def edit_fake(self, change: Callable[[Dict[str, Any]], None]) -> None:
        state = self.fake()
        change(state)
        self.fake_state.write_text(json.dumps(state))

    def devices(self) -> Dict[str, Dict[str, Any]]:
        return self.fake()["devices"]

    def clones(self) -> Dict[str, Dict[str, Any]]:
        return self.fake()["sets"].get(str(self.xctest), {})

    def names(self) -> List[str]:
        return sorted(device["name"] for device in self.devices().values())

    def agent_names(self) -> List[str]:
        return [name for name in self.names() if AGENT_NAME.match(name)]

    def clone_names(self) -> List[str]:
        return sorted(device["name"] for device in self.clones().values())

    def add_clone(self, name: str, state: str = "Shutdown", old: bool = False) -> str:
        udid = self.new_udid("CCCCCCCC")
        self.edit_fake(lambda s: s["sets"].setdefault(str(self.xctest), {}).update(
            {udid: {"name": name, "runtime": IOS27, "state": state}}))
        folder = self.xctest / udid
        folder.mkdir()
        if old:
            os.utime(folder, (OLD, OLD))
        return udid

    def add_device(self, name: str, state: str) -> None:
        udid = self.new_udid("DDDDDDDD")
        self.edit_fake(lambda s: s["devices"].update({udid: {"name": name, "runtime": IOS27, "state": state}}))

    def new_udid(self, head: str) -> str:
        self.serial += 1
        return f"{head}-0000-4000-8000-{self.serial:012d}"

    def claim_ids(self) -> List[str]:
        return sorted(path.stem for path in (self.state / "claims").glob("*.json"))

    def edit_claim(self, claim_id: str, **fields: Any) -> None:
        path = self.state / "claims" / f"{claim_id}.json"
        path.write_text(json.dumps({**json.loads(path.read_text()), **fields}))

    def snapshot(self) -> Any:
        state = self.fake()
        state.pop("calls")
        claims = {path.name: path.read_text() for path in (self.state / "claims").glob("*.json")}
        return state, claims


def tree_snapshot(folder: Path) -> Dict[str, Any]:
    return {str(path.relative_to(folder)): (path.read_bytes() if path.is_file() else None, path.stat().st_mtime_ns)
            for path in [folder, *folder.rglob("*")]}


def test_claims(h: Harness, a: int, b: int) -> Dict[str, Dict[str, Any]]:
    wt_a, wt_b, wt_c = h.worktree("wt-a"), h.worktree("wt-b"), h.worktree("wt-c")
    a1 = h.claim(a, wt_a)
    h.check(not a1["reused"] and a1["kind"] == "simulator" and a1["status"] == "ready" and a1["temporary"], "default claim")
    h.check(a1["name"] == f"agent-sim {a1['id']} iPhone 17 Pro 27.0", f"claim name: {a1['name']}")
    h.check((a1["model"], a1["os"], a1["runtimeIdentifier"]) == ("iPhone 17 Pro", "27.0", IOS27), "default model and newest OS")
    h.check(a1["runtimeBuild"] == "24A434", "claim records the build CoreSimulator booted")
    h.check(a1["destination"] == f"platform=iOS Simulator,id={a1['udid']}", "simulator destination")
    h.check(a1["owner"]["pid"] == a and a1["owner"]["startedAt"] and a1["worktree"] == wt_a and a1["label"] == "", "owner")
    h.check(h.devices()[a1["udid"]] == {"name": a1["name"], "runtime": IOS27, "state": "Booted"}, "simulator created and booted")
    h.check(a1["id"] in h.claim_ids() and (h.state / "maintenance.json").is_file(), "claim file and maintenance written")

    again = h.claim(a, wt_a)
    h.check(again["reused"] and again["id"] == a1["id"], "same owner, worktree, and label reuse the claim")
    h.check(again["expiresAt"] > a1["expiresAt"], "reuse refreshes the 12-hour expiry")
    same_spec = h.claim(a, wt_a, "--model", "iphone 17 pro", "--os", "27")
    h.check(same_spec["reused"] and same_spec["id"] == a1["id"], "matching --model/--os reuses the claim")
    text = h.run("claim", "--owner-pid", str(a), "--worktree", wt_a).stdout
    for line in (f"claim {a1['id']}", f"udid {a1['udid']}", f"destination {a1['destination']}",
                 "device iPhone 17 Pro, iOS 27.0 (24A434)", "reused yes", "expires "):
        h.check(line in text, f"text output has {line!r}:\n{text}")
    h.check(len(h.agent_names()) == 1, "reuse creates no simulator")

    a2 = h.claim(a, wt_a, "--label", "ui")
    a3 = h.claim(a, wt_b)
    a4 = h.claim(a, wt_a, "--os", "26.5")
    a5 = h.claim(a, wt_a, "--model", "iPhone 17")
    h.check(len({a1["id"], a2["id"], a3["id"], a4["id"], a5["id"]}) == 5, "label, worktree, and spec changes get new claims")
    h.check((a4["os"], a4["runtimeBuild"], a5["model"]) == ("26.5", "23F77", "iPhone 17"), "requested model and OS")

    for args in (("--os", "25"), ("--os", "28"), ("--model", "iPhone 99"), ("--runtime-build", "99Z999")):
        stderr = h.claim_fails(a, wt_c, 3, *args)
        h.check("blocked:" in stderr and "Xcode > Settings > Components" in stderr, f"missing {args} is blocked: {stderr}")
    before, creates = h.snapshot(), len(h.fake()["calls"])
    stderr = h.claim_fails(a, wt_c, 3, "--runtime-build", "24A5390f")
    h.check("24A434" in stderr, f"build mismatch names the booted build: {stderr}")
    h.check(h.snapshot() == before, "build mismatch leaves no simulator or claim behind")
    h.check(any(call[:2] == ["simctl", "create"] for call in h.fake()["calls"][creates:]), "mismatch did create, then undo")
    pinned = h.claim(a, wt_c, "--runtime-build", "24A434")
    h.check(pinned["runtimeBuild"] == "24A434", "matching --runtime-build")

    h.claim_fails(a, wt_c, 2, "--device-id", PHYS_A, "--model", "iPhone 17")
    h.claim_fails(a, wt_c, 2, "--no-boot", "--runtime-build", "24A434")
    h.run("claim", "--owner-pid", "999999", "--worktree", wt_c, expect=2)
    lazy = h.claim(a, wt_c, "--label", "nb", "--no-boot")
    h.check(h.devices()[lazy["udid"]]["state"] == "Shutdown" and lazy["runtimeBuild"] is None, "--no-boot")
    woken = h.claim(a, wt_c, "--label", "nb")
    h.check(woken["reused"] and h.devices()[lazy["udid"]]["state"] == "Booted" and woken["runtimeBuild"] == "24A434",
            "reusing a --no-boot claim boots it and reads the build")
    return {"a1": a1, "a2": a2, "a3": a3, "a4": a4, "a5": a5}


def test_release(h: Harness, a: int, b: int, claims: Dict[str, Dict[str, Any]]) -> None:
    wt_a = h.worktree("wt-a")
    a1, a2 = claims["a1"], claims["a2"]
    h.add_clone(f"Clone 1 of {a1['name']}", "Booted")
    h.add_clone(f"Clone 2 of {a1['name']}")
    h.add_clone(f"Clone 1 of {a2['name']}")
    kept = ["Clone 1 of iPhone 17 Pro", "Clone 2 of iPhone 17 Pro", "Clone 3 of iPhone 17 Pro", "Some Device"]
    h.add_clone(kept[0], "Booted", old=True)
    h.add_clone(kept[1])
    h.add_clone(kept[2], old=True)
    h.add_clone(kept[3], old=True)

    stderr = h.run("release", "--owner-pid", str(b), "--worktree", wt_a, "--claim", a1["id"], expect=2).stderr
    h.check("only its owner" in stderr and a1["id"] in h.claim_ids(), "release refuses another live owner")
    released = h.release(a, wt_a, "--claim", a1["id"])
    h.check([c["id"] for c in released["released"]] == [a1["id"]], "release --claim")
    h.check(a1["udid"] not in h.devices() and a1["id"] not in h.claim_ids(), "release deletes the simulator and claim")
    h.check(h.clone_names() == sorted([f"Clone 1 of {a2['name']}", *kept]), f"release deletes only its clones: {h.clone_names()}")
    h.check(a2["udid"] in h.devices() and KEPT_NAMES <= set(h.names()), "other simulators kept")

    released = h.release(a, wt_a)
    h.check(sorted(c["id"] for c in released["released"]) == sorted([claims["a4"]["id"], claims["a5"]["id"]]),
            "release without --claim takes owner + worktree + label")
    h.check(a2["id"] in h.claim_ids(), "release keeps claims with another label")
    out = h.run("release", "--owner-pid", str(a), "--worktree", wt_a).stdout
    h.check("no claims to release" in out, "nothing to release")


def test_abandoned(h: Harness, a: int, b: int, claims: Dict[str, Dict[str, Any]]) -> None:
    wt_d, wt_e, wt_z = h.worktree("wt-d"), h.worktree("wt-e"), h.worktree("wt-z")
    crashed_owner = h.owner()
    crashed = h.claim(crashed_owner, wt_d)
    h.kill(crashed_owner)
    h.run("claim", "--owner-pid", str(crashed_owner), "--worktree", wt_d, expect=2)
    stderr = h.run("claim", "--owner-pid", str(b), "--worktree", wt_d).stderr
    h.check(f"removed abandoned claim {crashed['id']} (owner process ended)" in stderr, f"dead owner cleanup: {stderr}")
    h.check(crashed["udid"] not in h.devices() and crashed["id"] not in h.claim_ids(), "dead owner's simulator deleted")

    a3 = claims["a3"]
    h.edit_claim(a3["id"], expiresAt="2020-01-01T00:00:00Z")
    h.release(b, wt_z)
    h.check(a3["udid"] not in h.devices() and a3["id"] not in h.claim_ids(), "expired claim cleaned on release")

    stale = h.claim(a, wt_e)
    h.edit_claim(stale["id"], expiresAt="2020-01-01T00:00:00Z")
    result = h.run("release", "--owner-pid", str(b), "--worktree", wt_e, "--claim", stale["id"])
    h.check(f"releasing claim {stale['id']} of another owner (expired)" in result.stderr
            and stale["id"] not in h.claim_ids(), f"expired claim of a live owner: {result.stderr}")

    # A claim left 'creating' by a killed claim (SIGKILL, host timeout) is never reused; clean it after 30 minutes.
    stuck, busy = h.claim(a, wt_e, "--label", "stuck"), h.claim(a, wt_e, "--label", "busy")
    h.edit_claim(stuck["id"], status="creating", createdAt="2020-01-01T00:00:00.000Z")
    h.edit_claim(busy["id"], status="creating")
    stderr = h.run("claim", "--owner-pid", str(b), "--worktree", wt_e).stderr
    h.check(f"removed abandoned claim {stuck['id']} (creation interrupted)" in stderr
            and stuck["udid"] not in h.devices() and stuck["id"] not in h.claim_ids(), f"stale 'creating' claim: {stderr}")
    h.check(busy["id"] in h.claim_ids() and busy["udid"] in h.devices(), "a fresh 'creating' claim of a live owner is kept")
    h.edit_claim(busy["id"], status="ready")
    h.release(a, wt_e, "--label", "busy")
    h.release(b, wt_e)


def test_cleanup(h: Harness, a: int, b: int, claims: Dict[str, Dict[str, Any]]) -> None:
    a2 = claims["a2"]
    h.add_device("agent-sim deadbeef iPhone 17 Pro 27.0", "Booted")
    h.add_clone("Clone 1 of agent-sim cafebabe iPhone 17 Pro 27.0")
    h.add_clone("Clone 2 of agent-sim cafebabe iPhone 17 Pro 27.0", "Booted")
    h.add_clone(f"Clone 1 of {HUMAN_AGENT_NAMES[1]}")

    before = h.snapshot()
    listing = h.run_json("list")
    h.check(h.snapshot() == before, "list changes nothing")
    h.check([o["name"] for o in listing["orphanSimulators"]] == ["agent-sim deadbeef iPhone 17 Pro 27.0"], "list orphans")
    booted = sum(d["state"] == "Booted" for d in [*h.devices().values(), *h.clones().values()])
    h.check(listing["bootedSimulators"] == booted, "list booted count")
    h.check(all(row["ownerAlive"] is True and row["abandoned"] is False for row in listing["claims"]), "list liveness")
    mine = h.run_json("list", "--mine", "--owner-pid", str(a), "--worktree", h.worktree("wt-a"), "--label", "ui")
    h.check([row["id"] for row in mine["claims"]] == [a2["id"]], "list --mine")
    h.check("booted simulators:" in h.run("list").stdout, "list text output")

    dry = h.run_json("cleanup")
    h.check(h.snapshot() == before, "cleanup dry run changes nothing")
    h.check(not dry["apply"] and [o["name"] for o in dry["orphanSimulators"]] == ["agent-sim deadbeef iPhone 17 Pro 27.0"],
            "dry run reports the orphan")
    h.check(sorted(c["name"] for c in dry["clones"]) == ["Clone 1 of agent-sim cafebabe iPhone 17 Pro 27.0",
                                                         "Clone 3 of iPhone 17 Pro"], f"dry run clones: {dry['clones']}")
    h.check("dry run: pass --apply" in h.run("cleanup").stdout, "dry run text output")
    h.run("cleanup", "--older-than-days", "0", expect=2)

    applied = h.run_json("cleanup", "--apply")
    h.check(applied["apply"] and "agent-sim deadbeef iPhone 17 Pro 27.0" not in h.names(), "cleanup --apply deletes orphans")
    h.check(h.clone_names() == sorted([
        f"Clone 1 of {a2['name']}", "Clone 1 of iPhone 17 Pro", "Clone 2 of agent-sim cafebabe iPhone 17 Pro 27.0",
        "Clone 2 of iPhone 17 Pro", "Some Device", f"Clone 1 of {HUMAN_AGENT_NAMES[1]}"]),
        f"cleanup keeps booted, fresh, live, and non-clone devices: {h.clone_names()}")
    h.check(KEPT_NAMES <= set(h.names()), f"cleanup keeps non-agent and person-named 'agent-sim' simulators: {h.names()}")

    h.add_clone("Clone 4 of iPhone 17 Pro", old=True)
    h.release(b, h.worktree("wt-z"))
    h.check("Clone 4 of iPhone 17 Pro" in h.clone_names(), "automatic cleanup skips generic clones until maintenance is due")
    (h.state / "maintenance.json").write_text(json.dumps({"lastGenericClonePruneAt": "2020-01-01T00:00:00Z"}))
    h.release(b, h.worktree("wt-z"))
    h.check("Clone 4 of iPhone 17 Pro" not in h.clone_names(), "automatic cleanup prunes old clones when due")
    last = json.loads((h.state / "maintenance.json").read_text())["lastGenericClonePruneAt"]
    h.check(not last.startswith("2020"), "maintenance time updated")

    # Automatic cleanup removes a shut-down orphan but only reports a running one (it may belong to an unseen claim).
    h.add_device("agent-sim 0badf00d iPhone 17 Pro 27.0", "Shutdown")
    h.add_device("agent-sim 0dd5eed5 iPhone 17 Pro 27.0", "Booted")
    stderr = h.run("claim", "--owner-pid", str(a), "--worktree", h.worktree("wt-a"), "--label", "ui").stderr
    h.check("agent-sim 0badf00d iPhone 17 Pro 27.0" not in h.names(), "automatic cleanup removes a shut-down orphan")
    h.check("agent-sim 0dd5eed5 iPhone 17 Pro 27.0" in h.names() and "kept running orphan simulator agent-sim 0dd5eed5" in stderr,
            f"automatic cleanup keeps and reports a running orphan: {stderr}")
    h.run("cleanup", "--apply")
    h.check("agent-sim 0dd5eed5 iPhone 17 Pro 27.0" not in h.names(), "cleanup --apply removes a running orphan")


def test_physical(h: Harness, a: int, b: int) -> None:
    wt_a, wt_b = h.worktree("wt-a"), h.worktree("wt-b")
    phone = h.claim(a, wt_a, "--device-id", PHYS_A)
    h.check(phone["kind"] == "physical" and not phone["temporary"] and phone["udid"] == PHYS_A_HW, "physical claim")
    h.check(phone["destination"] == f"platform=iOS,id={PHYS_A_HW}", "physical destination")
    h.check((phone["model"], phone["os"], phone["runtimeBuild"]) == ("iPhone 16 Pro Max", "27.0", "24A437"), "physical info")
    for device_id in (PHYS_A_HW.lower(), PHYS_A):
        again = h.claim(a, wt_a, "--device-id", device_id)
        h.check(again["reused"] and again["id"] == phone["id"], f"physical reuse by {device_id}")
    plain = h.claim(a, wt_a)
    h.check(plain["kind"] == "simulator" and not plain["reused"] and plain["id"] != phone["id"],
            "a plain claim after a physical claim gets a simulator, not the phone")
    h.check(h.claim(a, wt_a)["id"] == plain["id"], "a plain claim reuses the simulator claim")
    h.release(a, wt_a, "--claim", plain["id"])
    h.check("held by claim" in h.claim_fails(b, wt_b, 3, "--device-id", PHYS_A), "physical held by another claim")
    h.check("legacy" in h.claim_fails(a, wt_a, 3, "--device-id", PHYS_B), "physical held by a legacy lease")
    h.check("created per task" in h.claim_fails(a, wt_a, 2, "--device-id", SIM_CORE), "--device-id refuses simulators")
    h.claim_fails(a, wt_a, 3, "--device-id", UNKNOWN)
    released = h.release(a, wt_a, "--claim", phone["id"])
    h.check([c["id"] for c in released["released"]] == [phone["id"]], "physical release")
    touched = [c for c in h.fake()["calls"] if c[:1] == ["simctl"] and ({PHYS_A, PHYS_A_HW, PHYS_B_HW} & set(c))]
    h.check(not touched, f"physical devices never booted or deleted: {touched}")


def ps_tree(h: Harness, *ancestors: str) -> Dict[str, str]:
    """Env whose fake ps shows the test process as a shell under `ancestors` (nearest first), pids 4242 upward."""
    pids = [str(os.getpid())] + [str(4242 + index) for index in range(len(ancestors))]
    commands = ["/bin/zsh", *ancestors]
    tree = {pid: [pids[index + 1] if index + 1 < len(pids) else "1", "Thu Oct  1 13:25:40 2026", commands[index]]
            for index, pid in enumerate(pids)}
    return {**h.env, "APPLE_SIMULATORS_PS": h.fake_ps, "FAKE_PS_TREE": json.dumps(tree)}


def test_owner_detection(h: Harness, a: int, b: int) -> None:
    wt_f = h.worktree("wt-f")
    agent = "/Users/me/Library/Application Support/Codex/bin/codex"
    env = ps_tree(h, agent)
    found = h.run_json("claim", "--worktree", wt_f, env=env)
    h.check(found["owner"] == {"pid": 4242, "startedAt": "2026-10-01T13:25:40Z", "command": agent}, f"{found['owner']}")
    h.check(h.run_json("claim", "--worktree", wt_f, env=env)["reused"], "detected owner reuses its claim")
    h.check(len(h.run_json("release", "--worktree", wt_f, env=env)["released"]) == 1, "detected owner releases")

    # The real Claude desktop tree: zsh -> claude (Claude Code) -> disclaimer -> Claude (the app). The nearer wins.
    cli = "/Users/me/Library/Application Support/Claude/claude-code/2.1.284/claude.app/Contents/MacOS/claude"
    desktop = ps_tree(h, cli, "/Applications/Claude.app/Contents/Helpers/disclaimer",
                      "/Applications/Claude.app/Contents/MacOS/Claude")
    found = h.run_json("claim", "--worktree", wt_f, env=desktop)
    h.check(found["owner"]["pid"] == 4242 and found["owner"]["command"] == cli, f"nearest agent ancestor: {found['owner']}")
    h.check(len(h.run_json("release", "--worktree", wt_f, env=desktop)["released"]) == 1, "desktop tree release")

    none_env = ps_tree(h, "/usr/sbin/sshd")
    result = h.run("claim", "--worktree", wt_f, "--json", env=none_env)
    h.check(json.loads(result.stdout)["owner"] is None and "12-hour expiry" in result.stderr, "no agent ancestor warns")
    h.check(len(h.run_json("release", "--worktree", wt_f, env=none_env)["released"]) == 1, "ownerless release")

    via_env = h.run_json("claim", "--worktree", wt_f, env={**h.env, "APPLE_SIMULATORS_OWNER_PID": str(a)})
    h.check(via_env["owner"]["pid"] == a, "APPLE_SIMULATORS_OWNER_PID")
    h.release(a, wt_f)


def test_parallel_claims(h: Harness, a: int, b: int) -> None:
    runs = [subprocess.Popen([sys.executable, str(SCRIPT), "claim", "--json", "--owner-pid", str(owner),
                              "--worktree", h.worktree(name)], env=h.env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True) for owner, name in ((a, "wt-g"), (b, "wt-h"))]
    outputs = [run.communicate(timeout=120) for run in runs]
    h.check(all(run.returncode == 0 for run in runs), f"parallel claims succeed: {outputs}")
    udids = {json.loads(out)["udid"] for out, _ in outputs}
    h.check(len(udids) == 2 and udids <= set(h.devices()), "parallel claims get separate simulators")


def test_time_zones(h: Harness, a: int, b: int) -> None:
    """ps prints start times in the caller's time zone; another agent's TZ must never make a live owner look gone."""
    wt = h.worktree("wt-tz")
    plain = {key: value for key, value in h.env.items() if key != "TZ"}
    first = h.claim(a, wt, env=plain)
    for zone in ("UTC", "Asia/Kolkata", "America/New_York"):
        result = h.run("claim", "--owner-pid", str(b), "--worktree", wt, "--label", zone, env={**plain, "TZ": zone})
        h.check(first["id"] in h.claim_ids() and first["udid"] in h.devices() and "abandoned" not in result.stderr,
                f"a live claim survives another agent with TZ={zone}: {result.stderr}")
    again = h.claim(a, wt, env={**plain, "TZ": "Asia/Kolkata"})
    h.check(again["reused"] and again["id"] == first["id"], "the owner reuses its claim from another time zone")

    # Claims written before start times were stored in UTC hold ps's local time; they must stay alive too.
    zone = "Asia/Kolkata"
    local = subprocess.run(["ps", "-o", "lstart=", "-p", str(a)], env={**plain, "LC_ALL": "C", "TZ": zone},
                           capture_output=True, text=True, check=True).stdout
    h.edit_claim(first["id"], owner={**first["owner"], "startedAt": " ".join(local.split())})
    for other in ("America/New_York", "UTC"):
        h.run("claim", "--owner-pid", str(b), "--worktree", wt, "--label", "legacy", env={**plain, "TZ": other})
        h.check(first["id"] in h.claim_ids() and first["udid"] in h.devices(), f"an old local-time claim survives TZ={other}")
    listing = h.run_json("list", env={**plain, "TZ": "UTC"})
    row = next(row for row in listing["claims"] if row["id"] == first["id"])
    h.check(row["ownerAlive"] is True and row["abandoned"] is False, f"an old local-time claim lists as alive: {row}")
    again = h.claim(a, wt, env={**plain, "TZ": zone})
    h.check(again["reused"] and again["id"] == first["id"], "the owner reuses its old local-time claim")
    h.release(a, wt)
    for label in ("UTC", "Asia/Kolkata", "America/New_York", "legacy"):
        h.release(b, wt, "--label", label)
    h.check(first["id"] not in h.claim_ids() and first["udid"] not in h.devices(), "time-zone claims released")


def test_ps_failure(h: Harness, a: int, b: int) -> None:
    """A sandboxed agent cannot run the setuid /bin/ps. Unknown liveness must never delete another agent's simulator."""
    wt, wt_sandbox = h.worktree("wt-ps"), h.worktree("wt-ps-sandbox")
    live = h.claim(a, wt)
    denied = {**h.env, "APPLE_SIMULATORS_PS": h.ps_denied}
    ids, devices = set(h.claim_ids()), set(h.devices())
    result = h.run("claim", "--worktree", wt_sandbox, "--json", env=denied)
    h.check("ps failed" in result.stderr and json.loads(result.stdout)["owner"] is None, f"ps failure warns: {result.stderr}")
    h.check(ids <= set(h.claim_ids()) and devices <= set(h.devices()), "a claim with a failing ps touches no live claim")
    h.check(len(h.run_json("release", "--worktree", wt_sandbox, env=denied)["released"]) == 1, "sandboxed release")
    h.check(ids <= set(h.claim_ids()) and devices <= set(h.devices()), "a release with a failing ps touches no live claim")
    stderr = h.run("release", "--worktree", wt, "--claim", live["id"], expect=2, env=denied).stderr
    h.check("only its owner" in stderr and live["id"] in h.claim_ids(), f"release --claim refuses an unchecked owner: {stderr}")
    stderr = h.run("claim", "--owner-pid", str(a), "--worktree", wt, expect=1, env=denied).stderr
    h.check(f"ps failed; cannot check owner process {a}" in stderr, f"--owner-pid with a failing ps: {stderr}")
    text = h.run("list", env=denied).stdout
    h.check(f"owner {a} unknown" in text, f"list shows unknown liveness:\n{text}")
    h.edit_claim(live["id"], expiresAt="2020-01-01T00:00:00Z")
    h.run("cleanup", "--apply", env=denied)
    h.check(live["id"] not in h.claim_ids() and live["udid"] not in h.devices(), "expiry still applies when ps fails")


def test_cleanup_errors(h: Harness, a: int, b: int) -> None:
    """Automatic cleanup is housekeeping: its failures never block the caller's own claim or release."""
    wt = h.worktree("wt-err")
    first = h.claim(a, wt)
    h.add_clone(f"Clone 1 of {first['name']}")
    broken = {**h.env, "FAKE_XCRUN_FAIL_SET_LIST": "1"}
    result = h.run("claim", "--owner-pid", str(a), "--worktree", wt, "--json", env=broken)
    h.check(json.loads(result.stdout)["reused"] and "warning: automatic cleanup skipped" in result.stderr,
            f"a failing XCTest set listing still lets a claim be reused: {result.stderr}")
    result = h.run("release", "--owner-pid", str(a), "--worktree", wt, env=broken)
    h.check("XCTest clones not listed" in result.stderr and first["udid"] not in h.devices()
            and first["id"] not in h.claim_ids(), f"release still deletes the simulator: {result.stderr}")
    h.run("cleanup", "--apply")
    h.check(f"Clone 1 of {first['name']}" not in h.clone_names(), "the leftover clone is cleaned once listing works")


def test_renamed(h: Harness, a: int, b: int) -> None:
    wt = h.worktree("wt-rename")
    claim = h.claim(a, wt)
    h.edit_fake(lambda s: s["devices"][claim["udid"]].update(name="iPhone 17 Pro"))
    h.release(a, wt)
    h.check(claim["udid"] not in h.devices(), "release deletes a renamed claimed simulator by its UDID")
    h.check("AAAAAAAA-0000-4000-8000-000000000001" in h.devices(), "release keeps the real simulator with that name")


def test_signals(h: Harness, a: int, b: int) -> None:
    """A claim interrupted during the first boot deletes its simulator and claim."""
    wt = h.worktree("wt-signal")
    for sig, code in ((signal.SIGTERM, 143), (signal.SIGHUP, 129), (signal.SIGINT, 130)):
        marker = h.root / f"booting-{code}"
        ids, agents = h.claim_ids(), h.agent_names()
        run = subprocess.Popen([sys.executable, str(SCRIPT), "claim", "--owner-pid", str(a), "--worktree", wt],
                               env={**h.env, "FAKE_BOOT_MARKER": str(marker)}, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 60
        while not marker.exists() and run.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        h.check(marker.exists(), f"claim reached the first boot before {sig.name}")
        run.send_signal(sig)
        _, stderr = run.communicate(timeout=60)
        h.check(run.returncode == code, f"{sig.name} exits {code}, got {run.returncode}: {stderr}")
        h.check(h.claim_ids() == ids and h.agent_names() == agents, f"{sig.name} during boot leaves nothing behind")


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="manage-apple-simulators-")).resolve()
    h = Harness(root)
    legacy_before = tree_snapshot(h.legacy)
    try:
        a, b = h.owner(), h.owner()
        claims = test_claims(h, a, b)
        test_release(h, a, b, claims)
        test_abandoned(h, a, b, claims)
        test_cleanup(h, a, b, claims)
        test_physical(h, a, b)
        test_owner_detection(h, a, b)
        test_parallel_claims(h, a, b)
        test_time_zones(h, a, b)
        test_ps_failure(h, a, b)
        test_cleanup_errors(h, a, b)
        test_renamed(h, a, b)
        test_signals(h, a, b)
        h.check(tree_snapshot(h.legacy) == legacy_before, "legacy lease folder never written")

        for pid in (a, b):
            h.kill(pid)
        h.run("cleanup", "--apply")
        h.check(not h.claim_ids(), f"all abandoned claims removed: {h.claim_ids()}")
        h.check(not h.agent_names(), f"no agent-sim left: {h.names()}")
        h.check(KEPT_NAMES == set(h.names()), f"non-agent and person-named simulators untouched: {h.names()}")
        h.check("Clone 1 of iPhone 17 Pro" in h.clone_names(), "booted clone untouched")
    except AssertionError as error:
        print(f"self-test failed after {h.checks} checks: {error}", file=sys.stderr)
        print(f"fake state kept in {root}", file=sys.stderr)
        return 1
    finally:
        for process in h.owners:
            process.kill()
            process.wait()
    shutil.rmtree(root, ignore_errors=True)
    print(f"manage-apple-simulators self-test passed: {h.checks} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
