export const meta = {
  name: 'implement-ticket',
  description: 'One ticket: implement, verify, negotiated cross-model review rounds, gate',
  phases: [
    { title: 'Implement', detail: 'build the ticket end to end' },
    { title: 'Verify', detail: 'checks, acceptance rows, copy check' },
    { title: 'Review', detail: 'reviewer rounds negotiated by a Claude agent' },
    { title: 'Gate', detail: 'full suite, snapshots, string and lint checks' },
  ],
}

// Launched once per ticket by the main loop of the implement-spec-tickets skill:
//   Workflow({ scriptPath: '<RUN>/bin/ticket-workflow.js', args })
// args (paths absolute):
//   ticket        tracker id, also the folder name under RUN
//   run           RUN folder (project.md, decisions.md, state.json, bin/, review-negotiation.md)
//   worktree      checkout the agents edit; clean except for this ticket's work
//   base          commit the ticket starts from (HEAD at launch)
//   effort        'medium' | 'high' for the implement stage
//   model         Claude model alias for every agent (default 'opus')
//   maxRounds     review rounds before the user decides (default 3)
//   maxAgents     agent budget for this launch (default 10)
//   ui            true when the ticket changes screens (montage, device-only list)
//   copyCheck     true when the ticket adds or changes user-facing text
//   fullSnapshots true when this ticket's gate runs the full snapshot compare instead of a filtered one
//   resume        null, or the `resume` object a previous launch returned:
//                 { stage: 'implement'|'verify'|'verify-fix'|'review'|'user-fix'|'gate'|'gate-fix', round, roundsDone }
//                 roundsDone (review rounds already completed) defaults to maxRounds when resuming past the review
// Returns a compact object; full results live in RUN/<ticket>/*.json.
//   status: 'ready' | 'blocked' | 'needs-user' | 'failed' | 'infra' | 'budget'

const A = args || {}
for (const k of ['ticket', 'run', 'worktree', 'base', 'effort']) {
  if (!A[k]) throw new Error(`args.${k} is required`)
}
const RUN = A.run
const WT = A.worktree
const T = `${A.run}/${A.ticket}`
const BIN = `${A.run}/bin`
const MODEL = A.model || 'opus'
const MAX_ROUNDS = A.maxRounds === undefined ? 3 : A.maxRounds
const MAX_AGENTS = A.maxAgents === undefined ? 10 : A.maxAgents
const RESUME = A.resume || null
const ORDER = ['implement', 'verify', 'verify-fix', 'review', 'user-fix', 'gate', 'gate-fix']
const START = RESUME ? ORDER.indexOf(RESUME.stage) : 0
if (!Number.isInteger(MAX_ROUNDS) || MAX_ROUNDS < 1) throw new Error('args.maxRounds must be a positive integer')
if (!Number.isInteger(MAX_AGENTS) || MAX_AGENTS < 1) throw new Error('args.maxAgents must be a positive integer')
if (START < 0) throw new Error(`unknown resume stage ${RESUME && RESUME.stage}`)
if (RESUME && RESUME.stage === 'review' && !(Number.isInteger(RESUME.round) && RESUME.round >= 1 && RESUME.round <= MAX_ROUNDS)) {
  throw new Error(`resume.round must be an integer from 1 to ${MAX_ROUNDS}`)
}
const at = (name) => START <= ORDER.indexOf(name)

