---
name: maintain-implementation-notes
description: >-
  Create or update a self-contained implementation-notes HTML decision ledger when the user or repository requires one, or when a long, ambiguous
  implementation needs a durable cold-handoff record. Do not use for routine fixes, straightforward single-ticket work, or evidence already owned
  by a plan, ticket, worklog, feature document, Git history, or PR.
---

# Maintain Implementation Notes

Keep one concise, durable HTML page that explains material interpretation of a specification. It is an optional decision ledger, not a chronological
activity log or a second copy of existing project state.

## Decide whether a ledger is justified

Use a separate ledger only when at least one condition is true:

- the user explicitly requests implementation notes;
- the repository contract requires a particular ledger;
- a long or multi-session implementation has material ambiguity, deviations, trade-offs, or open questions that a maintainer must recover cold, and
  no existing plan, ticket, worklog, ADR, or feature document already owns that information.

Do not create or update a ledger merely because implementation is occurring, a task has several slices, agents are delegated, tests ran, a resource
lane changed state, or commits were created. Routine fixes, straightforward single-ticket work, documentation/configuration edits, and short tasks
should use their existing task plan and repository records. When another artifact is authoritative, update that artifact instead of mirroring it.

If no condition applies, stop without loading the HTML template or creating a file.

## Locate or create the page

1. Read the repository contract and any existing implementation-notes convention before choosing a path or structure.
2. Reuse the existing notes page when the specification or repository already names one. Never create a competing ledger.
3. Otherwise derive `<spec-slug>` from the specification title or feature directory. When the filename is generic, such as `spec.md`, `prd.md`, or
   `requirements.md`, prefer the containing feature directory over the filename.
4. Create `<spec-slug>-implementation-notes.html` beside the specification unless repository guidance names another location.
5. Use [assets/implementation-notes.html](assets/implementation-notes.html) as the starting structure for a new page. Replace every placeholder,
   keep all CSS inline, and use no external scripts, fonts, stylesheets, or images.
6. When a new ledger is justified, create it before the first material implementation decision when practical. If implementation is already under
   way, reconstruct only material decisions from observed artifacts and label that history clearly.

When a page already exists, preserve its established structure and styling. Add missing sections without rewriting unrelated prose.

## Use one writer

Assign one agent as the notes owner. In a multi-agent run, the active ticket coordinator is the only writer; scouts, workers, reviewers, and QA
workers return proposed entries to that coordinator. The run coordinator may add missing bookkeeping after the ticket coordinator stops.

This single-writer rule prevents shared-file conflicts and inconsistent interpretations. Parallel ticket work must serialize notes updates or send
notes fragments to one designated integrator.

## Record material information

Batch updates at accepted milestones, a meaningful decision change, or handoff. Do not update once per ticket or slice by default. Maintain these
sections when they contain information that is not already owned elsewhere:

1. **Status** — only the current milestone or handoff state needed to interpret the decisions; keep commit hashes and routine status in Git, PRs, or
   the repository's tracker.
2. **Design decisions** — ambiguity, chosen interpretation, rejected alternative, and reason.
3. **Deviations** — the exact specification, ticket, glossary, or approved-design expectation; the intentional departure; and why.
4. **Trade-offs** — viable alternatives and why the selected architecture, seam, schema, projection, copy, or workflow won.
5. **Open questions** — affected ticket or slice, the question, impact, and recommended default.
6. **Repeated issues and skill/rule candidates** — what repeated, how often, its cost, the working solution, and the proposed durable destination.
7. **Verification evidence** — only results that establish or change a material decision or acceptance claim, with evidence links.

Write for a maintainer opening the page without the agent conversation. Name relevant ticket headings, specification sections, source paths, seams,
commit hashes, and evidence paths when they improve traceability. Distinguish observations from inferences and unresolved claims.

## Keep the ledger useful

- Keep entries short and dated; place the newest entry first within each section.
- Use stable HTML `id` values for entries that may be referenced later.
- Never delete history silently. Mark an obsolete entry as superseded and link or name its replacement.
- Use `None recorded` when a section is empty so absence is explicit.
- Do not duplicate routine file changes, test invocations, or commit messages unless they carry a decision or acceptance observation.
- Do not mirror plan status, ticket state, worklog entries, resource-lane lifecycle, or the same acceptance text into this page.
- Do not record secrets, credentials, private content, raw user data, or sensitive payloads.
- Do not create a later bookkeeping edit merely to add commit hashes. Git history or PR metadata owns exact hashes.

## Classify repeated work without silently changing policy

Use the repository's self-improvement or guidance-placement rules when they exist. Otherwise classify candidates as:

- **Skill** — reusable cross-repository procedure, tool workflow, or deterministic helper with a clear trigger.
- **Repository rule** — repeated repository-wide behavior that future agents must follow.
- **Feature or architecture documentation** — durable ownership, state, tradeoff, terminology, or subsystem design.
- **No promotion** — one-off evidence, historical counts, hashes, transient failures, or feature detail already owned elsewhere.

Record the candidate and proposed trigger or destination. Do not create a skill, change `ai-rules`, or alter canonical documentation unless the user
explicitly authorizes that separate action.

## Respect authorization and history

Commit selected notes only when commits are authorized, preferably with the implementation containing the decision. Do not create a notes-only
bookkeeping commit for hashes or routine status. Without commit authority, leave the scoped notes change visible and report it.

Never change ticket status, acceptance checkboxes, worklogs, or external systems merely because the notes page mentions them.

## Validate before handoff

When a ledger was selected and changed, before reporting it current:

- confirm the page is one self-contained HTML file with no external dependencies;
- confirm the title, specification reference, dates, and required sections contain no template placeholders;
- inspect the diff so existing prose and unrelated entries remain intact;
- check that every active open question names its affected ticket or slice and recommended default;
- check that superseded entries identify their replacement;
- check that verification claims link to or name the actual evidence;
- open or render the page when practical and confirm it is readable at desktop and narrow widths.
