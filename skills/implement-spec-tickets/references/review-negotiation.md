# Review negotiation

You are the **negotiator** for review round `N` of one ticket. You run the cross-model reviewer, judge every finding against the code,
settle disagreements with the reviewer in its own thread, and apply what you both agree on. `T` below is `RUN/<ticket>`. The reviewer
settings come from `RUN/reviewer.env`; the auto-fix scope and the stop-and-ask list come from `RUN/decisions.md`. A closing review uses the
report-only form at the end.

## 1. Snapshot and prompt

1. Take the **opening snapshot** inside the worktree: `RUN/bin/snapshot.sh` prints a tree id that includes untracked, non-ignored files and
   leaves the index alone. Record it as `snapshot_before`.
2. Choose the scope:
   - **Round 1**: `git diff <base> <snapshot_before>`, with `base` from `ticket.md`.
   - **Round N > 1**: `git diff <r(N-1).snapshot_before> <snapshot_before>`. This is everything changed since the reviewer last looked: the
     previous round's fixes, and any gate fix. Give the full `base` diff as context too.
3. Write `T/reviewer/rN.prompt.md`. It states:
   - **Role**: read-only reviewer of one ticket's change in this repository. It may read files and run read-only commands (`git diff`,
     `git show`, `rg`); it builds nothing and edits nothing.
   - **Scope**: the diff commands with their ids, `T/ticket.md` with the acceptance criteria, and the review-context documents it lists.
   - **What counts**: real defects in this change, each with file, line, what fails and when, and a fix. Covers correctness, data safety and
     migrations, concurrency, privacy, notifications, localization bugs, and missing tests for changed behaviour. Style, naming, process and
     taste stay out. With nothing wrong, `no_findings` is true.
   - **Rounds 2 and 3** also carry:
     - the ledger of every earlier round: agreed fixes to verify, dropped items to leave alone;
     - every item still open, with your new evidence, asking for one entry each in `responses` (`concede`, `maintain` or `revise`);
     - a request for defects the fixes introduced.
4. In round 1, copy-check findings (`T/copy.json`, when present) join the reviewer's findings for judgement.

## 2. Run the reviewer

A reviewer call takes 5 to 20 minutes (killed after `REVIEW_TIMEOUT_MIN`), so run it in the background, then poll in separate Bash calls:

```sh
RUN/bin/bg.sh T/logs/reviewer-rN -- RUN/bin/reviewer.sh <mode> T/reviewer N
RUN/bin/wait.sh T/logs/reviewer-rN        # repeat until DONE; DIED means start it again
```

| When | Mode | Reads → writes |
| --- | --- | --- |
| Round 1 | `new` | `rN.prompt.md` → `rN.json`; starts the ticket's thread (`thread_id`) |
| Rounds 2 and 3 | `next` | `rN.prompt.md` → `rN.json`, same thread |
| The reply turn of a round | `reply` | `rN-reply.prompt.md` → `rN-reply.json`, same thread |
| `next` failed or gave no valid JSON | `new` | the same `rN.prompt.md`, made self-contained (ledger and open items included); a new thread |
| `reply` failed or gave no valid JSON | `new-reply` | the same `rN-reply.prompt.md`, made self-contained; a new thread |

Note any new thread in the ledger. Output shapes: `RUN/bin/schemas/review.json` and `reply.json`.

## 3. Judge every finding

For each new finding, read the code it points at, then decide, with a one-line reason and evidence (file:line, a test, a document rule):

- `accept`: real and in scope.
- `reject`: wrong, already handled, or outside this ticket.
- `partial`: real, but a different fix is better.
- `user`: it needs a decision in an area `decisions.md` lists under stop-and-ask. The item stays open for the user and the round goes on.

Low-severity findings get the same judgement; every finding is read. Carried open items are settled by the reviewer's `responses` with
the same table as new findings (section 4): a conceded `reject` becomes agreed-drop, a conceded or matching `partial` becomes agreed-fix and
is applied in section 5, and a `maintain` with no new argument keeps the item open. An open item the reviewer leaves out of `responses`
stays open.

## 4. Reply once, then settle

If any new finding is `reject` or `partial`, write `T/reviewer/rN-reply.prompt.md`: your decisions with evidence, asking the reviewer for
each one to `concede`, `maintain` (with its counter-argument) or `revise` (with a revised fix). Run `reviewer.sh reply`. One reply turn per
round.

| You | Reviewer | Result |
| --- | --- | --- |
| accept | – | agreed-fix |
| reject | concede | agreed-drop |
| partial | concede, or revise to match | agreed-fix (your version) |
| reject or partial | maintain | Weigh the counter-argument: flip to accept, or the item stays open |
| user | – | open, `needs_user` |

New findings in the reply get your judgement too, without another reply this round; any you reject stay open into the next round.

## 5. Fix what you agreed

- Apply each agreed fix inside the auto-fix scope at its root cause, with a test that fails without it where behaviour changed.
- Run only the checks the fixes affect (`project.md`).
- A fix that would change a documented invariant, a stop-and-ask area or a product decision becomes an open `needs_user` item instead.
- Finish with `RUN/bin/snapshot.sh` again: that id is `snapshot_after`.

## 6. Report

Write `T/rounds/rN.json` and return the same object:

- `status`:
  - `clean`: no agreed fixes this round and nothing open from any round;
  - `fixed`: agreed fixes applied, nothing open;
  - `open`: items still open;
  - `blocked`: only when the round cannot be finished at all (put the question in `questions`, blocking).
- `ledger`: one row per finding of every round so far, with the round it was raised in, severity, your decision, the reviewer's response
  and the result.
- `fixes`: each fix applied this round, with its severity and test.
- `open`: **every** item still unresolved from any round, with both positions and `needs_user`.
- `checks`, `thread_id`, `snapshot_before` and `snapshot_after`.

The workflow decides what follows:

- `clean` ends the review.
- `fixed` or `open` starts the next round while rounds remain.
- After the last round:
  - the ticket **pauses for the user** on any open P0 to P2 item, any `needs_user` item, or a P0/P1 fix made in that round (it was never
    re-reviewed);
  - it **continues** with open P3 items or last-round P2/P3 fixes, which go into the progress note with both positions.

## Report-only form (closing review)

The closing review uses the same steps with three changes:

- the scope is the whole branch, `git diff <merge-base with target> <tip>`, looking for defects that cross tickets;
- section 5 is skipped: nothing is changed;
- the report lists the agreed findings and the open items with both positions, with status `clean` or `report`.