// ---------- schemas ----------
const STR = { type: 'string' }
const STRS = { type: 'array', items: STR }
const SEV = { type: 'string', enum: ['P0', 'P1', 'P2', 'P3'] }
const arr = (items) => ({ type: 'array', items })
const CHECK = {
  type: 'object',
  properties: { command: STR, exit_code: { type: 'integer' }, executed_tests: { type: 'integer' }, log: STR },
  required: ['command', 'exit_code', 'log'],
}
const ACCEPT = { type: 'object', properties: { criterion: STR, met: { type: 'boolean' }, proof: STR }, required: ['criterion', 'met', 'proof'] }
const QUESTION = {
  type: 'object',
  properties: { question: STR, recommendation: STR, blocking: { type: 'boolean' } },
  required: ['question', 'recommendation', 'blocking'],
}
const FINDING = {
  type: 'object',
  properties: { id: STR, severity: SEV, file: STR, line: { type: 'integer' }, title: STR, failure: STR, fix: STR },
  required: ['id', 'severity', 'file', 'title', 'failure', 'fix'],
}
const IMPL = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'blocked'] }, changed_paths: STRS, checks: arr(CHECK),
    acceptance: arr(ACCEPT), questions: arr(QUESTION), notes: STR,
  },
  required: ['status', 'changed_paths', 'checks', 'acceptance', 'questions'],
}
const VERIFY = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['pass', 'fail', 'blocked'] }, checks: arr(CHECK), acceptance: arr(ACCEPT),
    failures: STRS, montage: STRS, device_only: STRS, questions: arr(QUESTION), notes: STR,
  },
  required: ['status', 'checks', 'acceptance', 'failures'],
}
const COPY = { type: 'object', properties: { findings: arr(FINDING) }, required: ['findings'] }
const ROUND = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['clean', 'fixed', 'open', 'blocked'] },
    thread_id: STR,
    snapshot_before: STR,
    snapshot_after: STR,
    ledger: arr({
      type: 'object',
      properties: {
        id: STR, severity: SEV, title: STR, round_raised: { type: 'integer' },
        decision: { type: 'string', enum: ['accept', 'reject', 'partial', 'user'] },
        reviewer: STR,
        result: { type: 'string', enum: ['agreed-fix', 'agreed-drop', 'open'] },
      },
      required: ['id', 'severity', 'title', 'decision', 'result'],
    }),
    fixes: arr({ type: 'object', properties: { id: STR, severity: SEV, summary: STR, test: STR }, required: ['id', 'severity', 'summary'] }),
    open: arr({
      type: 'object',
      properties: { id: STR, severity: SEV, title: STR, ours: STR, theirs: STR, needs_user: { type: 'boolean' } },
      required: ['id', 'severity', 'title', 'ours', 'theirs', 'needs_user'],
    }),
    checks: arr(CHECK),
    questions: arr(QUESTION),
    notes: STR,
  },
  required: ['status', 'snapshot_before', 'snapshot_after', 'ledger', 'fixes', 'open', 'checks'],
}
const USERFIX = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'blocked'] },
    fixes: arr({ type: 'object', properties: { summary: STR, test: STR }, required: ['summary'] }),
    checks: arr(CHECK), questions: arr(QUESTION), notes: STR,
  },
  required: ['status', 'fixes', 'checks'],
}
const GATE = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['pass', 'fail', 'blocked'] }, checks: arr(CHECK),
    executed_tests: { type: 'integer' }, baseline_tests: { type: 'integer' }, flakes: STRS, failures: STRS,
    fixes: STRS, production_changes: STRS, questions: arr(QUESTION), notes: STR,
  },
  required: ['status', 'checks', 'executed_tests', 'baseline_tests', 'failures', 'production_changes', 'fixes'],
}

