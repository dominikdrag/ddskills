#!/usr/bin/env python3
"""Forward-test device authority, lease isolation, and guarded commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
LANE = SCRIPT_DIR / "lane.py"
DEVICE_A = "11111111-1111-4111-8111-111111111111"
DEVICE_B = "22222222-2222-4222-8222-222222222222"
PHYSICAL_DEVICE = "33333333-3333-4333-8333-333333333333"
PHYSICAL_DESTINATION = "00008140-00010D9A2E10801C"
UNKNOWN_DEVICE = "99999999-9999-4999-8999-999999999999"


def device(
    identifier: str, name: str, reality: str, destination: str, state: str
) -> dict[str, object]:
    return {
        "identifier": identifier,
        "properties": {
            "connection": {
                "state": "connected" if state == "booted" else "disconnected"
            },
            "hardware": {
                "platform": "iOS",
                "reality": reality,
                "udid": destination,
            },
            "software": {"osVersionNumber": {"stringValue": "27.0"}},
            "state": {"bootState": state, "name": name},
        },
    }


def install_fake_tools(root: Path) -> Path:
    tool_dir = root / "fake-tools"
    tool_dir.mkdir()
    device_file = root / "devices.json"
    device_file.write_text(
        json.dumps(
            {
                "info": {"jsonVersion": 5, "outcome": "success", "version": "test"},
                "result": {
                    "devices": [
                        device(DEVICE_A, "Lane A", "simulated", DEVICE_A, "booted"),
                        device(DEVICE_B, "Lane B", "simulated", DEVICE_B, "shutdown"),
                        device(
                            PHYSICAL_DEVICE,
                            "Physical iPhone",
                            "physical",
                            PHYSICAL_DESTINATION,
                            "booted",
                        ),
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    xcrun = tool_dir / "xcrun"
    xcrun.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

arguments = sys.argv[1:]
if arguments[:3] == ["devicectl", "list", "devices"]:
    print(Path(os.environ["FAKE_DEVICE_FILE"]).read_text(encoding="utf-8"))
    raise SystemExit(0)
if arguments[:4] in (
    ["devicectl", "device", "install", "app"],
    ["devicectl", "device", "process", "launch"],
):
    output_option = "--json-output" if "--json-output" in arguments else "-j"
    output_path = Path(arguments[arguments.index(output_option) + 1])
    output_path.write_text(
        json.dumps({"info": {"outcome": "success"}}),
        encoding="utf-8",
    )
    print("device operation completed")
    raise SystemExit(0)
print(f"unexpected xcrun arguments: {arguments}", file=sys.stderr)
raise SystemExit(64)
""",
        encoding="utf-8",
    )
    xcrun.chmod(0o755)

    xcodebuild = tool_dir / "xcodebuild"
    xcodebuild.write_text(
        """#!/usr/bin/env python3
import os

print("TEST SUCCEEDED" if os.environ.get("FAKE_ZERO_TESTS") else "Executed 1 test")
""",
        encoding="utf-8",
    )
    xcodebuild.chmod(0o755)
    return device_file


