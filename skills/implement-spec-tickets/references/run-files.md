# Run files

Everything the run needs to survive a compaction, a reboot or a new session lives under `RUN`. The main loop writes the top-level files;
workflow agents write only inside their ticket folder.

```
RUN/
  project.md               repository commands and rules for agents (main loop, once)
  decisions.md             answers, stop-and-ask list, review settings, user overrides (main loop, append as answers arrive)
  reviewer.env             REVIEW_MODEL=…, REVIEW_EFFORT=…, REVIEW_CWD=<worktree> (main loop, once)
  state.json               source of truth for progress (main loop, after every launch and commit)
  for-user.md              non-blocking questions and notes queued for the next progress message (main loop)
  review-negotiation.md    copied from the skill (setup)
  bin/                     copied from the skill's scripts/ (setup)
  baseline/                baseline evidence
  <ticket>/
    ticket.md              the ticket as agents see it (main loop, before launch)
    implement.json  verify.json  verify-fix.json  copy.json  user-fix.json
    gate.json  gate-fix.json  gate-2.json     one result per stage, never overwritten by a later stage (agents)
    rounds/rN.json         negotiator result per review round (agents)
    reviewer/              thread_id, rN.prompt.md, rN.json, rN.events.jsonl, rN-reply.prompt.md, rN-reply.json (agents)
    logs/                  bg.sh logs and exit files (agents)
    commit-msg.txt         (main loop)
  closing/                 gate.json, sweep.json, review.json, reviewer/, logs/ (closing workflow)
```

## state.json

```json
{
  "spec": "ABC-10",
  "branch": "…",
  "target": "main",
  "udid": "…",
  "baseline": { "tests": 1875, "suite_minutes": 14, "snapshots": 388, "compare_minutes": 6 },
  "order": ["ABC-11", "ABC-12"],
  "human_only": { "ABC-20": "pending | done (confirmed by the user)" },
  "tickets": {
    "ABC-11": {
      "effort": "high", "ui": false, "copyCheck": false, "fullSnapshots": false,
      "status": "pending | running | blocked | needs-user | failed | committed | skipped",
      "base": "<sha>", "sha": "<commit>", "run_id": "wf_…", "resume": null, "roundsDone": 2,
      "accepted": 3, "rejected": 1, "open": [], "questions": []
    }
  }
}
```

## ticket.md

Written before each launch. It holds:

- the tracker title and body, with the acceptance criteria as a numbered list;
- the boards, specs and documents to follow, by absolute path;
- **Review context**: the documents the reviewer should read (domain glossary, the decision records involved, the feature document);
- notes: the answers from `decisions.md` that apply, and the stop-and-ask areas this ticket touches.

## Why files, not prompts

Workflow prompts are frozen in `ticket-workflow.js` and carry only paths. Rules that change mid-run (answers, overrides, settings) live in
`decisions.md`, so an answer reaches the next stage without editing a prompt.