// ---------- prompts (frozen: changeable rules live in RUN files, not here) ----------
const common = (stage, file) => `You run one stage of a multi-ticket implementation run inside a Claude Code workflow. Ticket ${A.ticket}; stage: ${stage}.

Read first:
- ${RUN}/project.md: this repository's commands, simulator, build cache, montage method and architecture rules.
- ${RUN}/decisions.md: settled answers, the stop-and-ask list and the review settings for this run; it wins over older text anywhere else.
- ${T}/ticket.md: the ticket, its acceptance criteria, boards, review context and notes.
Work in the worktree ${WT}.

Ownership: the main session owns commits, the git index and the issue tracker. This replaces any rule in CLAUDE.md or AGENTS.md about committing your own work: in this stage you change working-tree files only, use read-only git commands (status, diff, log, show, ls-files, rev-parse), and leave the index empty. Before you return, confirm that \`git rev-parse HEAD\` is still ${A.base} and \`git diff --cached\` is empty; report it in notes if not.

Long commands (builds, test runs, snapshot runs, reviewer calls) run in the background, each in its own Bash call: start with \`${BIN}/bg.sh ${T}/logs/<name> -- <command> [args]\`, then poll with \`${BIN}/wait.sh ${T}/logs/<name>\` (it waits up to 100 seconds) until it prints DONE. DIED means the job ended without an exit code: read its log and start it again. If bg.sh says the job is still running, poll it instead of starting another.

Stop-and-ask: when the work needs a product, privacy, data-format or notification decision that decisions.md and ticket.md leave open, or touches an area decisions.md lists under stop-and-ask, return status "blocked" with the question (blocking: true) and your recommended answer; the main session asks the user. In a review round, follow review-negotiation.md instead: such a finding becomes an open item for the user and the round continues.

Evidence: each check you rely on records its exact command, exit code, executed-test count and raw log path. A run with zero executed tests proves nothing.

Before you return, write your result object as JSON to ${file}.`

const DIFF = `the change since ${A.base}: \`git diff ${A.base}\` plus the untracked files from \`git ls-files --others --exclude-standard\``

const implPrompt = () => `${common('implement', `${T}/implement.json`)}

Build the ticket end to end at every layer it needs, following project.md's architecture rules and the boards and documents ticket.md names. The working tree may already hold work from an earlier attempt of this stage; continue from it.
- Before changing a function, initializer or dependency-client signature, find every call site and update them all in the same pass.
- Test each new behaviour once, at the seam that observes it.
- Give every new user-facing string all the languages the project ships, and update the feature document when behaviour changes.
- Run the focused checks project.md names for what you touched until they pass.
Return "done" with the changed paths, your checks, one acceptance row per criterion in ticket.md (met only with proof) and any questions. Mark a question blocking only when the ticket cannot be finished without its answer.`

const verifyPrompt = () => `${common('verify', `${T}/verify.json`)}

Check the implement stage's work with fresh eyes: its claims count only with proof. Read ${T}/implement.json and ${DIFF}.
1. Regenerate the project when files were added or removed (project.md says how).
2. Run the focused test schemes for the changed code and a snapshot compare for affected screens. Open every changed snapshot image and compare it with the boards ticket.md names.
3. Run the string-catalog, localization, format and lint checks project.md lists.
4. Fill one acceptance row per criterion in ticket.md with proof (test name, snapshot path or file:line); met is false unless proven.${A.ui ? `
5. Make a montage of the changed screens as project.md describes and list its path under montage. List behaviour only a real device can prove under device_only.` : ''}
Return "pass" only when every check passed and every criterion is met; otherwise "fail" with each failure named.`

const verifyFixPrompt = () => `${common('verify-fix', `${T}/verify-fix.json`)}

Read the latest verification result: ${T}/verify-fix.json if an earlier attempt left one, otherwise ${T}/verify.json. Fix the root cause of every failed check and unmet criterion, re-run those checks, and re-fill every acceptance row with proof. Carry over the passing checks, montage and device_only from verify.json so ${T}/verify-fix.json is a complete record. Return "pass" only when every check passes and every criterion is met.`

const copyPrompt = () => `${common('copy-check', `${T}/copy.json`)}

Read-only review of the user-facing text in ${DIFF}: string catalogs and any text in code, in every language the project ships. Report real errors only: grammar or case errors, terms that contradict the project's glossary or term tables, untranslated, truncated or overlong text, broken placeholders. Each finding: id (C1, C2…), severity P1 to P3, file, line, title, the failure and a fix. Change no file other than ${T}/copy.json.`

