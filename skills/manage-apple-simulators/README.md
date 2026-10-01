# Manage Apple Simulators

Let several agents (Codex, Claude Code, and their sub-agents) test Apple apps on one Mac at the same time without fighting over simulators or
Device Hub. Each agent task claims its own fresh simulator, reuses it for every run in the task, and deletes it when the task ends.

Use this skill whenever an agent needs a simulator or physical device for tests, snapshot tests, or running the app. Build-only checks need no
device. [run-apple-verification-loop](../run-apple-verification-loop/README.md) decides what to test and how to prove it, and gets its devices
from this skill.

## How it works

1. **Claim.** `simulators.py claim` creates an `agent-sim <claim-id> <model> <os>` simulator (default `iPhone 17 Pro` on the newest installed
   iOS runtime), boots it, records the runtime build it actually got, and prints its UDID and `xcodebuild` destination. Snapshot work can ask
   for a model, OS version, and runtime build.
2. **Reuse.** The same agent process, worktree, and label get the same claim back, so every run in a task uses the same simulator; running
   `claim` before each run also refreshes its 12-hour expiry. A different worktree or `--label` gets a separate simulator; sub-agents share their
   session's process, so each passes its own `--label`.
3. **Release.** At the end of the task, `release` shuts down and deletes the simulator and its XCTest clones.
4. **Recover.** A claim records its owner, the long-running `claude` or `codex` process, with its start time. When that process is gone, or 12
   hours pass after the last `claim` that returned it, the claim is abandoned, and the next `claim` or `release` by any agent deletes it.

Physical devices are claimed by exact ID and are never created, booted, or deleted. A device still held by an old `lane.py` lease in
`~/.codex/state/apple-verification-lanes` is refused; the script reads that folder and never writes to it.

## Commands

| Command | What it does | Options |
| --- | --- | --- |
| `claim` | Create and boot a simulator, or claim a physical device, or return the existing claim | `--model`, `--os`, `--runtime-build`, `--device-id`, `--no-boot`, `--label`, `--worktree`, `--owner-pid`, `--json` |
| `release` | Delete the claimed simulator and its clones, or free a physical device | `--claim ID` (repeatable), `--label`, `--worktree`, `--owner-pid`, `--json` |
| `list` | Show claims, orphan `agent-sim` simulators, and the booted-simulator count; changes nothing | `--mine`, `--label`, `--worktree`, `--owner-pid`, `--json` |
| `cleanup` | Report abandoned claims, orphan `agent-sim` simulators, and shut-down XCTest clones; delete them with `--apply` | `--apply`, `--older-than-days N` (default 7), `--json` |

Exit codes: `0` ok, `1` unexpected error, `2` invalid or refused request, `3` blocked (model or runtime not installed, runtime build mismatch,
device held by someone else, device not found).

The script never downloads runtimes, never drives Device Hub, and never touches a simulator that is not named `agent-sim <claim-id> ...`,
except XCTest clones: its own on release, and shut-down ones during cleanup. Claims live in `~/.local/state/manage-apple-simulators`.

Environment overrides exist for tests: `APPLE_SIMULATORS_STATE` (state folder), `APPLE_SIMULATORS_XCRUN` (`xcrun` path),
`APPLE_SIMULATORS_XCTEST_SET` (XCTest clone device set), `APPLE_SIMULATORS_LEGACY_LEASES` (legacy registry folder, read-only),
`APPLE_SIMULATORS_OWNER_PID` (same as `--owner-pid`), and `APPLE_SIMULATORS_PS` (`ps` path).

## Requirements

macOS with Xcode (`xcrun simctl` and `xcrun devicectl`), the simulator runtimes you need installed in Xcode > Settings > Components, and
Python 3.9 or newer (standard library only). Device Hub and Computer Use are needed only to see or drive the app interactively.

## Bundled resources

- [`scripts/simulators.py`](scripts/simulators.py): claim, reuse, release, list, and clean up simulators and physical devices.
- [`scripts/self_test.py`](scripts/self_test.py): test the script against a fake `xcrun` and fake owner processes; it creates no real
  simulators. Run `python3 skills/manage-apple-simulators/scripts/self_test.py` from a checkout of this repository.
- [`references/device-hub.md`](references/device-hub.md): Device Hub rules, opening your own window, and the Computer Use check for interactive
  QA.

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill manage-apple-simulators \
  -g -a codex -y
```

Install it together with run-apple-verification-loop, which depends on it.

See the executable agent instructions in [SKILL.md](SKILL.md).

[Back to all skills](../../README.md)
