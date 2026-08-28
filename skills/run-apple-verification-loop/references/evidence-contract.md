# Apple Verification Evidence Contract

General snapshot and runtime evidence rules apply whenever those claims are in scope. Exact lane metadata and guarded command requirements apply
only after verification has escalated. Ordinary repository-native compile, test, and deterministic snapshot checks do not require an exact device,
new evidence directory, or isolated DerivedData.

## Authority boundaries

| Source or resource | What it can prove | What it cannot prove |
| --- | --- | --- |
| Structured `xcrun devicectl list devices` result | The selected Xcode's exact CoreDevice inventory and identity metadata | Fresh readiness, visible UI, active destination, app behavior, or test success |
| Atomic lease | Exclusive ownership of the recorded device and paths while the lease exists | Device readiness, command success, or UI state |
| Guarded `xcodebuild` command | Exact platform and destination ID, workspace, DerivedData, raw output, and exit status | Visible Device Hub state or user-visible behavior |
| Executed-test output | That the guarded test command executed a nonzero test count | Correct pixels, interaction behavior, or persistence beyond the test contract |
| Successful structured direct-device result | That the exact leased install or launch operation succeeded | App UI state, StoreKit scheme attachment, or downstream behavior |
| Fresh Computer Use state | The visible owned Device Hub or app surface and the exact identifier/state actually exposed there | Source revision, binary provenance, command success, or persistence from a static observation |
| Device Hub window label | Coordination intent that prevents two leases from naming the same planned window | The existence, identity, or current contents of an actual window |

Use only the sources needed for the claim. Automated compile, test, snapshot, install, and launch commands do not require a Device Hub observation.
Interactive Device Hub and runtime claims do.

## Required metadata for an isolated lane

- Repository and checkout path
- Task and owner
- Selected Xcode when binary or device-tool provenance matters
- Workspace and scheme
- Exact CoreDevice UUID
- Physical or simulated reality
- Exact Xcode destination identifier
- Isolated DerivedData and evidence paths
- Device Hub window coordination label only when interactive UI is in scope
- Source revision when binary provenance matters

## Automated gates in an isolated lane

- Preserve raw output and the underlying exit code.
- Recheck exact structured device identity immediately before a guarded command.
- Use only the leased workspace, exact platform and destination ID, isolated DerivedData, and evidence paths.
- Preserve successful structured JSON for direct install and launch operations.
- Confirm the intended test executed with a nonzero count when the command is a test gate.
- Run the smallest relevant gate, then broaden in proportion to risk.
- Do not convert automated results into Device Hub, physical-device, or interactive runtime claims.

## Snapshot gates

Use the repository's normal destination and existing DerivedData unless the output depends on a stable model, OS, scale, or exact runtime state. Do
not create persistent raw logs solely because a snapshot test ran. For each filter, confirm:

1. Record mode ran and produced the expected write count.
2. A list of every changed reference inspected at rendered size.
3. Notes for intentional visual changes and rejected output.
4. Record-off output proving the same test executed and passed.

When persistent evidence or an isolated lane is required, retain the corresponding raw logs and exact destination metadata.

Never accept a recording merely because files were written. Reject loading, blank, clipped, dependency-invalid, wrong-scenario, wrong-device, or
stale-binary images.

## Interactive runtime evidence

Store a short case table:

| Case | Setup | Action | Expected | Observed | Evidence | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `<id>` | Exact scenario, binary, device, and state | Control activated by ID | User-visible downstream result | Fresh accessibility and visual observation | Raw command evidence plus before/after UI observations | PASS/FAIL/BLOCKED |

Read [live-smoke.md](live-smoke.md) before collecting Device Hub or app UI evidence. Fetch fresh state before and after actions, keep Computer Use
scoped to the owned resources, and use screenshots only for claims they can support.

## Stop conditions

Stop the affected automated gate when:

- structured inventory is unavailable, malformed, ambiguous, or no longer contains the exact leased device;
- the device reality, destination identifier, platform, workspace, DerivedData, or evidence path differs from the lease;
- another lane owns an overlapping resource;
- the command uses a display name, partial identifier, unsupported operation, or unguarded shared path;
- a command fails, produces unsuccessful structured evidence, skips the intended test, or executes zero tests;
- source, workspace, generated project, or binary provenance needed for the claim is stale or unknown.

Stop only the interactive/UI lane when:

- Computer Use cannot fetch fresh state for the owned Device Hub window, exact identifier, app surface, or required state;
- Device Hub exposes only a generic label or disagrees with the leased identity;
- UI evidence is partial, loading, stale, wrong-scenario, wrong-binary, or from another lane;
- StoreKit behavior was launched outside the configured Xcode scheme.

An interactive blocker does not invalidate independent automated evidence. Report the boundary instead of broadening either claim.