const roundPrompt = (n) => `${common(`review round ${n} of ${MAX_ROUNDS}`, `${T}/rounds/r${n}.json`)}

You are the negotiator for review round ${n}. Follow ${RUN}/review-negotiation.md exactly: take the opening snapshot, prompt the reviewer through \`${BIN}/reviewer.sh\` (${n === 1 ? 'round 1 opens a new thread' : "this round continues the ticket's thread"}), judge every finding against the code, reply once where you disagree, settle each item with the agreement table, apply the agreed fixes, take the closing snapshot and report.
Inputs: base ${A.base}; reviewer files in ${T}/reviewer/; ${n === 1 ? `the latest verification result (${T}/verify-fix.json if it exists, otherwise ${T}/verify.json)${A.copyCheck ? ` and the copy findings in ${T}/copy.json` : ''}` : `every earlier round in ${T}/rounds/ (r1.json to r${n - 1}.json): their ledgers, open items and snapshot_before`}.`

const userFixPrompt = () => `${common('user-fix', `${T}/user-fix.json`)}

The review limit was reached and the user has answered. Read the last round in ${T}/rounds/, ${T}/gate-fix.json when it exists (its G-numbered fixes), and the section "${A.ticket} review answers" in ${RUN}/decisions.md, which answers each open item and unreviewed fix by its id. Apply exactly what the user decided, each fix with a test where behaviour changes, and run the affected checks. Return "done" with the fixes and checks.`

const gatePrompt = (name) => `${common(name, `${T}/${name}.json`)}

Take a snapshot with \`${BIN}/snapshot.sh\` first. Run the full gate project.md configures on the current tree: the full test suite, the ${A.fullSnapshots ? 'full' : 'filtered'} snapshot compare and the string-catalog and localization checks when the project has them, format and lint in check-only mode. Re-run a failing test once on its own to tell a flake from a real failure; list each check once, with its final result, and name flakes under flakes. Take a second snapshot at the end; if the tree changed, list the changed non-test files under production_changes. Read the baseline executed-test count from ${RUN}/state.json and report it as baseline_tests; an executed count below it counts as a failure unless the diff deliberately removes tests. Return "pass" only when every gate check passed with proof; otherwise "fail" with each failure named.`

const gateFixPrompt = () => `${common('gate-fix', `${T}/gate-fix.json`)}

Read ${T}/gate.json (and ${T}/gate-fix.json if an earlier attempt left one). Fix the root cause of each real failure (a flake that passed alone is not one) and list each fix under fixes as "G1: <summary> (<paths>)", numbering on from any earlier attempt. Under production_changes, list every non-test source file that differs between the last reviewed tree (the snapshot_after of the newest file in ${T}/rounds/) and a fresh \`${BIN}/snapshot.sh\` taken after your fixes (\`git diff --name-only <reviewed id> <fresh id>\`), which includes changes by earlier gate-fix attempts; an empty list when there are none. Then run the whole gate again as project.md configures it (check-only format and lint, each check listed once with its final result) and report baseline_tests from ${RUN}/state.json. Return "pass" only when the whole gate passed.`

// ---------- stage runner ----------
let agentsUsed = 0
async function stage(name, prompt, opts) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    if (agentsUsed >= MAX_AGENTS) throw { kind: 'budget', stage: name }
    agentsUsed++
    let r
    try {
      r = await agent(prompt, { label: `${A.ticket} ${name}`, phase: opts.phase, schema: opts.schema, model: MODEL, effort: opts.effort })
    } catch (e) {
      throw { kind: 'infra', stage: name, error: String((e && e.message) || e) }
    }
    if (r) return r
    log(`${A.ticket} ${name}: no result (attempt ${attempt})`)
  }
  throw { kind: 'infra', stage: name, error: 'agent returned no result twice' }
}

