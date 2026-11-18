# Lessons behind the rules

Taken from eight earlier multi-ticket runs on two iOS apps (Claude Code workflows, single-session runs and Codex-reviewed runs). Each row is a
rule in this skill and the evidence for it.

| Rule | Why |
| --- | --- |
| A separate verify stage, then a cross-model review | Implementers marked criteria met that a checker then failed: a page that overflowed its footer, archived items counted as missed, a Delete button that did nothing. |
| A Claude negotiator judges findings and replies once | The reviewer conceded or revised within one exchange every time it was challenged. Process-only findings were mostly noise; "real defects with file:line and a concrete failure" produced crisp ones. |
| Fixes are re-reviewed in the next round | Fixes introduced regressions that only a review of the corrective diff found. |
| At most three rounds, then the user decides | Unbounded loops ran for hours; real disagreements needed a product call anyway. |
| One ticket per workflow launch, chosen by the main loop | An outer chain workflow hid stalls, died with its session and could not resume cleanly. |
| Implementers run one at a time in one checkout | Parallel workers in one checkout swept each other's files into commits. |
| The main loop alone commits and updates the tracker | An agent's `git rm --cached` blocked a commit; a message to a running workflow agent produced a duplicate writer. |
| A dead agent is retried once, never treated as a failed check | A null result counted as a failure spawned fixers for work that had not run. |
| Only stop-and-ask decisions block a stage | A rule that stopped on any question halted a run after a successful commit. |
| Questions go to the user in this session, bundled, recommendation first | Questions sent to another session waited about twelve hours; one bundle got approval in one reply. |
| Prompts are frozen; answers live in `decisions.md` | Editing a prompt re-ran finished stages on resume, because prompts are the resume cache key. |
| Long commands run through `bg.sh`/`wait.sh`; a watchdog guards the main loop | Waiting on an untracked process, and permission prompts on ad-hoc shell, stalled runs for about four hours each. |
| Re-claim one labelled simulator per ticket | Free-form claims left nine simulators booted and overloaded the machine. |
| Full suite and snapshot compare once, in the gate | Full checks after every fix cost 3.6 to 5.3 hours per ticket. |
| Zero executed tests, or a snapshot record exit code, prove nothing | "0 passed, 0 failed" hid a compile error; snapshot record mode always exits nonzero. |
| Grep every call site before a signature change | Changing a dependency signature broke call sites one verify cycle at a time. |
| Strings in every shipped language in the same change | Commit hooks reject partial string catalogs. |
| Montage and device-only list for UI tickets, sent with each progress note | Layout and taste problems surfaced only on the owner's phone, days later. |
| Progress note after every ticket | Owners asked "how is it going" three or four times per run. |
| `state.json` re-read before any status claim | A post-compaction summary claimed nothing was waiting while a human-only ticket had open items. |
| Keep the computer awake for the run | A sleeping Mac stopped a run for about eight hours. |
| Reviewer calls pass the model and a read-only sandbox explicitly | The local Codex config defaulted to another model with full disk access; `codex exec resume` has no `-s` flag, so the sandbox goes through `-c sandbox_mode=read-only`. |
