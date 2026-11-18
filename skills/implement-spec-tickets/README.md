# Implement Spec Tickets

Implement an approved spec's dependency-ordered tickets in Claude Code. The main session picks each unblocked ticket and launches one
Workflow for it: implement, verify (with an optional copy check), up to three review rounds, and a gate. In each review round a Claude
negotiator runs a second model through the Codex CLI, judges every finding against the code, argues back in the same reviewer thread
until they agree, and applies the agreed fixes; anything still open after the last round goes to the user. Only the main session commits,
updates the issue tracker and talks to the user, after each ticket, with a progress note.

Agent instructions live in [SKILL.md](SKILL.md); `scripts/ticket-workflow.js` runs one ticket and `scripts/closing-workflow.js` the closing checks. Load the references when their branch is active:

- [review negotiation](references/review-negotiation.md): the negotiator's protocol for one round;
- [run files](references/run-files.md): the run folder, `state.json` and `ticket.md`;
- [lessons](references/lessons.md): the evidence from earlier runs behind each rule.

## Requirements

Claude Code with the Workflow tool, the Codex CLI signed in for the reviewer model, Git, Node.js and Python 3. For Apple apps, install
`manage-apple-simulators` and `run-apple-verification-loop` too.

## Verify

```sh
scripts/self_test.sh                         # offline: helpers, schemas, workflow syntax and control flow
REVIEW_MODEL=<model> scripts/reviewer.sh smoke "$(mktemp -d)"   # live: schema output, thread memory, refused write
```

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill implement-spec-tickets \
  -g -a claude-code -y
```

[Back to all skills](../../README.md)