const stageResume = (name) => {
  const m = /^review-r(\d+)$/.exec(name)
  if (m) return { stage: 'review', round: Number(m[1]) }
  if (name === 'copy-check') return { stage: 'verify' }
  if (name === 'gate-2') return { stage: 'gate' }
  return { stage: name }
}

const SERIOUS = ['P0', 'P1']
const blocking = (r) => !!r && (r.status === 'blocked' || ((r.questions || []).some((q) => q.blocking)))
const nonBlocking = (r) => ((r && r.questions) || []).filter((q) => !q.blocking)
const verified = (v) => v.status === 'pass' && !(v.failures || []).length && (v.acceptance || []).length > 0 &&
  v.acceptance.every((a) => a.met && String(a.proof || '').trim()) && (v.checks || []).every((c) => c.exit_code === 0)
const gatePassed = (g) => g.status === 'pass' && g.executed_tests > 0 && !(g.failures || []).length &&
  (g.checks || []).length > 0 && g.checks.every((c) => c.exit_code === 0) &&
  (!g.baseline_tests || g.executed_tests >= g.baseline_tests)

// review rounds already completed before this launch
let lastRound = 0
if (RESUME && RESUME.stage === 'review') lastRound = RESUME.round - 1
else if (START > ORDER.indexOf('review')) {
  const done = RESUME && RESUME.roundsDone !== undefined ? RESUME.roundsDone : A.roundsDone
  lastRound = done === undefined ? MAX_ROUNDS : done
}

const out = { ticket: A.ticket, status: 'ready', files: T, questions: [], notes: [], rounds: [] }
const resumeAt = (name) => ({ ...stageResume(name), roundsDone: lastRound })
const stop = (status, stageName, r, reason, extra = {}) => ({
  ...out, status, stage: stageName, reason, questions: [...out.questions, ...((r && r.questions) || [])],
  failures: (r && r.failures) || [], resume: resumeAt(stageName), ...extra,
})
const blockedAt = (stageName, r) => stop('blocked', stageName, r, 'needs a decision')

async function reviewRound(n) {
  const r = await stage(`review-r${n}`, roundPrompt(n), { phase: 'Review', schema: ROUND, effort: 'high' })
  out.rounds.push({ round: n, status: r.status, fixes: (r.fixes || []).length, open: (r.open || []).length })
  lastRound = n
  out.questions.push(...nonBlocking(r))
  return r
}

// Runs rounds from..MAX_ROUNDS. Returns a stop object when the ticket must pause, otherwise null.
async function reviewLoop(from) {
  for (let n = from; n <= MAX_ROUNDS; n++) {
    const r = await reviewRound(n)
    if (r.status === 'blocked') return blockedAt(`review-r${n}`, r)
    if (r.status === 'clean') return null
    if (n === MAX_ROUNDS) {
      const open = r.open || []
      const unreviewed = r.fixes || []
      const forUser = open.filter((o) => o.needs_user || o.severity !== 'P3')
      const seriousFixes = unreviewed.filter((f) => SERIOUS.includes(f.severity))
      if (forUser.length || seriousFixes.length) {
        return stop('needs-user', `review-r${n}`, r,
          forUser.length ? 'items still open after the last review round' : 'a P0/P1 fix from the last round was never re-reviewed',
          { open, unreviewed_fixes: unreviewed, resume: { stage: 'user-fix', roundsDone: n } })
      }
      out.open_p3 = open
      out.unreviewed_fixes = unreviewed
    }
  }
  return null
}

