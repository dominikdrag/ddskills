# Apple Verification Evidence Contract

## Required lane metadata

- Repository and checkout path
- Task or ticket
- Owner
- Selected Xcode path and version
- Workspace and scheme
- Exact device name, OS version, and UDID
- DerivedData path
- Device Hub window label
- Evidence directory
- Source revision when binary provenance matters

## Automated gates

- Preserve raw output.
- Gate on the underlying command exit code.
- Confirm the intended suite or test executed with a nonzero count.
- Record focused red evidence before implementation when the workflow calls for test-first proof.
- Run the smallest relevant green gate, then broader gates in proportion to risk.

## Snapshot gates

For each filter, retain:

1. Record-mode raw log and expected write count.
2. A list of every changed reference inspected.
3. Notes for intentional visual changes and rejected output.
4. Record-off raw log proving the same test executed and passed.

Never accept a recording merely because files were written. Reject loading, blank, clipped, dependency-invalid, wrong-scenario, or stale-binary images.

## Runtime QA case table

Store a short table with runtime evidence:

| Case | Setup | Action | Expected | Observed | Evidence | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `<id>` | Exact scenario, binary, device, and state | Control activated by ID | User-visible downstream result | AXTree and visual observation | Raw tree/log and screenshot paths | PASS/FAIL/BLOCKED |

Use `$computer-use` for Device Hub and runtime app interaction. Before each action, fetch fresh accessibility state for the exact owned window or app
surface; prefer element-based actions, and fetch state again before deciding the next action. Do not reuse stale element indices. Record the relevant
before-and-after accessibility observations with the case evidence.

Use screenshots for visual claims, incomplete accessibility data, known accessibility-tree defects, or representative proof. Do not claim a
platform or persistence result from a static image alone. Follow the Computer Use confirmation policy; lane ownership does not authorize unrelated
or consequential UI actions.

## Stop conditions

Stop and coordinate when:

- another lane owns the UDID, workspace, DerivedData, Device Hub window, or evidence path;
- Xcode shows only a generic destination label and Device Hub UUID is unverified;
- Computer Use cannot verify the owned Device Hub window, leased UUID, exact app surface, or current accessibility state;
- a foreign process is using an owned resource;
- the workspace, generated project, binary, or source revision is stale or unknown;
- a test exits zero but is skipped or executes zero tests;
- StoreKit proof was launched outside the configured Xcode scheme;
- evidence is partial, loading, wrong-scenario, or otherwise misleading.
