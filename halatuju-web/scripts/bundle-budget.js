#!/usr/bin/env node
/*
 * THE FIRST-LOAD-JS BUDGET — code health H18, closing TD-281.
 *
 * ── WHY THIS IS A SCRIPT AND NOT A TEST ─────────────────────────────────────────────────────
 * H17 cut the median route from 478.5 kB of first-load JS to 255.5 kB by stopping every visitor
 * downloading three languages to read one. It then REFUSED to write a kilobyte figure into
 * `code-standards.json`, and the reason is the whole of TD-281: **that number exists in exactly
 * one place — the route table `next build` prints — and nothing that runs in a test builds.**
 * jest has no build output to read; `code_health.py` does not build either. A number in the
 * ledger that nothing measures reads as enforced and is not, which is worse than no budget.
 *
 * So the reader had to be a thing that sees a BUILD. It runs in the one place that was already
 * building: the Cloud Build deploy gate (`halatuju-web/cloudbuild.yaml`, the `test` step,
 * straight after `npm run gates`). A regression therefore turns the gate RED before the image is
 * pushed, which is the only definition of "enforced" that means anything.
 *
 *   Locally, one command:            npm run bundle-budget
 *   Against a build you already ran: node scripts/bundle-budget.js --from-log build.log
 *
 * ⚠ **IT READS THE BUILD'S OUTPUT ON STDIN AND PRINTS IT STRAIGHT BACK OUT**, so the build log
 * still reaches the console and the Cloud Build viewer. It never starts a build itself: a parser
 * that shells out is a parser with a second failure mode, and `npm run bundle-budget` pipes
 * `next build` into it in one line.
 *
 * ⚠ A FAILED BUILD PRINTS NO ROUTE TABLE, and the MIN_ROUTES floor below turns that into a loud
 * failure rather than a silent pass. That is what makes the pipe safe on a shell without
 * `pipefail`: there is no way for this script to be handed nothing and report success.
 *
 * ── ⚠ WHAT IT CANNOT SEE ────────────────────────────────────────────────────────────────────
 * Written down because a guard whose limits are unwritten gets trusted for things it never
 * claimed:
 *   1. **It does not run in jest, so a developer who only runs `npm test` never sees it.** That
 *      is why the jest half (`codeStandards.test.ts`, "the first-load-JS budget") asserts that
 *      this script exists, that `package.json` exposes it, and that the deploy gate runs it — a
 *      reader nobody invokes is the same failure as a number nobody measures.
 *   2. **It reads what Next.js PRINTS, not what the browser downloads.** Next's figure is the
 *      gzipped JS for the first paint of that route. It excludes CSS, fonts, images, and every
 *      chunk fetched later by an `import()` — so moving weight behind a dynamic import makes this
 *      number fall without making the application smaller. That is usually the right trade (the
 *      panel pays, not the page) and it is still a trade.
 *   3. **It is blind between the floor and the ceiling.** A route may grow from 250 kB to 299 kB
 *      unremarked. That is the `oversize_files` bargain — a ceiling plus a ledger of the named
 *      exceptions — and the MEDIAN budget below is what covers the gap: broad creep across many
 *      routes moves the median even when no single route crosses the ceiling.
 *   4. **87.2 kB IS THE FLOOR** and no route can go below it: React, the Next runtime and the
 *      shared chunk. H17's acceptance asked for "`/` down by roughly three-quarters", which was
 *      arithmetically impossible for that reason. Anyone setting a target here subtracts the
 *      floor first.
 *   5. **One build, one machine.** The figures are deterministic for a given tree, but a Next.js
 *      upgrade can move every route at once. That is a ledger-wide re-record and a deliberate one.
 */
'use strict'

const fs = require('fs')
const path = require('path')

const WEB_ROOT = path.resolve(__dirname, '..')
const BUDGET_PATH = path.join(WEB_ROOT, 'code-standards.json')

/**
 * Any route AT OR ABOVE this must be named in the `first_load_js` ledger with its own number.
 * 300 kB, set 2026-09-20: the median route is ~256 kB and the shared floor is 87 kB, so this is
 * "about 45 kB of page on top of a normal page" — comfortably above ordinary variation and well
 * below the routes that were genuinely heavy when it was set.
 * ⚠ LOWER IT, NEVER RAISE IT. Raising it grants an exemption to every route at once, silently.
 */