async function main() {
  // Implement
  if (at('implement')) {
    phase('Implement')
    const impl = await stage('implement', implPrompt(), { phase: 'Implement', schema: IMPL, effort: A.effort })
    if (blocking(impl)) return blockedAt('implement', impl)
    out.questions.push(...nonBlocking(impl))
  }

  // Verify (with the copy check beside it)
  if (at('verify-fix')) {
    phase('Verify')
    let v = null
    if (at('verify')) {
      const [first, copy] = await parallel([
        () => stage('verify', verifyPrompt(), { phase: 'Verify', schema: VERIFY, effort: 'high' }),
        () => (A.copyCheck ? stage('copy-check', copyPrompt(), { phase: 'Verify', schema: COPY, effort: 'medium' }) : Promise.resolve({ findings: [] })),
      ])
      if (!first) return stop('infra', 'verify', null, 'verify agent did not return')
      if (!copy) out.notes.push('copy check did not return; review ran without it')
      v = first
      if (blocking(v)) return blockedAt('verify', v)
    }
    if (!v || !verified(v)) {
      v = await stage('verify-fix', verifyFixPrompt(), { phase: 'Verify', schema: VERIFY, effort: 'high' })
      if (blocking(v)) return blockedAt('verify-fix', v)
      if (!verified(v)) return stop('failed', 'verify-fix', v, 'checks or acceptance criteria still fail after one fix')
    }
    out.questions.push(...nonBlocking(v))
  }

  // Review rounds
  if (at('review')) {
    phase('Review')
    const paused = await reviewLoop(lastRound + 1)
    if (paused) return paused
  }

  // User decisions after the review limit
  if (RESUME && RESUME.stage === 'user-fix') {
    phase('Review')
    const u = await stage('user-fix', userFixPrompt(), { phase: 'Review', schema: USERFIX, effort: 'high' })
    if (blocking(u)) return blockedAt('user-fix', u)
    out.user_fixes = (u.fixes || []).length
    out.questions.push(...nonBlocking(u))
  }

  // Gate
  phase('Gate')
  let g = null
  if (at('gate')) {
    g = await stage('gate', gatePrompt('gate'), { phase: 'Gate', schema: GATE, effort: 'medium' })
    if (blocking(g)) return blockedAt('gate', g)
  }
  let gateStage = 'gate'
  if (!g || !gatePassed(g)) {
    g = await stage('gate-fix', gateFixPrompt(), { phase: 'Gate', schema: GATE, effort: 'high' })
    gateStage = 'gate-fix'
    if (blocking(g)) return blockedAt('gate-fix', g)
    if (!gatePassed(g)) return stop('failed', 'gate-fix', g, 'gate still fails after one fix (or ran fewer tests than the baseline)')
  }
  {
    const prod = g.production_changes || []
    if (prod.length) {
      // production code changed since the last review: the ordinary review loop while rounds remain, then the gate again
      if (lastRound >= MAX_ROUNDS) {
        const fixes = (g.fixes || []).length ? g.fixes : prod.map((p, i) => `G${i + 1}: changed ${p}`)
        return stop('needs-user', gateStage, g, 'production code changed during the gate, after the last review round',
          { unreviewed_fixes: fixes.map((f) => ({ id: (/^(G\d+)/.exec(f) || [])[1] || '', summary: f })), production_changes: prod, resume: { stage: 'user-fix', roundsDone: lastRound } })
      }
      phase('Review')
      const paused = await reviewLoop(lastRound + 1)
      if (paused) return paused
      phase('Gate')
      g = await stage('gate-2', gatePrompt('gate-2'), { phase: 'Gate', schema: GATE, effort: 'medium' })
      if (blocking(g)) return blockedAt('gate-2', g)
      if (!gatePassed(g)) return stop('failed', 'gate-2', g, 'gate fails after the review of the gate fix')
    }
  }
  out.gate = { executed_tests: g.executed_tests, baseline_tests: g.baseline_tests, flakes: g.flakes || [] }
  out.questions.push(...nonBlocking(g))
  out.agents = agentsUsed
  out.roundsDone = lastRound
  return out
}

let result
try {
  result = await main()
} catch (e) {
  if (e && (e.kind === 'infra' || e.kind === 'budget')) {
    result = { ...out, status: e.kind, stage: e.stage, error: e.error, agents: agentsUsed, resume: resumeAt(e.stage) }
  } else {
    throw e
  }
}
return result
