# Device Hub and Computer Use

Read this only before seeing or driving the app in Device Hub, or before collecting runtime UI evidence. Builds, tests, snapshots, screenshots,
install, launch, and settings changes do not need Device Hub: use `xcrun devicectl` with your claimed UDID, for example
`xcrun devicectl device capture screenshot --device <udid> --destination <file.png>`.

## Rules

Device Hub is one app shared by every agent on this Mac.

- Claim the device first with `manage-apple-simulators`. Work only with your claimed UDID (simulator) or hardware UDID (physical device).
- Keep Device Hub running. Its Quit can shut down every simulator on the Mac ("Quit and Shutdown Simulators"), so never quit, force-quit, or
  restart it.
- Open your own window for your own claimed device, work only in that window, and close only that window.
- Leave every other window as it is. Never switch the device shown in the main window or in another agent's window.

## Open your own window

1. Resolve Device Hub from the selected Xcode (`${DEVELOPER_DIR:-$(xcode-select -p)}/../Applications/DeviceHub.app`) and verify its bundle
   identifier is `com.apple.dt.Devices`.
2. Bring Device Hub to the front. Driving its menus needs Computer Use approval for the full screen.
3. Choose File > New Window.
4. In the new window, select only your own claimed device. Check its UDID in the device Info before doing anything else.

Device Hub `devices://` links opened no window when tested (2026-10-01, Xcode 27.0 RC); open your own window with File > New Window.

## Discover the current host interface

Inspect available computer-use tools and read their current entrypoint documentation. Use the interface exposed by this host; do not import an
SDK or assume a tool name from an older session.

For a host exposing `mcp__cua_repl`, its current entrypoint is a single call such as:

```js
let deviceHub = await cua.getApp("com.apple.dt.Devices");
```

Read the documentation and initial state returned by that call before using further APIs. Another host may provide a different supported
interface; follow that tool's schema. Discover first instead of treating an unavailable historical API as a Device Hub outage.

The compatibility check passes only when fresh state identifies your own window, your claimed simulator UDID or physical hardware UDID, and the
visible state the check needs. If targeting by bundle ID fails, try the resolved app path once when the current API supports it. Capture the
exact error and elapsed time if the supported entrypoints fail; mark only the affected interactive check blocked and close any window you opened.
Extending a client timeout does not fix a server deadline.

## Interactive evidence

- Fetch fresh state immediately before and after actions; use current accessibility elements rather than stale indices.
- Verify your claimed identifier before selecting, preparing, launching, or collecting evidence from a device.
- Keep interaction scoped to your own window, your claimed device, the exact binary, and the named scenario.
- Use screenshots for visual results or incomplete accessibility data. A static image alone does not establish device identity, platform
  behavior, or persistence.

Report only what was freshly observed. Keep automated command evidence separate when interactive checks are unavailable.

## Finish

Close your own window, leaving Device Hub running. Release the claim at the end of the task, as `SKILL.md` describes.
