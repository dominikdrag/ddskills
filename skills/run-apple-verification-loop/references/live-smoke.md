# Device Hub and Computer Use Live Smoke

Read this only for Device Hub interaction or runtime UI evidence. It is not a prerequisite for automated builds, tests, or snapshots.

## Preconditions

- Own the exact CoreDevice UUID and a unique Device Hub window label before interaction.
- Resolve Device Hub from the selected Xcode (`${DEVELOPER_DIR:-$(xcode-select -p)}/../Applications/DeviceHub.app`) and verify its bundle identifier is `com.apple.dt.Devices`.

## Discover the current host interface

Inspect available computer-use tools and read their current entrypoint documentation. Use the interface exposed by this host; do not import an SDK or assume a tool name from an older session.

For a host exposing `mcp__cua_repl`, its current entrypoint is a single call such as:

```js
let deviceHub = await cua.getApp("com.apple.dt.Devices");
```

Read the documentation and initial state returned by that call before using further APIs. Another host may provide a different supported interface; follow that tool's schema. Discover first instead of treating an unavailable historical API as a Device Hub outage.

The compatibility check passes only when fresh state identifies the owned window, exact leased simulator UUID or physical hardware UDID, and the visible state needed for the claim. If targeting by bundle ID fails, try the resolved app path once when the current API supports it. Capture the exact error and elapsed time if the supported entrypoints fail; mark only the affected interactive gate blocked and release UI-only resources. Extending a client timeout does not fix a server deadline.

## Interactive evidence

- Fetch fresh state immediately before and after actions; use current accessibility elements rather than stale indices.
- Verify the exact leased identifier before selecting, preparing, launching, or collecting evidence from a device.
- Keep interaction scoped to the owned window, leased device, exact binary, and named scenario.
- Use screenshots for visual claims or incomplete accessibility data. A static image alone does not establish device identity, platform behavior, or persistence.

Report only what was freshly observed. Keep automated command evidence separate when interactive checks are unavailable.
