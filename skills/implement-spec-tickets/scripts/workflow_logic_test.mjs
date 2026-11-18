// Runs ticket-workflow.js against mocked agents to check its control flow. Usage: node scripts/workflow_logic_test.mjs
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'ticket-workflow.js'), 'utf8').replace(/^export const meta/m, 'const meta')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const body = new AsyncFunction('agent', 'parallel', 'phase', 'log', 'args', src)

const base = { ticket: 'T-1', run: '/run', worktree: '/wt', base: 'abc', effort: 'medium' }
const CHECKS = [{ command: 'verify test', exit_code: 0, executed_tests: 10, log: 'l' }]
const ACC = [{ criterion: 'c', met: true, proof: 'Test c' }]
const clean = { status: 'clean', snapshot_before: 's0', snapshot_after: 's0', ledger: [], fixes: [], open: [], checks: [] }
const gatePass = { status: 'pass', checks: CHECKS, executed_tests: 10, baseline_tests: 9, failures: [], fixes: [], production_changes: [] }
const ok = {
  implement: { status: 'done', changed_paths: ['a'], checks: [], acceptance: [], questions: [] },
  verify: { status: 'pass', checks: CHECKS, acceptance: ACC, failures: [], montage: ['m.png'], device_only: [] },
  'copy-check': { findings: [] },
  'review-r1': clean, 'review-r2': clean, 'review-r3': clean,
  gate: gatePass,
  'gate-2': gatePass,
  'verify-fix': { status: 'pass', checks: CHECKS, acceptance: ACC, failures: [] },
  'gate-fix': gatePass,
}

async function run(name, overrides, argOverrides = {}) {
  const calls = []
  const counts = {}
  const agent = async (prompt, opts) => {
    const stage = opts.label.replace(/^T-1 /, '')
    calls.push({ stage, model: opts.model, effort: opts.effort, prompt })
    counts[stage] = (counts[stage] || 0) + 1
    const v = stage in overrides ? overrides[stage] : ok[stage]
    if (v instanceof Error) throw v
    return typeof v === 'function' ? v(counts[stage]) : v
  }
  const parallel = async (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)))
  let result
  try {
    result = await body(agent, parallel, () => {}, () => {}, { ...base, ...argOverrides })
  } catch (e) {
    result = { thrown: String(e.message || e) }
  }
  return { name, result, calls }
}

const fixed = (sev) => ({ ...clean, status: 'fixed', fixes: [{ id: 'F', severity: sev, summary: 's' }] })
const open = (sev, needsUser = false) => ({ ...clean, status: 'open', open: [{ id: 'O', severity: sev, title: 't', ours: 'a', theirs: 'b', needs_user: needsUser }] })
const failingGate = { status: 'fail', checks: CHECKS, executed_tests: 10, baseline_tests: 9, failures: ['t'], fixes: [], production_changes: [] }
const stages = (c) => c.map((x) => x.stage).join(',')

