# Apple Verification Evidence Contract

## Authority boundaries

| Source or resource | What it can prove | What it cannot prove |
| --- | --- | --- |
| Structured `xcrun devicectl list devices` result | The selected Xcode's CoreDevice inventory, exact CoreDevice identifier, physical/simulated reality, hardware UDID, platform, OS metadata, and a reported state snapshot | Fresh boot/connection readiness, the currently visible Device Hub window, the active Xcode destination, app UI state, persistence, or test success |
| Physical device | Real hardware identified by `reality=physical`; its CoreDevice UUID is the lane/operation key and its hardware UDID is the Xcode destination ID | Simulator behavior or proof that the device is currently connected, unlocked, trusted, or ready |
| Simulator | A simulated device identified by `reality=simulated`; its exact UUID is both the lane key and Xcode destination ID | Physical-device behavior or a fresh visible boot state without Device Hub confirmation |
| Device Hub window via fresh Computer Use state | The owned UI window, exact displayed simulator UUID or physical-device hardware UDID, visible boot/connection state, and current runtime UI surface | Source revision, binary provenance, command exit status, test execution count, or persistence from a static image |
| Guarded Xcode destination | Exact `platform` plus `id` from the lease, exact workspace, and isolated DerivedData used by the command | Device Hub readiness or success unless the underlying raw output and executed-test evidence also prove it |
| Lease's Device Hub window label | A collision key that prevents concurrent lanes from claiming the same intended window | Device identity or UI state by itself |

The `devicectl` inventory and Device Hub confirmation are a handshake. A lane is not ready when only one source confirms the identifier. If either
source is unavailable, ambiguous, stale, or disagrees with the lease, stop without switching to another discovery or targeting mechanism.

## Required lane metadata

- Repository and checkout path
- Task or ticket
- Owner
- Selected Xcode path and version
- Workspace and scheme
- Exact CoreDevice identifier UUID
- Device kind: physical or simulator
- Exact hardware UDID and generated Xcode destination
- Device name and OS version as descriptive metadata only
- Isolated DerivedData path
- Device Hub window coordination label
- Fresh Device Hub destination/runtime confirmations, including exact observed simulator UUID or physical hardware UDID, visible state, purpose, and timestamp
- Evidence directory
- Source revision when binary provenance matters

## Automated gates

- Preserve raw output.
- Gate on the underlying command exit code.
- Preserve the successful structured JSON for direct device install and launch operations.
- Confirm the intended suite or test executed with a nonzero count.
- Record focused red evidence before implementation when the workflow calls for test-first proof.
- Run the smallest relevant green gate, then broader gates in proportion to risk.
- Recheck exact `devicectl` identity immediately before guarded Xcode or direct-device operations.
- Require a matching Device Hub destination confirmation before `xcodebuild` and a runtime confirmation before direct install or launch.

## Snapshot gates

For each filter, retain:

1. Record-mode raw log and expected write count.
2. A list of every changed reference inspected.
3. Notes for intentional visual changes and rejected output.
4. Record-off raw log proving the same test executed and passed.

Never accept a recording merely because files were written. Reject loading, blank, clipped, dependency-invalid, wrong-scenario, wrong-device, or
stale-binary images.

## Runtime QA case table

Store a short table with runtime evidence:

| Case | Setup | Action | Expected | Observed | Evidence | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `<id>` | Exact scenario, binary, device, and state | Control activated by ID | User-visible downstream result | AXTree and visual observation | Raw tree/log, structured command JSON, and screenshot paths | PASS/FAIL/BLOCKED |

Use `$computer-use` for Device Hub and runtime app interaction. Before each action, fetch fresh accessibility state for the exact owned window or app
surface; prefer element-based actions, and fetch state again before deciding the next action. Do not reuse stale element indices. Record the relevant
before-and-after accessibility observations with the case evidence.

Use screenshots for visual claims, incomplete accessibility data, known accessibility-tree defects, or representative proof. Do not claim a
platform or persistence result from a static image alone. Follow the Computer Use confirmation policy; lane ownership does not authorize unrelated
or consequential UI actions.

## Stop conditions

Stop and coordinate when:

- `xcrun devicectl` is unavailable, returns unsuccessful or malformed structured output, or does not contain the exact leased CoreDevice UUID;
- the device's physical/simulated reality, hardware UDID, platform, or Xcode destination differs from the lease;
- another lane owns the device UUID, workspace, DerivedData, Device Hub window label, or evidence path;
- Device Hub or Xcode shows only a generic destination label and Device Hub's exact device identifier is unverified;
- Computer Use cannot read fresh state for the owned Device Hub window, leased device identifier, exact app surface, or current state;
- Device Hub and `devicectl` disagree about the exact device;
- an Xcode destination uses a display name, partial identifier, wrong platform, or wrong hardware UDID;
- a direct device operation lacks a matching runtime confirmation or successful structured result;
- a foreign process is using an owned resource;
- the workspace, generated project, binary, or source revision is stale or unknown;
- a test exits zero but is skipped or executes zero tests;
- StoreKit proof was launched outside the configured Xcode scheme;
- evidence is partial, loading, wrong-scenario, or otherwise misleading.