def reserve(
    env: dict[str, str],
    root: Path,
    owner: str,
    identifier: str,
    suffix: str,
    *,
    device_hub_window: str | None = None,
) -> subprocess.Popen[str]:
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
        "--device-id",
        identifier,
        "--repo",
        str(repo),
        "--workspace",
        str(workspace),
        "--derived-data",
        str(evidence / "DerivedData"),
        "--evidence",
        str(evidence),
    ]
    if device_hub_window:
        command.extend(["--device-hub-window", device_hub_window])
    return subprocess.Popen(
        command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def run(
    *command: str, env: dict[str, str], expected: int
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, check=False
    )
    if result.returncode != expected:
        raise AssertionError(
            f"expected {expected}, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def gate_command(
    repo: Path,
    evidence: Path,
    destination: str,
    log_name: str,
    *,
    require_tests: bool = False,
) -> list[str]:
    command = [
        sys.executable,
        str(LANE),
        "run-xcodebuild",
        "--owner",
        "owner-a",
        "--device-id",
        DEVICE_A,
        "--log",
        str(evidence / log_name),
    ]
    if require_tests:
        command.append("--require-executed-tests")
    command.extend(
        [
            "--",
            "xcodebuild",
            "test",
            "-workspace",
            str(repo / "App-a2.xcworkspace"),
            "-destination",
            destination,
            "-derivedDataPath",
            str(evidence / "DerivedData"),
        ]
    )
    return command


def assert_no_legacy_tool() -> None:
    forbidden = "sim" + "ctl"
    for path in SKILL_DIR.rglob("*"):
        if path.suffix not in {".md", ".py", ".yaml", ".yml"}:
            continue
        if forbidden in path.read_text(encoding="utf-8").casefold():
            raise AssertionError(
                f"legacy device tool reference found in {path.relative_to(SKILL_DIR)}"
            )


def assert_no_fake_ui_evidence() -> None:
    forbidden = ("confirm-device" + "-hub", "deviceHub" + "Confirmations")
    for path in SKILL_DIR.rglob("*"):
        if path.suffix not in {".md", ".py", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                raise AssertionError(
                    f"fake UI evidence record found in {path.relative_to(SKILL_DIR)}"
                )


def assert_single_guard_entrypoint() -> None:
    removed_names = ("run_" + "gate.py", "run_" + "device.py")
    for name in removed_names:
        if (SCRIPT_DIR / name).exists():
            raise AssertionError(f"obsolete guard script still exists: {name}")
    for path in SKILL_DIR.rglob("*"):
        if path.suffix not in {".md", ".py", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for name in removed_names:
            if name in text:
                raise AssertionError(
                    f"obsolete guard reference found in {path.relative_to(SKILL_DIR)}"
                )


def main() -> int:
    assert_no_legacy_tool()
    assert_no_fake_ui_evidence()
    assert_single_guard_entrypoint()
    with tempfile.TemporaryDirectory(prefix="apple-lane-test-") as temporary:
        root = Path(temporary)
        device_file = install_fake_tools(root)
        env = os.environ.copy()
        env["CODEX_APPLE_LANE_STATE"] = str(root / "state")
        env["FAKE_DEVICE_FILE"] = str(device_file)
        env["PATH"] = f"{root / 'fake-tools'}{os.pathsep}{env['PATH']}"

        listed = run(sys.executable, str(LANE), "list", "--json", env=env, expected=0)
        inventory = json.loads(listed.stdout)
        if {item["kind"] for item in inventory["devices"]} != {"simulator", "physical"}:
            raise AssertionError(
                "inventory did not distinguish simulator and physical devices"
            )

        unknown = reserve(env, root, "owner-x", UNKNOWN_DEVICE, "unknown")
        if unknown.wait() != 2:
            raise AssertionError(
                "unknown device reservation did not fail closed: "
                f"{unknown.communicate()}"
            )
        unknown.communicate()

        contenders = [
            reserve(env, root, "owner-a", DEVICE_A, "a"),
            reserve(env, root, "owner-b", DEVICE_A, "b"),
        ]
        results = [(process.wait(), process.communicate()) for process in contenders]
        if sorted(code for code, _ in results) != [0, 2]:
            raise AssertionError(
                f"same-device race did not yield one winner: {results}"
            )
        winner = "owner-a" if results[0][0] == 0 else "owner-b"
        loser = "owner-b" if winner == "owner-a" else "owner-a"

        run(
            sys.executable,
            str(LANE),
            "release",
            "--owner",
            loser,
            "--device-id",
            DEVICE_A,
            env=env,
            expected=2,
        )
        run(
            sys.executable,
            str(LANE),
            "release",
            "--owner",
            winner,
            "--device-id",
            DEVICE_A,
            env=env,
            expected=0,
        )

        first = reserve(env, root, "owner-a", DEVICE_A, "a2")
        second = reserve(env, root, "owner-b", DEVICE_B, "b2")
        if first.wait() != 0 or second.wait() != 0:
            raise AssertionError(
                "distinct lanes should reserve concurrently: "
                f"{first.communicate()} {second.communicate()}"
            )
        first.communicate()
        second.communicate()

        repo = root / "repo-a2"
        evidence = repo / "task-evidence" / "a2"
        exact_destination = f"platform=iOS Simulator,id={DEVICE_A}"
        gate = run(
            *gate_command(
                repo, evidence, exact_destination, "gate.raw.log", require_tests=True
            ),
            env=env,
            expected=0,
        )
        if "Executed 1 test" not in gate.stdout:
            raise AssertionError("guarded command output was not preserved")

        run(
            *gate_command(
                repo,
                evidence,
                "platform=iOS Simulator,name=Lane A",
                "name-based.raw.log",
            ),
            env=env,
            expected=2,
        )
        run(
            *gate_command(
                repo,
                evidence,
                f"platform=iOS Simulator,id={DEVICE_A}0",
                "partial-id.raw.log",
            ),
            env=env,
            expected=2,
        )
        duplicate_destination = gate_command(
            repo,
            evidence,
            exact_destination,
            "duplicate-destination.raw.log",
        )
        duplicate_destination.extend(["-destination", exact_destination])
        run(*duplicate_destination, env=env, expected=2)
        zero_env = env.copy()
        zero_env["FAKE_ZERO_TESTS"] = "1"
        run(
            *gate_command(
                repo,
                evidence,
                exact_destination,
                "zero-tests.raw.log",
                require_tests=True,
            ),
            env=zero_env,
            expected=86,
        )

        install_json = evidence / "install.json"
        installed_app = evidence / "DerivedData" / "Build" / "App.app"
        installed_app.mkdir(parents=True)
        install_command = [
            sys.executable,
            str(LANE),
            "run-devicectl",
            "--owner",
            "owner-a",
            "--device-id",
            DEVICE_A,
            "--log",
            str(evidence / "install.raw.log"),
            "--",
            "xcrun",
            "devicectl",
            "device",
            "install",
            "app",
            "--device",
            DEVICE_A,
            str(installed_app),
            "--json-output",
            str(install_json),
        ]
        run(*install_command, env=env, expected=0)
        if (
            json.loads(install_json.read_text(encoding="utf-8"))["info"]["outcome"]
            != "success"
        ):
            raise AssertionError(
                "structured device-operation evidence was not preserved"
            )

        launch_json = evidence / "launch.json"
        run(
            sys.executable,
            str(LANE),
            "run-devicectl",
            "--owner",
            "owner-a",
            "--device-id",
            DEVICE_A,
            "--log",
            str(evidence / "launch.raw.log"),
            "--",
            "xcrun",
            "devicectl",
            "device",
            "process",
            "launch",
            "--device",
            DEVICE_A,
            "--terminate-existing",
            "com.example.App",
            "--json-output",
            str(launch_json),
            env=env,
            expected=0,
        )

        name_target = install_command.copy()
        name_target[name_target.index(DEVICE_A, name_target.index("--device"))] = (
            "Lane A"
        )
        run(*name_target, env=env, expected=2)
        info_command = install_command.copy()
        operation_start = info_command.index(
            "device", info_command.index("devicectl") + 1
        )
        info_command[operation_start : operation_start + 3] = [
            "device",
            "info",
            "details",
        ]
        run(*info_command, env=env, expected=2)

        physical = reserve(env, root, "owner-p", PHYSICAL_DEVICE, "physical")
        if physical.wait() != 0:
            raise AssertionError(
                f"physical lane reservation failed: {physical.communicate()}"
            )
        physical.communicate()
        physical_repo = root / "repo-physical"
        physical_evidence = physical_repo / "task-evidence" / "physical"
        physical_gate = gate_command(
            repo,
            evidence,
            exact_destination,
            "placeholder.raw.log",
        )
        physical_gate[physical_gate.index("owner-a")] = "owner-p"
        physical_gate[physical_gate.index(DEVICE_A)] = PHYSICAL_DEVICE
        physical_gate[physical_gate.index(str(evidence / "placeholder.raw.log"))] = str(
            physical_evidence / "physical.raw.log"
        )
        physical_gate[physical_gate.index(str(repo / "App-a2.xcworkspace"))] = str(
            physical_repo / "App-physical.xcworkspace"
        )
        physical_gate[physical_gate.index(exact_destination)] = (
            f"platform=iOS,id={PHYSICAL_DESTINATION}"
        )
        physical_gate[physical_gate.index(str(evidence / "DerivedData"))] = str(
            physical_evidence / "DerivedData"
        )
        run(*physical_gate, env=env, expected=0)

        for owner, identifier in (
            ("owner-a", DEVICE_A),
            ("owner-b", DEVICE_B),
            ("owner-p", PHYSICAL_DEVICE),
        ):
            run(
                sys.executable,
                str(LANE),
                "release",
                "--owner",
                owner,
                "--device-id",
                identifier,
                env=env,
                expected=0,
            )

        interactive = reserve(
            env,
            root,
            "owner-ui",
            DEVICE_A,
            "interactive",
            device_hub_window="shared-device-hub-window",
        )
        if interactive.wait() != 0:
            raise AssertionError(
                f"interactive lane reservation failed: {interactive.communicate()}"
            )
        interactive.communicate()
        window_collision = reserve(
            env,
            root,
            "owner-ui-2",
            DEVICE_B,
            "interactive-2",
            device_hub_window="shared-device-hub-window",
        )
        if window_collision.wait() != 2:
            raise AssertionError(
                "shared Device Hub window did not collide: "
                f"{window_collision.communicate()}"
            )
        window_collision.communicate()
        run(
            sys.executable,
            str(LANE),
            "release",
            "--owner",
            "owner-ui",
            "--device-id",
            DEVICE_A,
            env=env,
            expected=0,
        )

        corrupt_lease = root / "state" / "corrupt.json"
        corrupt_lease.write_text("{", encoding="utf-8")
        run(sys.executable, str(LANE), "list", "--json", env=env, expected=2)
        corrupt_lease.rename(corrupt_lease.with_suffix(".invalid"))

        failing_tool_dir = root / "failing-tools"
        failing_tool_dir.mkdir()
        failing_xcrun = failing_tool_dir / "xcrun"
        failing_xcrun.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        failing_xcrun.chmod(0o755)
        unavailable_env = env.copy()
        unavailable_env["PATH"] = f"{failing_tool_dir}{os.pathsep}{env['PATH']}"
        run(
            sys.executable, str(LANE), "list", "--json", env=unavailable_env, expected=2
        )

    print(
        "self-test passed: devicectl identity, collisions, device kinds, exact "
        "destinations, guarded operations, and regression checks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