const cases = [
  [await run('happy path', {}), (r, c) => r.status === 'ready' && stages(c) === 'implement,verify,review-r1,gate' && c.every((x) => x.model === 'opus') && c[0].effort === 'medium' && c[2].effort === 'high' && c[3].effort === 'medium'],
  [await run('verify fix', { verify: { status: 'fail', checks: CHECKS, acceptance: ACC, failures: ['x'] }, 'verify-fix': ok.verify }), (r) => r.status === 'ready'],
  [await run('verify pass with a failed check', { verify: { ...ok.verify, checks: [{ command: 'lint', exit_code: 1, log: 'l' }] } }), (r, c) => c.some((x) => x.stage === 'verify-fix')],
  [await run('verify-fix drops the criteria', { verify: { ...ok.verify, acceptance: [{ criterion: 'c', met: false, proof: '' }] }, 'verify-fix': { ...ok.verify, acceptance: [] } }), (r) => r.status === 'failed'],
  [await run('gate pass with a failed check', { gate: { ...gatePass, checks: [{ command: 'lint', exit_code: 1, log: 'l' }] } }), (r, c) => c.some((x) => x.stage === 'gate-fix')],
  [await run('gate itself changed production code (formatter)', { gate: { ...gatePass, production_changes: ['Src/A.swift'] } }), (r, c) => r.status === 'ready' && stages(c).endsWith('gate,review-r2,gate-2')],
  [await run('gate-fix paths without ids after the last round', { 'review-r1': fixed('P2'), 'review-r2': fixed('P2'), 'review-r3': fixed('P3'), gate: failingGate, 'gate-fix': { ...gatePass, production_changes: ['Src/A.swift'] } }), (r) => r.status === 'needs-user' && r.unreviewed_fixes[0].id === 'G1'],
  [await run('verify still failing', { verify: { status: 'fail', checks: CHECKS, acceptance: ACC, failures: ['x'] }, 'verify-fix': { status: 'fail', checks: CHECKS, acceptance: ACC, failures: ['x'] } }), (r) => r.status === 'failed' && r.resume.stage === 'verify-fix'],
  [await run('three rounds, P2 open', { 'review-r1': fixed('P1'), 'review-r2': open('P2'), 'review-r3': open('P2') }), (r) => r.status === 'needs-user' && r.resume.stage === 'user-fix' && r.open.length === 1],
  [await run('last-round P3 fix only', { 'review-r1': fixed('P2'), 'review-r2': fixed('P2'), 'review-r3': fixed('P3') }), (r) => r.status === 'ready' && r.unreviewed_fixes.length === 1],
  [await run('last-round P1 fix', { 'review-r1': fixed('P2'), 'review-r2': fixed('P2'), 'review-r3': fixed('P1') }), (r) => r.status === 'needs-user' && r.unreviewed_fixes.length === 1],
  [await run('P3 open after three rounds', { 'review-r1': open('P3'), 'review-r2': open('P3'), 'review-r3': open('P3') }), (r) => r.status === 'ready' && r.open_p3.length === 1],
  [await run('user item open', { 'review-r1': open('P3', true), 'review-r2': open('P3', true), 'review-r3': open('P3', true) }), (r) => r.status === 'needs-user'],
  [await run('clean in round 2', { 'review-r1': fixed('P1') }), (r, c) => r.status === 'ready' && !c.some((x) => x.stage === 'review-r3')],
  [await run('round 2 prompt reads earlier rounds', { 'review-r1': fixed('P1') }), (r, c) => /r1\.json to r1\.json/.test(c.find((x) => x.stage === 'review-r2').prompt)],
  [await run('review round blocked', { 'review-r1': { ...open('P1'), status: 'blocked', questions: [{ question: 'q', recommendation: 'r', blocking: true }] } }), (r) => r.status === 'blocked' && r.resume.stage === 'review' && r.resume.round === 1 && r.questions.length === 1],
  [await run('blocking question at implement', { implement: { ...ok.implement, questions: [{ question: 'q', recommendation: 'r', blocking: true }] } }), (r) => r.status === 'blocked' && r.stage === 'implement'],
  [await run('blocking question at gate', { gate: { ...gatePass, questions: [{ question: 'q', recommendation: 'r', blocking: true }] } }), (r) => r.status === 'blocked' && r.resume.stage === 'gate'],
  [await run('non-blocking questions collected', { 'review-r1': { ...clean, questions: [{ question: 'q', recommendation: 'r', blocking: false }] } }), (r) => r.status === 'ready' && r.questions.length === 1],
  [await run('dead agent twice', { implement: null }), (r, c) => r.status === 'infra' && r.resume.stage === 'implement' && c.length === 2],
  [await run('dead agent once', { implement: (n) => (n === 1 ? null : ok.implement) }), (r) => r.status === 'ready'],
  [await run('agent throws (token budget spent)', { verify: new Error('budget exhausted') }), (r) => r.status === 'infra' && r.resume.stage === 'verify'],
  [await run('agent throws outside parallel', { 'review-r1': new Error('budget exhausted') }), (r) => r.status === 'infra' && r.resume.stage === 'review' && /budget/.test(r.error)],
  [await run('gate fails twice', { gate: failingGate, 'gate-fix': failingGate }), (r) => r.status === 'failed' && r.resume.stage === 'gate-fix'],
  [await run('gate pass with zero tests', { gate: { ...gatePass, executed_tests: 0 } }), (r, c) => c.some((x) => x.stage === 'gate-fix')],
  [await run('gate pass below baseline', { gate: { ...gatePass, executed_tests: 5, baseline_tests: 9 }, 'gate-fix': { ...gatePass, executed_tests: 5, baseline_tests: 9 } }), (r) => r.status === 'failed'],
  [await run('gate fixed, tests only', { gate: failingGate, 'gate-fix': { ...gatePass, fixes: ['f'] } }), (r, c) => r.status === 'ready' && !c.some((x) => x.stage === 'review-r2')],
  [await run('gate fix changed production code', { gate: failingGate, 'gate-fix': { ...gatePass, fixes: ['f'], production_changes: ['Src/A.swift'] } }), (r, c) => r.status === 'ready' && stages(c).endsWith('gate,gate-fix,review-r2,gate-2')],
  [await run('gate fix after the last round', { 'review-r1': fixed('P2'), 'review-r2': fixed('P2'), 'review-r3': fixed('P3'), gate: failingGate, 'gate-fix': { ...gatePass, fixes: ['f'], production_changes: ['Src/A.swift'] } }), (r) => r.status === 'needs-user' && r.stage === 'gate-fix'],
  [await run('resume user-fix', { 'user-fix': { status: 'done', fixes: [{ summary: 's' }], checks: [] } }, { resume: { stage: 'user-fix' } }), (r, c) => r.status === 'ready' && stages(c) === 'user-fix,gate'],
  [await run('resume user-fix, gate fix changes code', { 'user-fix': { status: 'done', fixes: [], checks: [] }, gate: failingGate, 'gate-fix': { ...gatePass, fixes: ['f'], production_changes: ['x'] } }, { resume: { stage: 'user-fix' } }), (r) => r.status === 'needs-user'],
  [await run('resume review round 2', {}, { resume: { stage: 'review', round: 2 } }), (r, c) => c[0].stage === 'review-r2' && r.status === 'ready'],
  [await run('resume gate-fix', {}, { resume: { stage: 'gate-fix' } }), (r, c) => stages(c) === 'gate-fix'],
  [await run('resume verify-fix', {}, { resume: { stage: 'verify-fix' } }), (r, c) => stages(c) === 'verify-fix,review-r1,gate'],
  [await run('copy check runs beside verify', {}, { copyCheck: true }), (r, c) => r.status === 'ready' && c.some((x) => x.stage === 'copy-check') && !r.notes.length],
  [await run('copy check missing', { 'copy-check': null }, { copyCheck: true }), (r) => r.status === 'ready' && r.notes.length === 1],
  [await run('budget', { 'review-r1': fixed('P2'), 'review-r2': fixed('P2'), 'review-r3': fixed('P3') }, { maxAgents: 4 }), (r) => r.status === 'budget' && r.resume.stage === 'review' && r.resume.round === 3],
  [await run('verify pass with unmet criterion', { verify: { ...ok.verify, acceptance: [{ criterion: 'c', met: false, proof: '' }] } }), (r, c) => c.some((x) => x.stage === 'verify-fix') && r.status === 'ready'],
  [await run('gate fix, then ordinary rounds', { gate: failingGate, 'gate-fix': { ...gatePass, fixes: ['G1'], production_changes: ['x'] }, 'review-r2': fixed('P1') }), (r, c) => r.status === 'ready' && stages(c).endsWith('gate-fix,review-r2,review-r3,gate-2')],
  [await run('gate fix review leaves P3 open in round 2', { gate: failingGate, 'gate-fix': { ...gatePass, fixes: ['G1'], production_changes: ['x'] }, 'review-r2': open('P3') }), (r, c) => stages(c).includes('review-r3')],
  [await run('round count carried in resume', { gate: { ...gatePass, questions: [{ question: 'q', recommendation: 'r', blocking: true }] } }), (r) => r.status === 'blocked' && r.resume.stage === 'gate' && r.resume.roundsDone === 1],
  [await run('resume gate with roundsDone 1 allows review of a gate fix', { gate: failingGate, 'gate-fix': { ...gatePass, fixes: ['G1'], production_changes: ['x'] } }, { resume: { stage: 'gate', roundsDone: 1 } }), (r, c) => r.status === 'ready' && stages(c) === 'gate,gate-fix,review-r2,gate-2'],
  [await run('ready result carries roundsDone', {}), (r) => r.roundsDone === 1],
  [await run('bad resume round', {}, { resume: { stage: 'review', round: 4 } }), (r) => /resume.round/.test(r.thrown || '')],
  [await run('missing args', {}, { base: '' }), (r) => /args.base/.test(r.thrown || '')],
]

let failed = 0
for (const [{ name, result, calls }, check] of cases) {
  let pass = false
  try { pass = check(result, calls) } catch { pass = false }
  if (!pass) failed++
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name}${pass ? '' : ` -> ${JSON.stringify(result)} calls=${stages(calls)}`}`)
}
if (failed) {
  console.log(`${failed} case(s) failed`)
  process.exit(1)
}
console.log('all workflow logic cases passed')
