export const meta = {
  name: 'close-ticket-run',
  description: 'Closing checks for a ticket run: full gate and screen sweep on the branch tip, plus a report-only cross-ticket review',
  phases: [
    { title: 'Gate', detail: 'full suite and full snapshot compare on the tip, then the screen sweep' },
    { title: 'Review', detail: 'report-only review of the whole branch' },
  ],
}

// Launched once by the main loop of the implement-spec-tickets skill, after the last ticket is committed and the worktree is clean:
//   Workflow({ scriptPath: '<RUN>/bin/closing-workflow.js', args })
// args: run, worktree, target (branch the run merges into), tip (HEAD sha the checks must cover), model (default 'opus'),
//       sweep (true when the run changed screens; default false)
// Writes RUN/closing/{gate,sweep,review}.json. Returns { status: 'ready' | 'failed' | 'mismatch' | 'infra', gate, sweep, review }.

const A = args || {}
for (const k of ['run', 'worktree', 'target', 'tip']) {
  if (!A[k]) throw new Error(`args.${k} is required`)
}
const RUN = A.run
const C = `${A.run}/closing`
const BIN = `${A.run}/bin`
const MODEL = A.model || 'opus'

const STR = { type: 'string' }
const STRS = { type: 'array', items: STR }
const CHECK = {
  type: 'object',
  properties: { command: STR, exit_code: { type: 'integer' }, executed_tests: { type: 'integer' }, log: STR },
  required: ['command', 'exit_code', 'log'],
}
const GATE = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['pass', 'fail', 'mismatch'] }, checks: { type: 'array', items: CHECK },
    executed_tests: { type: 'integer' }, baseline_tests: { type: 'integer' }, failures: STRS, notes: STR,
  },
  required: ['status', 'checks', 'executed_tests', 'baseline_tests', 'failures'],
}
const SWEEP = {
  type: 'object',
  properties: { status: { type: 'string', enum: ['pass', 'issues', 'mismatch'] }, montage: STRS, issues: STRS, notes: STR },
  required: ['status', 'montage', 'issues'],
}
const REPORT = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['clean', 'report', 'mismatch'] },
    agreed: { type: 'array', items: { type: 'object', properties: { id: STR, severity: STR, title: STR, file: STR, fix: STR }, required: ['id', 'severity', 'title'] } },
    open: { type: 'array', items: { type: 'object', properties: { id: STR, severity: STR, title: STR, ours: STR, theirs: STR }, required: ['id', 'severity', 'title', 'ours', 'theirs'] } },
    thread_id: STR, notes: STR,
  },
  required: ['status', 'agreed', 'open'],
}

const common = (stage, file) => `You run the closing ${stage} of a multi-ticket implementation run inside a Claude Code workflow.
Read ${RUN}/project.md (commands and rules) and ${RUN}/decisions.md (settled answers) first. Work in ${A.worktree}, whose HEAD must be ${A.tip} with a clean working tree: confirm both with \`git rev-parse HEAD\` and \`git status --porcelain\` when you start and again before you return; if either differs, return status "mismatch" and name it in notes.
This stage changes no tracked file and writes no git state; the main session owns commits. Long commands run through \`${BIN}/bg.sh ${C}/logs/<name> -- <command>\` and \`${BIN}/wait.sh ${C}/logs/<name>\` (repeat until DONE).
Write your result object as JSON to ${file} before you return.`

const gatePrompt = () => `${common('gate', `${C}/gate.json`)}

Run the full gate project.md configures on the tip: the full test suite, the full snapshot compare and the string-catalog and localization checks when the project has them, format and lint in check-only mode; list each check once, with its final result. Report the baseline executed-test count from ${RUN}/state.json as baseline_tests. Re-run a failing test once on its own to tell a flake from a real failure. Return "pass" only when every check passed with proof and the executed count is at least the baseline.`

const sweepPrompt = () => `${common('screen sweep', `${C}/sweep.json`)}

Render the screens the run added or changed (the tickets in ${RUN}/state.json marked ui) in a second shipped language, at a large accessibility text size, and on the 12-hour clock, as project.md describes. Make one montage per condition, list the paths under montage, and list every clipped, overlapping, untranslated or misformatted element under issues with the screen and condition.`

const reviewPrompt = () => `${common('cross-ticket review', `${C}/review.json`)}

Follow ${RUN}/review-negotiation.md in its report-only form: the scope is \`git diff $(git merge-base ${A.target} ${A.tip}) ${A.tip}\`, the folder for reviewer files is ${C}/reviewer, and you look for defects that cross tickets (one ticket's change breaking another's behaviour, inconsistent data handling, missing migrations or strings). Judge and settle findings as usual, reply once where you disagree, and apply no fixes. Return "clean" when nothing was agreed or left open, otherwise "report" with the agreed findings and the open items with both positions.`

async function run(name, prompt, schema, effort, ph) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    let r
    try {
      r = await agent(prompt, { label: `closing ${name}`, phase: ph, schema, model: MODEL, effort })
    } catch (e) {
      return { infra: String((e && e.message) || e) }
    }
    if (r) return r
    log(`closing ${name}: no result (attempt ${attempt})`)
  }
  return { infra: 'agent returned no result twice' }
}

phase('Gate')
const [checks, review] = await parallel([
  async () => {
    const gate = await run('gate', gatePrompt(), GATE, 'medium', 'Gate')
    if (gate.infra || gate.status !== 'pass' || !A.sweep) return { gate, sweep: null }
    const sweep = await run('sweep', sweepPrompt(), SWEEP, 'medium', 'Gate')
    return { gate, sweep }
  },
  () => run('review', reviewPrompt(), REPORT, 'high', 'Review'),
])

const gate = checks && checks.gate
const sweep = checks && checks.sweep
const infra = !gate || !!gate.infra || !!(sweep && sweep.infra) || !review || !!review.infra
const gateOk = gate && !gate.infra && gate.status === 'pass' && gate.executed_tests > 0 && !(gate.failures || []).length &&
  (gate.checks || []).length > 0 && gate.checks.every((c) => c.exit_code === 0) &&
  (!gate.baseline_tests || gate.executed_tests >= gate.baseline_tests)
const mismatch = [gate, sweep, review].some((x) => x && x.status === 'mismatch')
return {
  status: infra ? 'infra' : mismatch ? 'mismatch' : gateOk ? 'ready' : 'failed',
  gate: gate && { status: gate.status, executed_tests: gate.executed_tests, baseline_tests: gate.baseline_tests, failures: gate.failures, infra: gate.infra },
  sweep: sweep && { status: sweep.status, montage: sweep.montage, issues: sweep.issues, infra: sweep.infra },
  review: review && { status: review.status, agreed: review.agreed, open: review.open, infra: review.infra },
  files: C,
}
