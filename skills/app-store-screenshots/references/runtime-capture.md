# Real runtime screenshots

Use this guide when obtaining app screens or checking whether existing sources are suitable for finished App Store artwork. Capture the running app's window on a simulator or device, including its native material rendering. A file under `__Snapshots__`, a passed snapshot comparison, or a PNG rendered from SwiftUI is not evidence of a runtime capture.

## Select the build and rendering path

- Read the app repository's build, testing, and device-ownership rules. Select the intended checkout, source revision, app target, runtime, and exact device identifier. Use its existing simulator pool and build-cache coordination where provided; do not interfere with another task's device or build.
- Build and install the selected app, or verify the exact existing binary being reused. Check its actual path, bundle identity, version, and build context. Capture configurations can point at stale temporary binaries even when the repository is current.
- A Playbook or scenario app is suitable when it presents the product's actual views through their normal runtime rendering path. Authored example data is acceptable; a separate imitation of the UI is not. Check that the scene represents the intended product state and visible navigation.
- Inspect capture flags and rendering policy where needed. Examples include `isSnapshot`, `PLAYBOOK_SNAPSHOTS`, and `forcesPlainFills`; names vary by app. Do not invoke the snapshot suite or enable a flag that substitutes solid fills for native materials. A normal Playbook launch and its snapshot-test launch can render the same view differently.
- Resolve the actual runtime scene identifier. A `-dark` suffix on a golden-image filename does not establish a dark-mode launch route.

Keep reusable instructions free of app-specific bundle IDs, simulator UUIDs, private paths, and source revisions. Record those values in the task's capture manifest instead.

## Verify appearance before multiplying captures

Set and read back the requested light or dark appearance, locale, text size, and relevant accessibility settings. For the ordinary Liquid Glass appearance, verify that Reduce Transparency and any app-specific plain-fill override are off. Do not disable an accessibility setting when that setting is the treatment the user requested. Record and restore any shared-device settings you change.

Capture one representative screen and inspect the **raw full-size PNG** before batch capture or composition. Check actual glass surfaces, translucency, layered backgrounds, native controls, system chrome, and intended content. Configuration values and a successful build are insufficient on their own. Capture each requested appearance from the running app; recoloring or inverting another capture cannot reproduce native dark mode.

Use the device tooling supported by the selected Xcode and repository. Inspect local `--help` before copying commands across toolchains. In a workflow that uses Device Hub / `devicectl`, an old script hardcoding `simctl` may be unusable; do not assume commands are interchangeable.

## Reach and verify the actual screen

Launch the intended scene or navigate through the app. Inspect accessibility text and state before capture when available. Wait for meaningful readiness: loaded data, the correct screen, and an enabled action when an asynchronous transition is involved. A screen sentinel can appear before its controls finish preparing; a fixed delay alone is not proof of readiness. Let entrance and material animations settle as needed.

Derive interaction queries from the running accessibility tree. SwiftUI can propagate a container's identifier onto its descendants, replacing identifiers expected from source code. Use an observed unique button label or a child-button query when appropriate. A container existing does not mean it is the tappable control. Scroll the actual scroll view without triggering unrelated card gestures, and confirm the resulting state after each interaction.

To obtain a better example, perform supported interactions or use an existing authored scenario. Do not relabel a bitmap, invent controls, or change product styling to fit the artwork. If an optional interaction cannot be confirmed, relaunch a known supported state and document what was actually captured.

## Capture the native window

Choose an available route that preserves the runtime window. These are capture mechanisms, not replacements for the repository's build and device-ownership workflow.

### XCTest attachments

An existing UI-test target can launch a normal app or Playbook scene and capture `XCUIScreen.main.screenshot()`. This is different from a SwiftUI snapshot-test renderer. Prefer a focused capture method in an existing target over unnecessary project regeneration. Adapt the app identity, launch arguments, and readiness query to the observed app:

