---
name: social-campaign-lab
description: >-
  Coordinate multi-task static social campaign exploration, self-contained visual review boards, and decision-driven revision rounds.
  Use when a campaign needs isolated concept lanes and consolidated Keep, Iterate, or Drop review; do not use for publishing.
---

# Social Campaign Lab

Run a coherent campaign as one coordinator with a configurable number of isolated source tasks. The current task is the coordinator unless the user
explicitly asks for a separate one. Campaign exploration, review, revision, approval, and publishing are separate states.

## Set the boundary

- Ground the brief in current posted assets, product truth, and the requested audience or objective. Inspect those sources before launching tasks.
- State the shared visual language, required output format, prohibited claims, and distinct feature or benefit angles.
- Keep publishing, scheduling, and external account changes out of scope unless the user explicitly authorizes them.
- Treat the requested source-task count as configuration, not a fixed campaign rule.

## Launch isolated lanes

When the user has authorized task creation, launch one Codex task per lane. Choose an execution topology whose outputs the coordinator can actually
read. Shared-checkout tasks are safe only when every lane owns a disjoint seed directory. Worktree outputs are not automatically visible in another
checkout, so record an accessible source path instead of assuming they are shared.

Give every source task:

- the same campaign brief and reference assets;
- a coordinator-assigned lane label, a unique 10-character lowercase alphanumeric seed, and a distinct approach;
- an exclusive `goldie/social/seed-lab/<seed>/` output directory;
- a prohibition on editing shared campaign files or another lane;
- the required deliverables: `concept.md`, `caption.md`, `render.mjs`, and final static PNG frames;
- a requirement to verify every final PNG as 1080x1350, 8-bit RGB, and without alpha.

Record the final Codex `threadId` beside the seed as soon as it is available. If task creation initially returns only a `clientThreadId`, retain the lane
label while resolving the final `threadId`; do not substitute titles or list position as identity. Wait on the recorded task IDs, using returned cursors
when the task API supports them, until every lane completes or needs attention.

## Collect and verify

Wait for every source task. A completed task message is not asset proof: inspect the declared directory and required files. Reject missing artifacts,
files outside the lane, invalid PNGs, or work that contradicts the shared brief.

Create the review manifest only after verification. Read [references/review-manifest.md](references/review-manifest.md) for its schema and refresh
contract. Build the portable board with:

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

Finish by reporting task coverage, asset counts, validation results, decision totals, unresolved revisions, and the exact board path. Never describe the
campaign as published without direct publishing evidence and authorization.
