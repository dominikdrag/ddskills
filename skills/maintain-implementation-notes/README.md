# Maintain Implementation Notes

Maintain a self-contained HTML decision and evidence ledger while implementing a specification or ticket set.

The page is for a maintainer catching up without the agent conversation. It records material interpretation, not a chronological transcript of routine edits and commands.

## What it maintains

Unless the repository defines another convention, the skill creates `<spec-slug>-implementation-notes.html` beside the specification. The ledger
keeps these sections current:

- status by ticket or implementation slice;
- design decisions made where the specification was ambiguous;
- intentional deviations and their reasons;
- trade-offs and rejected alternatives;
- open questions with impact and a recommended default;
- repeated issues that may deserve a reusable skill or repository rule;
- verification evidence with observed results and provenance.

Entries are concise, dated, and traceable to specifications, tickets, source paths, commits, or evidence. Obsolete decisions are marked as superseded instead of silently deleted.

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
