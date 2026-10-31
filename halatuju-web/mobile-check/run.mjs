/**
 * `npm run mobile-check [-- --update] [-- <playwright args>]` (Mobile M0).
 *
 * 1. Clears the last run's results, then runs the Playwright check (`pages.pw.ts`). A cell FAILS
 *    when it is worse than `baseline.json`; see `worseThan` in targets.ts for exactly what "worse"
 *    means.
 * 2. Prints what got BETTER, so a fix is seen as well as a regression.
 * 3. With `--update` (or MOBILE_UPDATE=1), rewrites `baseline.json` from this run — and only ever
 *    LOWERS a number. A cell measured for the first time is added as measured. A cell not measured
 *    this run (the sandbox, when the base is the live site) keeps its old numbers.
 *
 * ⚠ MOBILE_ALLOW_WORSE=1 lets `--update` RAISE numbers too. It exists for the cases where the
 * measurement moved and the page did not: a new measuring rule, a Chromium upgrade, a fixture that
 * now shows more of a screen. It is NOT for accepting a regression. Whoever sets it says why in the
 * commit message, and the reviewer checks the screenshots for every number that rose.
 */
import { spawnSync } from 'node:child_process'
import * as fs from 'node:fs'
import { createRequire } from 'node:module'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const RESULTS = path.join(HERE, 'output', 'results')
const BASELINE = path.join(HERE, 'baseline.json')

const args = process.argv.slice(2)
const update = args.includes('--update') || process.env.MOBILE_UPDATE === '1'
const allowWorse = process.env.MOBILE_ALLOW_WORSE === '1'
const passThrough = args.filter((a) => a !== '--update')

// Last run's results AND screenshots go, so the folder only ever shows this run.
fs.rmSync(RESULTS, { recursive: true, force: true })
fs.rmSync(path.join(HERE, 'output', 'screenshots'), { recursive: true, force: true })

const cli = createRequire(import.meta.url).resolve('@playwright/test/cli')
const run = spawnSync(process.execPath, [cli, 'test', '-c', path.join(HERE, 'playwright.config.ts'), ...passThrough],
  { stdio: 'inherit', env: process.env })

const results = fs.existsSync(RESULTS)
  ? fs.readdirSync(RESULTS).filter((f) => f.endsWith('.json'))
    .map((f) => JSON.parse(fs.readFileSync(path.join(RESULTS, f), 'utf8')))
  : []
const baseline = fs.existsSync(BASELINE) ? JSON.parse(fs.readFileSync(BASELINE, 'utf8')) : { cells: {} }
const NUMBERS = ['overflow', 'smallInputs', 'smallTargets']

const better = []
for (const r of results) {
  const old = baseline.cells[r.key]
  if (!old) continue
  const moved = NUMBERS.filter((n) => r[n] < old[n]).map((n) => `${n} ${old[n]} → ${r[n]}`)
  if (moved.length) better.push(`  ${r.key}: ${moved.join(', ')}`)
}
console.log(`\nmobile-check: ${results.length} cell(s) measured.`)
if (better.length) console.log(`Better than the baseline (${better.length}):\n${better.join('\n')}`)

if (update) {
  const cells = { ...baseline.cells }
  let raised = 0
  for (const r of results) {
    const old = cells[r.key]
    const now = Object.fromEntries(NUMBERS.map((n) => [n, r[n]]))
    if (!old || allowWorse) {
      if (old && NUMBERS.some((n) => now[n] > old[n])) raised++
      cells[r.key] = now
    } else {
      cells[r.key] = Object.fromEntries(NUMBERS.map((n) => [n, Math.min(old[n], now[n])]))
    }
  }
  const sorted = Object.fromEntries(Object.keys(cells).sort().map((k) => [k, cells[k]]))
  const measured = { ...(baseline.measured || {}) }
  const publicBase = process.env.MOBILE_PUBLIC_BASE || process.env.MOBILE_BASE || 'http://localhost:3100'
  if (results.some((r) => !r.key.startsWith('sandbox:'))) measured.public = publicBase
  if (results.some((r) => r.key.startsWith('sandbox:'))) measured.sandbox = process.env.MOBILE_BASE || 'http://localhost:3100'
  measured.updated = new Date().toISOString().slice(0, 10)
  fs.writeFileSync(BASELINE, `${JSON.stringify({
    _how_this_works: 'The mobile-check ratchet (Mobile M0). One cell per page × width × language: '
      + 'overflow = sideways scroll in CSS px, smallInputs = text fields under 16 px, smallTargets = '
      + 'controls under 44 × 44 px. A run fails when a cell gets worse. `npm run mobile-check -- '
      + '--update` rewrites this file and only ever LOWERS numbers (MOBILE_ALLOW_WORSE=1 is the '
      + 'documented exception — see mobile-check/run.mjs). Never edit by hand.',
    measured,
    cells: sorted,
  }, null, 2)}\n`)
  console.log(`Baseline rewritten: ${Object.keys(sorted).length} cell(s)`
    + (allowWorse ? `, ${raised} raised under MOBILE_ALLOW_WORSE=1.` : ', nothing raised.'))
}

process.exit(run.status ?? 1)
