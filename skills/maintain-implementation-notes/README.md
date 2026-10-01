# Maintain Implementation Notes

Maintain a self-contained HTML decision ledger when a long or ambiguous implementation needs a durable cold-handoff record, or when the user or
repository explicitly requires one. Routine implementation should use its existing plan, ticket, worklog, feature documentation, Git history, and PR.

The page is for a maintainer catching up without the agent conversation. It records material interpretation, not a chronological transcript of routine edits and commands.

## What it maintains

When a separate ledger is justified and the repository defines no convention, the skill creates `<spec-slug>-implementation-notes.html` beside the
specification. It records material information not already owned elsewhere:

- current milestone or handoff state needed to interpret decisions;
- design decisions made where the specification was ambiguous;
- intentional deviations and their reasons;
- trade-offs and rejected alternatives;
- open questions with impact and a recommended default;
- repeated issues that may deserve a reusable skill or repository rule;
- verification evidence that establishes a material decision or acceptance claim.

Updates are batched at meaningful milestones or handoff. The ledger does not mirror routine commands, device claim state, plan or ticket status, commit hashes,
or acceptance text already recorded elsewhere. Obsolete decisions are marked as superseded instead of silently deleted.

## Multi-agent ownership

One agent writes the ledger at a time. In a coordinated ticket run, the active ticket coordinator is the writer. Scouts, workers, reviewers, and QA
agents return proposed entries instead of editing the shared file.

The bundled [HTML template](assets/implementation-notes.html) is self-contained, responsive, and has no external fonts, scripts, stylesheets, or images.

## Install

```sh
npx skills add dominikdrag/ddskills \
  --skill maintain-implementation-notes \
  -g -a codex -y
```

See the executable agent instructions in [SKILL.md](SKILL.md).

[Back to all skills](../../README.md)
