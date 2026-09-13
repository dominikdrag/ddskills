---
name: social-campaign-lab
description: >-
  Coordinate visually consistent static social campaigns from isolated concept lanes through review and a deterministic posting pack.
  Use when supplied product captures must stay pixel-exact and campaign work needs consolidated Keep, Iterate, or Drop decisions; do not use for publishing.
---

# Social Campaign Lab

Run a coherent campaign as one coordinator with a configurable number of isolated source tasks. The current task is the coordinator unless the user
explicitly asks for a separate one. Campaign exploration, review, revision, approval, and publishing are separate states.

## Establish one visual authority

- Ground the brief in current posted assets, product truth, and the requested audience or objective. Inspect those sources before launching tasks.
- Create one tracked `visual-authority.json` before launching lanes. It is the campaign's shared authority for incumbent posts, brand tokens, feed and safe-area
  geometry, and captured product references. Read [references/campaign-contract.md](references/campaign-contract.md) for the schema and evidence contract.
- Hash the approved authority file and every incumbent or capture it names. Revalidate those hashes after any change; do not silently let one lane follow a
  different authority revision.
- State the required output format, prohibited claims, and distinct feature or benefit angles.
- Keep publishing, scheduling, and external account changes out of scope unless the user explicitly authorizes them.
- Treat the requested source-task count as configuration, not a fixed campaign rule.

Visible product UI must come from an authority-listed screenshot, snapshot, or captured frame. Never redraw, generate, typeset, or infer app controls,
copy, counts, data, or state. Place supplied app pixels at 1:1 from the recorded crop: no scaling, recolouring, retouching, or overlays. A crop is acceptable
only when it preserves the capture's protected rectangle and places that protected content inside the campaign safe area.

## Launch isolated lanes

When the user has authorized task creation, launch one Codex task per lane. Choose an execution topology whose outputs the coordinator can actually
read. Shared-checkout tasks are safe only when every lane owns a disjoint seed directory. Worktree outputs are not automatically visible in another
checkout, so record an accessible source path instead of assuming they are shared.

Give every source task:

- the same campaign brief and exact `visual-authority.json` path and SHA-256;
- a coordinator-assigned lane label, a unique 10-character lowercase alphanumeric seed, and a distinct approach;
- an exclusive `goldie/social/seed-lab/<seed>/` output directory;
- a prohibition on editing shared campaign files or another lane;
- the required deliverables: `concept.md`, `caption.md`, `render.mjs`, `render-manifest.json`, and final static PNG frames;
- a requirement that the render manifest records output and renderer hashes, used brand-token names, and every app-capture placement.

Record the final Codex `threadId` beside the seed as soon as it is available. If task creation initially returns only a `clientThreadId`, retain the lane
label while resolving the final `threadId`; do not substitute titles or list position as identity. Wait on the recorded task IDs, using returned cursors
when the task API supports them, until every lane completes or needs attention.

## Collect and verify

Wait for every source task. A completed task message is not asset proof. Create the schema-v2 campaign manifest, then run:

```sh
node .agents/skills/social-campaign-lab/scripts/campaign-assets.mjs validate \
  --manifest <campaign-manifest.json> \
  --report <validation-report.json>
```

Reject missing artifacts, stale hashes, paths outside a lane, invalid PNGs, unapproved brand tokens, unsafe crops, altered app pixels, or any lane bound to
a different visual-authority hash. This validation proves the recorded artifacts satisfy the contract; it does not replace full-size visual review.

Build the portable board only after validation. Read [references/review-manifest.md](references/review-manifest.md) for its decision and refresh contract:

```sh
node .agents/skills/social-campaign-lab/scripts/build-review-board.mjs \
  --manifest <campaign-manifest.json> \
  --output <review-board.html> \
  [--decisions <exported-decisions.json>]
```

The builder embeds every PNG and includes search, format and review-status filters, full-size inspection, verdicts, notes, JSON import/export, and a
copyable routing summary. Its stable decision key is `campaignId + taskId + seed`; keep all three unchanged when a source task replaces its frames.

## Route a review round

Export the board's decision JSON before rebuilding it or moving review to another browser. Route the verdict and full note together:

| Verdict | Note | Coordinator action |
| --- | --- | --- |
| Keep | Empty | No revision. |
| Keep | Actionable | Ask the originating task for only that fix. |
| Iterate | Any | Ask the originating task to revise; include the note verbatim and flag a missing note. |
| Drop | Any | Preserve the note, but do not request replacement unless explicitly asked. |
| Unreviewed | Any | Do not route. |

Address each relevant task by the manifest's exact `taskId`; include its seed and stable output directory in the message. Wait for replacements, re-run
the same verification, update frame paths or descriptive metadata without changing identity, and rebuild with `--decisions` so verdicts and notes
remain embedded. A revised asset does not silently change its verdict.

## Assemble the handoff

After all intended posts have a `Keep` decision and an explicit unique `postingOrder`, assemble one immutable, numbered handoff directory:

```sh
node .agents/skills/social-campaign-lab/scripts/campaign-assets.mjs assemble \
  --manifest <campaign-manifest.json> \
  --decisions <exported-decisions.json> \
  --output <posting-pack-directory>
```

The assembler revalidates first, refuses an existing output path, copies captions and frames without changing their bytes, and writes deterministic
`README.md` and `posting-pack.json` provenance. Inspect the resulting directory and validation summary before handoff.

Finish by reporting task coverage, asset counts, validation results, decision totals, unresolved revisions, and the exact board and posting-pack paths.
Never describe the campaign as scheduled or published without direct evidence and authorization.
