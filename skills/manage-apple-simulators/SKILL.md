---
name: manage-apple-simulators
description: >-
  Claim a private iOS simulator, or an exact physical device, for one agent task and release it at the end, so several agents can test Apple apps
  on the same Mac at once. Use before running tests, snapshot tests, or the app on a simulator or device; when a sub-agent needs its own simulator;
  before opening Device Hub; or to clean up leftover agent simulators.
---

# Manage Apple Simulators

Simulators and Device Hub are shared by every agent on this Mac. Each agent task works on its own **claim**: a fresh simulator created for the
task, reused for every run in that task, and deleted when the task releases it. `scripts/simulators.py` creates, boots, records, and deletes
claimed devices; it does not build or test. For what to build and test and how to prove it, use `$run-apple-verification-loop`.

Resolve `SIMULATORS_DIR` to the directory containing this skill's `SKILL.md`, including when it is a repository-local copy. Do not assume a
particular global installation path. Pass `--worktree <repository root>` on every command; agent shells, especially sub-agent shells, often start
outside the repository you test.

## Decide whether you need a device

- Tests, snapshot tests, or running the app on a simulator: claim a simulator.
- A physical device: claim it by exact ID (see [Physical devices](#physical-devices)).
- Build-only checks: no device. Use a generic destination such as `-destination 'generic/platform=iOS Simulator'`.

## 1. Claim

```sh
python3 "$SIMULATORS_DIR/scripts/simulators.py" claim --worktree <repository root>
```

It prints `claim <id>`, `udid <udid>`, `destination platform=iOS Simulator,id=<udid>`, `device <model>, iOS <os> (<build>)`, `reused yes|no`,
and `expires <time>`, one per line; `--json` prints one object. The first claim takes about 30 seconds (create and first boot).

The default device is `iPhone 17 Pro` on the newest installed iOS runtime. Ask for another one only when the work depends on it:

- `--model NAME`: exact device type name, for example `--model 'iPhone 17'`.
- `--os VERSION`: for example `--os 26.5`; `--os 27` takes the newest installed `27.x`.
- `--runtime-build BUILD`: require one runtime build. Several builds can share one OS version (for example iOS 27.0 `24A5390f` and `24A434`);
  CoreSimulator picks one, and the claim records the build it actually got.
- `--no-boot`: create without booting. Not with `--runtime-build`.

The script claims iPhone and iPad simulators only; for other simulator platforms, report the device step as blocked.

Snapshot tests: claim the model and OS the repository pins, and add `--runtime-build` when its reference images were recorded on a specific build.

Exit codes: `0` ready; `2` invalid or refused request; `3` blocked (model or runtime not installed, runtime build mismatch, device held by someone
else, device not found); `1` unexpected error. On `3`, report the work as blocked and quote the script's message.

The step is done when you have the `udid` and `destination`, or a blocked result to report.

## 2. Use the claimed device

Pass the claimed UDID everywhere. Device names repeat across agents, so never target a device by name.

- `xcodebuild`: `-destination "<destination printed by claim>"` (`platform=iOS Simulator,id=<udid>` for a simulator), or the repository
  wrapper's device-ID option (such as `--device-id <udid>`).
- Install, launch, screenshots, settings: `xcrun devicectl device install app --device <udid> <App.app>`, `xcrun devicectl device process launch
  --device <udid> --terminate-existing <bundle-id>`, `xcrun devicectl device capture screenshot --device <udid> --destination <file.png>`,
  `xcrun devicectl device settings ...`.
- `devicectl` cannot boot or shut down a simulator. For that, use `xcrun simctl boot|shutdown <udid>` on your claimed simulator.
- Device Hub: only to see or drive the app, in your own window for your claimed device. Read [references/device-hub.md](references/device-hub.md)
  before opening it.

A claim separates devices, not build caches. If Xcode reports a locked build database, another build is using the same DerivedData: wait, or
work in your own worktree.

## 3. Reuse it for the whole task

Run the same `claim` (same worktree and label) again before each test run. It returns the same device (`reused yes`), boots the simulator if it
was shut down, and refreshes the 12-hour expiry; running tests does not refresh it. This is also how to look up the UDID later. Without device
options, `claim` returns your newest simulator claim; a physical claim comes back only with `--device-id`. With `--model`, `--os`, or
`--runtime-build`, it returns a claim only when they match, and otherwise creates another simulator. Keep claims between runs; release them only
when the task ends.

## 4. Sub-agents and labels

A claim belongs to an **owner** (the nearest ancestor process named `claude`, `codex`, or `codex-*`), a worktree (`--worktree`, by default the
Git root of the working directory), and a label (`--label`, empty by default). The same owner, worktree, and label always get the same claim.

- Sub-agents of one session share the session's owner process (in Claude Code and Codex alike). A sub-agent therefore always passes its own
  `--label` (for example its ticket or task name) to both `claim` and `release`, even in another worktree. Without one, it can get the parent's
  or a sibling's simulator, and its `release` would delete it.
- A parent can instead hand its claim (UDID and destination) to a sub-agent. The sub-agent uses it and leaves the release to the parent.
- A parent that gave a sub-agent a label releases that label at the end (`release --label <label>`) if the sub-agent did not.
- Sessions that run under one host process count as one owner: every thread of the Codex desktop app runs under one `codex app-server`. In that
  app, pass a `--label` unique to the thread (for example its task name) to every `claim` and `release`.
- If `claim` warns that no agent process was found, the claim relies on the 12-hour expiry. Pass `--owner-pid <pid>` of the long-running agent
  process when you know it (or set `APPLE_SIMULATORS_OWNER_PID`), with the same value on every later `claim`, `release`, and `list --mine`.

## 5. Release at the end of the task

```sh
python3 "$SIMULATORS_DIR/scripts/simulators.py" release --worktree <repository root>
```

Release when the task ends, whether it succeeded, failed, or was interrupted. Use the same `--label`, `--worktree`, and `--owner-pid` as the
claim; this releases every claim you hold for that worktree and label. To release only some, name them with `--claim ID` (repeatable). Release
deletes the simulator and any XCTest clones left from it; for a physical device it only frees the claim.
`no claims to release` is a normal result. Release refuses (exit `2`) a claim whose owner is another agent that is still running, or that `ps`
cannot check.

The step is done when `release` exits `0` and you have reported that your Apple devices are released.

## Crashed sessions and cleanup

When the owning agent process ends without releasing, its claim is **abandoned**. A claim also expires 12 hours after the last `claim` call that
returned it, even while its owner is still running. Every `claim` and `release` by any agent removes abandoned and expired claims with their
simulators and clones, and deletes shut-down `agent-sim` simulators that have no claim; it only reports running ones, because another state
folder may own them. A crashed session needs no manual step. Where `ps` cannot run (some
sandboxes block it), owners count as alive and only expired claims are removed.

To inspect or clean up by hand:

```sh
python3 "$SIMULATORS_DIR/scripts/simulators.py" list [--mine [--label L]] [--json]
python3 "$SIMULATORS_DIR/scripts/simulators.py" cleanup [--older-than-days 7] [--json]   # dry run: reports only
python3 "$SIMULATORS_DIR/scripts/simulators.py" cleanup --apply
```

`list` shows every claim (owner alive, gone, or unknown; abandoned or not; expiry), orphan `agent-sim` simulators, and how many simulators are
booted on the Mac; it changes nothing. `cleanup --apply` removes abandoned claims, orphan `agent-sim` simulators (running ones too, so check
`list` first), shut-down XCTest clones of
`agent-sim` simulators that no live claim owns, and other shut-down XCTest clones older than `--older-than-days`. Apart from those clones, it
touches only simulators named `agent-sim <claim-id> <model> <os>`.

## Parallel test workers

Tests run serially by default. Use parallel workers only when the user or repository asks:
`-parallel-testing-enabled YES -parallel-testing-worker-count N`. Each worker is an XCTest clone of your simulator (`Clone <N> of agent-sim ...`).
Xcode deletes the clones after a finished run; release deletes any that an interrupted run left behind. The script sets no worker limit, but
each clone costs memory and boot time; `claim` prints a note when more than 4 simulators are booted on the Mac.

## Physical devices

Claim with `claim --device-id <CoreDevice identifier or hardware UDID>`; the destination is `platform=iOS,id=<hardware UDID>`. The script never
creates, boots, or deletes a physical device, and refuses (exit `3`) one that another live claim or an old `lane.py` lease holds. `--device-id`
does not combine with `--model`, `--os`, or `--runtime-build`, and does not accept simulators: simulators are created per task.

## Hard rules

- Touch only devices you claimed: boot, shut down, erase, install on, or change settings only for your claimed UDID. Create and delete
  simulators through `claim` and `release`, so the claim record stays in step with the device. Never rename a claimed simulator. The
  automatic cleanup inside `claim` and `release` (abandoned and expired claims, shut-down orphans) is expected and does not break this rule.
- Never quit Device Hub; its Quit can shut down every simulator on the Mac. Close only your own window.
- Never download or install simulator runtimes. A missing runtime is a blocked result for the owner.
- Never write to the legacy registry `~/.codex/state/apple-verification-lanes`; the script only reads it.
