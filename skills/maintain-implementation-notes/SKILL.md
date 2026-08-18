---
name: maintain-implementation-notes
description: >-
  Create and maintain a self-contained spec-named implementation-notes HTML decision ledger while implementing from a specification or ticket
  set. Use when implementation must preserve material design decisions, intentional deviations, tradeoffs, open questions, repeated work that may
  deserve a skill or repository rule, status, and verification evidence for a maintainer catching up cold. Supports both coordinated multi-ticket
  runs and ordinary single-ticket or single-agent specification work.
---

# Maintain Implementation Notes

Keep one concise, durable HTML page that explains how implementation interpreted the specification. It is a decision and evidence ledger, not a
chronological activity log.

## Locate or create the page

1. Read the repository contract and any existing implementation-notes convention before choosing a path or structure.
2. Reuse the existing notes page when the specification or repository already names one. Never create a competing ledger.
3. Otherwise derive `<spec-slug>` from the specification title or feature directory. When the filename is generic, such as `spec.md`, `prd.md`, or
   `requirements.md`, prefer the containing feature directory over the filename.
4. Create `<spec-slug>-implementation-notes.html` beside the specification unless repository guidance names another location.
5. Use [assets/implementation-notes.html](assets/implementation-notes.html) as the starting structure for a new page. Replace every placeholder,
   keep all CSS inline, and use no external scripts, fonts, stylesheets, or images.
6. Create the page before the first implementation edit. If implementation is already under way, create it immediately from observed artifacts and
   label any reconstructed history clearly; do not pretend it was recorded contemporaneously.

When a page already exists, preserve its established structure and styling. Add missing sections without rewriting unrelated prose.

## Use one writer

Assign one agent as the notes owner. In a multi-agent run, the active ticket coordinator is the only writer; scouts, workers, reviewers, and QA
workers return proposed entries to that coordinator. The run coordinator may add missing bookkeeping after the ticket coordinator stops.

This single-writer rule prevents shared-file conflicts and inconsistent interpretations. Parallel ticket work must serialize notes updates or send
notes fragments to one designated integrator.

## Record material information

Update the page after every material judgment and at least once per ticket or implementation slice. Maintain these sections:

1. **Status** — ticket or slice, state, commit hashes when known, evidence location, and date.
2. **Design decisions** — ambiguity, chosen interpretation, rejected alternative, and reason.
3. **Deviations** — the exact specification, ticket, glossary, or approved-design expectation; the intentional departure; and why.
4. **Trade-offs** — viable alternatives and why the selected architecture, seam, schema, projection, copy, or workflow won.
5. **Open questions** — affected ticket or slice, the question, impact, and recommended default.
6. **Repeated issues and skill/rule candidates** — what repeated, how often, its cost, the working solution, and the proposed durable destination.
7. **Verification evidence** — observed command or flow, exit/result, executed-test count when relevant, device or lane facts, and evidence links.

Write for a maintainer opening the page without the agent conversation. Name relevant ticket headings, specification sections, source paths, seams,
commit hashes, and evidence paths when they improve traceability. Distinguish observations from inferences and unresolved claims.

## Keep the ledger useful

- Keep entries short and dated; place the newest entry first within each section.
- Use stable HTML `id` values for entries that may be referenced later.
- Never delete history silently. Mark an obsolete entry as superseded and link or name its replacement.
- Use `None recorded` when a section is empty so absence is explicit.
- Do not duplicate routine file changes, test invocations, or commit messages unless they carry a decision or acceptance observation.
- Do not record secrets, credentials, private content, raw user data, or sensitive payloads.
- Do not claim that a commit contains its own hash. Add the hash in a later authorized bookkeeping update or leave it explicitly pending.

## Classify repeated work without silently changing policy

Use the repository's self-improvement or guidance-placement rules when they exist. Otherwise classify candidates as:

- **Skill** — reusable cross-repository procedure, tool workflow, or deterministic helper with a clear trigger.
- **Repository rule** — repeated repository-wide behavior that future agents must follow.
- **Feature or architecture documentation** — durable ownership, state, tradeoff, terminology, or subsystem design.
- **No promotion** — one-off evidence, historical counts, hashes, transient failures, or feature detail already owned elsewhere.

Record the candidate and proposed trigger or destination. Do not create a skill, change `ai-rules`, or alter canonical documentation unless the user
explicitly authorizes that separate action.

## Respect authorization and history

Commit the notes only when commits are authorized. When authorized, include the decision entry with the implementation it describes when practical;
use a later bookkeeping commit for hashes that cannot exist beforehand. Without commit authority, leave the scoped notes change visible and report it.

Never change ticket status, acceptance checkboxes, worklogs, or external systems merely because the notes page mentions them.

## Validate before handoff

Before reporting the notes current:

- confirm the page is one self-contained HTML file with no external dependencies;
- confirm the title, specification reference, dates, and required sections contain no template placeholders;
- inspect the diff so existing prose and unrelated entries remain intact;
- check that every active open question names its affected ticket or slice and recommended default;
- check that superseded entries identify their replacement;
- check that verification claims link to or name the actual evidence;
- open or render the page when practical and confirm it is readable at desktop and narrow widths.
