# Campaign contract

Use schema version 2 when a campaign enters asset production. Keep the authority separate from the campaign manifest so every lane can receive and hash
the same immutable file.

## Visual authority

Paths resolve from `visual-authority.json`. SHA-256 values are lowercase hexadecimal digests of file bytes.

```json
{
  "schemaVersion": 1,
  "id": "launch-control-2026-09-a",
  "canvas": { "width": 1080, "height": 1350, "colorSpace": "srgb" },
  "safeArea": { "x": 72, "y": 72, "width": 936, "height": 1206 },
  "brand": {
    "colors": { "paper": "#F4F0E8", "ink": "#26231F", "accent": "#D86B3D" },
    "fonts": { "display": "New York", "body": "SF Pro" }
  },
  "incumbentPosts": [
    { "path": "references/incumbent-01.png", "sha256": "<sha256>" }
  ],
  "appCaptures": [
    {
      "id": "morning-board",
      "path": "captures/morning-board.png",
      "sha256": "<sha256>",
      "protectedRect": { "x": 0, "y": 120, "width": 980, "height": 1050 }
    }
  ]
}
```

The canvas is the final feed size. `safeArea` is where essential content must remain. Each `protectedRect` identifies app content that a crop must keep;
use the whole capture when no smaller crop is defensible. Incumbent posts must be valid feed PNGs. Captures must be non-interlaced, 8-bit RGB or opaque
RGBA PNGs so exact output comparison is possible.

## Campaign manifest

Schema version 2 extends the review manifest. `visualAuthority` resolves from the campaign manifest. Each lane's `renderManifest` resolves from its
`sourceDir`.

```json
{
  "schemaVersion": 2,
  "campaign": {
    "id": "2026-09-13-campaign-a",
    "title": "Launch Control campaign A",
    "brief": "Feature-led posts grounded in current product captures",
    "reference": "goldie/social/posts/",
    "visualAuthority": "visual-authority.json"
  },
  "concepts": [
    {
      "taskId": "01a00000-0000-7000-8000-000000000001",
      "seed": "a1b2c3d4e5",
      "title": "A calm way back",
      "feature": "Morning Board recovery",
      "benefit": "A late start can still become a useful plan",
      "approach": "Hook-and-proof carousel",
      "format": "single",
      "assetStatus": "ready",
      "postingOrder": 1,
      "sourceDir": "seed-lab/a1b2c3d4e5",
      "renderManifest": "render-manifest.json",
      "frames": ["out/01-cover.png"]
    }
  ]
}
```

## Render manifest

The renderer writes this receipt after rendering. Frame order and paths must exactly match the campaign manifest. Token arrays contain authority token
names, not raw values.

```json
{
  "schemaVersion": 1,
  "campaignId": "2026-09-13-campaign-a",
  "visualAuthoritySha256": "<sha256>",
  "rendererSha256": "<render.mjs sha256>",
  "frames": [
    {
      "path": "out/01-cover.png",
      "sha256": "<frame sha256>",
      "brandTokens": { "colors": ["paper", "ink", "accent"], "fonts": ["display", "body"] },
      "containsAppUI": true,
      "appCapturePlacements": [
        {
          "captureId": "morning-board",
          "sourceRect": { "x": 0, "y": 100, "width": 980, "height": 1100 },
          "destination": { "x": 50, "y": 125 }
        }
      ]
    }
  ]
}
```

App capture placement is deliberately narrow: source and destination dimensions are identical. The validator compares every placed source pixel against
the final PNG, confirms the protected content remains inside both the crop and campaign safe area, and rejects scaling, overlays, recolouring, or stale
captures. Set `containsAppUI` explicitly on every frame. Use `false` with an empty `appCapturePlacements` array only when the frame contains no visible
product UI.

The posting pack includes only concepts whose exported decision is `keep`. `postingOrder` determines folder order; task completion time and manifest
array order do not.