```swift
@MainActor
func testCaptureStoreScene() {
    continueAfterFailure = false
    let app = XCUIApplication(bundleIdentifier: "com.example.app.playbook")
    // Use only launch arguments supported by this app's normal runtime route.
    app.launchArguments = ["--test-destination", "example-runtime-scene"]
    app.launch()
    defer { app.terminate() }

    let ready = app.buttons["Observed ready action"]
    XCTAssertTrue(ready.waitForExistence(timeout: 20))
    XCTAssertTrue(ready.isEnabled)

    let hierarchy = XCTAttachment(string: app.debugDescription)
    hierarchy.name = "scene-final-accessibility"
    hierarchy.lifetime = .keepAlways
    add(hierarchy)

    let capture = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
    capture.name = "scene-native-fullscreen"
    capture.lifetime = .keepAlways
    add(capture)
}
```

Run only the intended capture test on the owned exact device, using the repository's test wrapper and serial-execution rules. Keep a result bundle. Wait for the test process and bundle to finish before exporting attachments. Where supported:

```sh
xcrun xcresulttool export attachments \
  --path "$CAPTURE_RESULT_BUNDLE" \
  --output-path "$CAPTURE_EVIDENCE/attachments"
```

Read the exported attachment manifest to map scene names to files; exported filenames may be opaque UUIDs. Verify the executed test result and the actual screenshot contents. A compiled helper, started test runner, or zero-test run is not capture success. A partial run may contain usable individual captures, but it does not prove the full set completed.

### Native device capture command

If supported by the selected Xcode and device, `devicectl` can read appearance and capture the display. Set the variables below to the owned device and absolute evidence directory; create that directory first. The app must already be foregrounded on the verified, ready scene:

```sh
xcrun devicectl device info appearance \
  --device "$CAPTURE_DEVICE_ID" \
  --json-output "$CAPTURE_EVIDENCE/appearance.json"

xcrun devicectl device capture screenshot \
  --device "$CAPTURE_DEVICE_ID" \
  --destination "$CAPTURE_EVIDENCE/scene-native.png"
```

Verify that the result is the app scene, not the Home Screen, test runner, alert, or a stale view. A successful screenshot command only establishes that a display image was saved.

## Handle capture failures without downgrading the result

A UI-control timeout does not prove the simulator cannot run the app. Inspect the concrete failure, available owned devices, and supported capture routes. For example, a working simulator with unreliable window automation may still support a focused XCTest capture. Keep retries bounded by new evidence or a changed condition; do not repeatedly boot the same failing environment or take over another task's device.

If no runtime route works, finish independent copy/layout preparation, identify the missing scenes and blocker, and leave the set incomplete. Do not copy snapshot goldens into the capture directory, reuse unverified stale binaries, fabricate missing chrome, or upload reference-based artwork as the requested finished set. Preserving a previously approved layout does not validate replacement source images.

## Preserve proof and hand off

Keep raw captures unchanged. Record source revision and binary identity, device/runtime, appearance, locale, scene identifier and relevant interactions, capture time, original path, dimensions, and SHA-256. Link runtime/test evidence according to the repository's evidence rules. Keep source-capture hashes separate from composed-export hashes. Authored sample data and a visible proposal are not customer results or proof of a completed action.

Inspect whether the native screenshot includes the hardware camera cutout. Simulator images may include a genuine status bar but omit the physical cutout; the surrounding device frame may supply that hardware detail. Avoid duplicate cutouts and preserve the clock, status icons, and app content. Never draw missing software chrome into the image. Continue with the [framing and delivery checks](review-and-delivery.md#capture-and-framing).

Restore temporary capture-only source changes and any device settings you changed; preserve unrelated work. Release only the resources owned by this task. Update the gallery, exports, package, and provenance together. Keep retained reference variants clearly historical and outside the current delivery when they no longer match its runtime captures. Capture and export verification do not authorize App Store upload or prove a public release.