const CEILING_KB = 300

/**
 * How far a recorded number may sit ABOVE the real one before the ratchet asks for it to be
 * lowered. Next prints three significant digits, so an unchanged route can land either side of a
 * rounding boundary; 2 kB absorbs that and nothing larger.
 */
const SHRINK_SLACK_KB = 2

/** The same slack for the median, which is one number over ~87 routes and moves less. */
const MEDIAN_SLACK_KB = 2

/**
 * A FLOOR on the parse itself. A regex that matched nothing would report no violations and pass
 * for ever while watching an empty room — the failure this arc has met four times (TD-276). The
 * application had 88 routes on 2026-09-20; 50 leaves room to delete a third of them.
 */
const MIN_ROUTES = 50

/** `┌ ○ /admin/billing    10.4 kB    254 kB` — tree glyph, kind marker, route, size, first load. */
const ROUTE_LINE =
  /^[┌├└│\s]*[○ƒλ●]\s+(\S+)\s+[\d.]+\s*(?:B|kB|MB)\s+([\d.]+)\s*(B|kB|MB)\s*$/
/** `+ First Load JS shared by all            87.2 kB` — the floor under every route. */
const SHARED_LINE = /^\s*\+\s*First Load JS shared by all\s+([\d.]+)\s*(B|kB|MB)\s*$/

const UNIT_KB = { B: 0.001, kB: 1, MB: 1024 }

