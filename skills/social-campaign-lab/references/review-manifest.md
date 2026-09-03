# Review manifest

Use one JSON manifest as the coordinator ledger. Relative `sourceDir` values resolve from the manifest file; absolute values are accepted when a task
worktree needs an explicitly shared collection path. Every frame resolves from its `sourceDir`.

```json
{
  "schemaVersion": 1,
  "campaign": {
    "id": "2026-09-03-campaign-b",
    "title": "Launch Control campaign B",
    "brief": "Coherent feature-led concepts grounded in posted Launch Control assets",
    "reference": "goldie/social/posts/02-grace-under-pressure/"
  },
  "concepts": [
    {
      "taskId": "01a00000-0000-7000-8000-000000000001",
      "seed": "a1b2c3d4e5",
      "title": "A calm way back",
      "feature": "Morning Board recovery",
      "benefit": "A late start can still become a useful plan",
      "approach": "Hook-and-proof carousel",
      "format": "carousel",
      "assetStatus": "ready",
      "sourceDir": "../seed-lab/a1b2c3d4e5",
      "frames": ["out/01-cover.png", "out/02-proof.png"]
    }
  ]
}
```

Required invariants:

- `campaign.id` is stable across review rounds.
- Every concept has a unique pair of final `taskId` and 10-character lowercase alphanumeric `seed`.
- `format` is `single` for exactly one frame or `carousel` for two or more frames.
- `sourceDir` contains `concept.md`, `caption.md`, and `render.mjs`.
- Every frame stays inside `sourceDir` and is a 1080x1350 8-bit RGB PNG without alpha.
- `assetStatus` is descriptive metadata such as `ready` or `revised`; it does not replace the review verdict.

The builder derives identity as `<campaign.id>::<taskId>::<seed>`. Replace frames and update descriptions in place during iteration. Do not change
identity merely because an asset was revised.

## Decision record

The board stores decisions locally for convenience and can export a portable ledger:

```json
{
  "schemaVersion": 1,
  "campaignId": "2026-09-03-campaign-b",
  "decisions": {
    "2026-09-03-campaign-b::01a00000-0000-7000-8000-000000000001::a1b2c3d4e5": {
      "verdict": "keep",
      "note": "Keep the design; reduce the card clutter."
    }
  }
}
```

Before an iteration refresh:

1. Use **Export decisions** in the board.
2. Rebuild with that file passed to `--decisions`.
3. Open the refreshed HTML and confirm the counts, verdicts, and notes before routing further work.

The builder embeds imported decisions, merges newer browser-local values for the same campaign, and retains decision entries for concepts no longer
displayed. The board's **Import decisions** action supports moving the self-contained HTML to another browser or machine.
