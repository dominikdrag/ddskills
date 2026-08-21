# Device Hub and Computer Use Live Smoke

Read this only when the task needs Device Hub interaction or runtime UI evidence. This is a live compatibility check, not a deterministic unit test
and not a prerequisite for automated compile, test, or snapshot commands.

## Preconditions

- Reserve the exact CoreDevice UUID before opening or interacting with Apple tooling.
- Include a unique `--device-hub-window` label in the lease.
- Resolve Device Hub from the selected Xcode:

  ```sh
  developer_dir="${DEVELOPER_DIR:-$(xcode-select -p)}"
  device_hub="$developer_dir/../Applications/DeviceHub.app"
  ```

- Verify the resolved app's bundle identifier is `com.apple.dt.Devices`.

## Read-only compatibility check

Use Computer Use through `node_repl` and `@oai/sky`:

```js
globalThis.sky = (await import("@oai/sky")).sky;
var started = Date.now();
var state = await sky.get_app_state({
  app: "com.apple.dt.Devices",
  disableDiff: true,
});
nodeRepl.write(JSON.stringify({
  elapsedMs: Date.now() - started,
  text: state.text,
  screenshot: state.screenshot?.url,
}));
```

The check passes only when fresh state returns and exposes enough information to identify the owned Device Hub window, the exact leased simulator
UUID or physical-device hardware UDID, and the visible state needed for the claim.

If bundle targeting fails, retry once with the full resolved Device Hub path. A longer `node_repl` timeout does not override an earlier Computer Use
server deadline. If both forms fail, record the exact error and latency, mark Device Hub/runtime UI verification blocked, and release any UI-only
lane resources. Do not manufacture a manifest record from a display name, inventory state, screenshot, or free-form observation.

## Interactive evidence

- Fetch fresh state immediately before every action.
- Verify the exact leased identifier before selecting, preparing, launching, or collecting evidence from a device.
- Prefer current accessibility-element actions; never reuse stale element indices.
- Fetch fresh state after each action before deciding the next step.
- Use screenshots for visual claims or incomplete accessibility data, but do not infer device identity, platform behavior, or persistence from a
  static image alone.
- Keep the interaction scoped to the owned Device Hub window, leased device, exact binary, and named scenario.

Computer Use evidence proves only what was freshly observed. Automated command evidence remains separate, and successful builds or snapshots do not
become interactive runtime proof when this smoke check is blocked.