/** Strip ANSI colour, which Next emits when it thinks it has a terminal (Cloud Build sometimes). */
function plain(text) {
  // eslint-disable-next-line no-control-regex -- stripping ANSI escapes is the whole point here
  return text.replace(/\[[0-9;]*m/g, '')
}

function parseRouteTable(output) {
  const routes = []
  let shared = null
  for (const raw of plain(output).split(/\r?\n/)) {
    const route = ROUTE_LINE.exec(raw)
    if (route) {
      const kb = Number(route[2]) * UNIT_KB[route[3]]
      // `/icon.png` and friends print `0 B` — a static asset, not a JS route. Nothing to budget.
      if (kb > 0) routes.push({ route: route[1], kb })
      continue
    }
    const sharedLine = SHARED_LINE.exec(raw)
    if (sharedLine) shared = Number(sharedLine[1]) * UNIT_KB[sharedLine[2]]
  }
  return { routes, shared }
}

function median(numbers) {
  const sorted = [...numbers].sort((a, b) => a - b)
  const mid = sorted.length >> 1
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

/** Read `budget.first_load_js` + `budget.first_load_js_median_kb`, with a readable failure. */
function readBudget() {
  let file
  try {
    file = JSON.parse(fs.readFileSync(BUDGET_PATH, 'utf8'))
  } catch (err) {
    throw new Error(`cannot read ${BUDGET_PATH}: ${err.message}`)
  }
  const ledger = file.budget && file.budget.first_load_js
  const medianKb = file.budget && file.budget.first_load_js_median_kb
  if (!ledger || typeof ledger !== 'object' || typeof medianKb !== 'number') {
    throw new Error(
      `${BUDGET_PATH}: "budget" must carry a "first_load_js" object and a numeric `
      + '"first_load_js_median_kb". They are the recorded first-load-JS budget; restore them from '
      + 'git rather than deleting the standard to silence it.')
  }
  return { ledger, medianKb }
}

function check(output) {
  const { routes, shared } = parseRouteTable(output)
  const { ledger, medianKb } = readBudget()
  const failures = []
  const notes = []

  // ── the floor ────────────────────────────────────────────────────────────────────────────
  if (routes.length < MIN_ROUTES) {
    throw new Error(
      `the route table parse found ${routes.length} routes, which is below the floor of `
      + `${MIN_ROUTES}. Either the build failed (a failed build prints no table), or it printed `
      + 'nothing this parser recognises. Either way the budget is watching nothing, and passing '
      + 'would be a lie. Read the build output above; if Next.js changed its format, fix '
      + 'ROUTE_LINE in scripts/bundle-budget.js.')
  }

  const byRoute = new Map(routes.map((r) => [r.route, r.kb]))

  // ── 1. nothing new may sit above the ceiling unbudgeted ──────────────────────────────────
  for (const { route, kb } of routes) {
    if (kb >= CEILING_KB && !(route in ledger)) {
      failures.push(
        `${route}: ${kb} kB of first-load JS, over the ${CEILING_KB} kB ceiling and NOT in the `
        + 'ledger. Make the route lighter — the usual cause is a module imported statically that '
        + 'only one panel needs, so reach it through an `import()` instead. ⚠ Do NOT add a line '
        + 'to "first_load_js": that ledger records what was already heavy on 2026-09-20 and may '
        + 'only shrink.')
    }
  }

  // ── 2. a budgeted route may not grow past its number ─────────────────────────────────────
  for (const [route, limit] of Object.entries(ledger)) {
    if (!byRoute.has(route)) {
      failures.push(
        `${route}: in the "first_load_js" ledger but NOT in the build's route table. A budget on `
        + 'a route that no longer exists describes nothing. If the route was deleted, remove the '
        + 'line. If it was RENAMED, declare the move in "_moved" (ledger "first_load_js"), which '
        + 'relabels the frozen entry and grants exactly the room it already had.')
      continue
    }
    const kb = byRoute.get(route)
    if (kb > limit) {
      failures.push(
        `${route}: ${kb} kB of first-load JS, budget ${limit} kB — ${(kb - limit).toFixed(1)} kB `
        + 'over. ⚠ NEVER RAISE THE BUDGET. Find what the route started importing; a static import '
        + 'of a module a single panel needs is paid for by the whole page.')
    } else if (limit > kb + SHRINK_SLACK_KB) {
      notes.push(
        `first_load_js["${route}"]: budget ${limit} kB, build ${kb} kB — LOWER it to ${kb}`)
    }
  }

  // ── 3. the median, which is what broad creep moves ───────────────────────────────────────
  const now = median(routes.map((r) => r.kb))
  if (now > medianKb) {
    failures.push(
      `the MEDIAN route is ${now} kB of first-load JS; the budget is ${medianKb} kB. No single `
      + 'route has to be at fault for this: it is what happens when a module every page imports '
      + 'gets heavier. Find what the shared chunk or the root layout picked up.')
  } else if (medianKb > now + MEDIAN_SLACK_KB) {
    notes.push(`first_load_js_median_kb: budget ${medianKb} kB, build ${now} kB — LOWER it to ${now}`)
  }

  process.stdout.write(
    `\nfirst-load JS: ${routes.length} routes, median ${now} kB, worst `
    + `${Math.max(...routes.map((r) => r.kb))} kB, shared ${shared === null ? '?' : shared} kB\n`)

  if (notes.length) {
    failures.push(
      'A recorded budget now sits above what the build produces. Edit "budget" in '
      + 'halatuju-web/code-standards.json exactly as each line says — this is the ratchet catching '
      + 'up with your improvement, and leaving it loose gives the next change room to put the '
      + `weight back.\n  ${notes.join('\n  ')}`)
  }
  return failures
}

function verdict(output) {
  let failures
  try {
    failures = check(output)
  } catch (err) {
    process.stderr.write(`\nFIRST-LOAD-JS BUDGET: ${err.message}\n`)
    process.exitCode = 1
    return
  }
  if (failures.length) {
    process.stderr.write(
      `\nFIRST-LOAD-JS BUDGET — ${failures.length} problem(s). This is what every visitor `
      + 'downloads before the page can do anything.\n\n'
      + failures.map((f) => `  * ${f}`).join('\n\n') + '\n')
    process.exitCode = 1
    return
  }
  process.stdout.write('first-load-JS budget: ok\n')
}

const fromLog = process.argv.indexOf('--from-log')
if (fromLog >= 0) {
  verdict(fs.readFileSync(process.argv[fromLog + 1], 'utf8'))
} else {
  // The build's own output, echoed straight back out so the log is not swallowed by the pipe.
  const chunks = []
  process.stdin.setEncoding('utf8')
  process.stdin.on('data', (chunk) => { chunks.push(chunk); process.stdout.write(chunk) })
  process.stdin.on('end', () => verdict(chunks.join('')))
}
