# ddskills

Personal Codex skills, packaged for installation with the [`skills` CLI](https://github.com/vercel-labs/skills).

## Skills

- [`coordinate-multi-ticket-run`](skills/coordinate-multi-ticket-run/README.md): coordinate an approved dependency-ordered ticket graph through a
  deterministic workflow state machine and evidence-backed agent delivery.
- [`maintain-implementation-notes`](skills/maintain-implementation-notes/README.md): maintain a self-contained HTML decision and verification
  ledger while implementing a specification.
- [`run-apple-verification-loop`](skills/run-apple-verification-loop/README.md): reserve isolated Apple verification lanes and produce exact test,
  snapshot, and runtime evidence.

## Install

The repository is private. Authenticate GitHub access on the machine first, for example with `gh auth login`.

Install all three skills globally for Codex:

```sh
npx skills add dominikdrag/ddskills --skill '*' -g -a codex -y
```

Install one skill:

```sh
npx skills add dominikdrag/ddskills \
  --skill coordinate-multi-ticket-run \
  -g -a codex -y
```

Replace the value passed to `--skill` with any skill listed above.

List the repository's available skills without installing them:

```sh
npx skills add dominikdrag/ddskills --list
```
