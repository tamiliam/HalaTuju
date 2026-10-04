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
 *
 * ── TD-304 (2026-10-04): EXACT BYTES, AND THE LAYOUT CODE PRINTED BESIDE THEM ───────────────
 *   * **The budget now reads EXACT gzip bytes, not the printed three-digit figure.** Next prints
 *     "273 kB" for anything from 272.5 to 273.5, so a route could sit 0.5 kB over its line and
 *     pass on rounding (TD-306 met it at 53 bytes). The reader takes each route's PAGE entry from
 *     `.next/app-build-manifest.json` and gzips its chunks as Next does (level 9), and checks
 *     every derived figure against the printed one first: if the two disagree by more than the
 *     print's own rounding, it FAILS — the manifest belongs to another build, or Next changed how
 *     it counts. It never quietly measures something else.
 *   * **The layout code is PRINTED, not budgeted.** Next's figure for an app route is the page
 *     entry only; the chunks only a LAYOUT loads (the root providers, the admin menu) are fetched
 *     on first paint too, and moving weight from a page into a layout lowers the printed number
 *     without making anything lighter. Every run now prints the FIRST-PAINT figure — page plus
 *     every layout above it, JavaScript only — beside the budgeted one. It has no budget of its
 *     own: the first reading (2026-10-04) put its median well over 229 kB, and a new budget is a
 *     new standard, which is the lead's / owner's call (TD-286), never this script's to invent.
 */
'use strict'

const fs = require('fs')
const path = require('path')

const zlib = require('zlib')

const WEB_ROOT = path.resolve(__dirname, '..')
const BUDGET_PATH = path.join(WEB_ROOT, 'code-standards.json')
const NEXT_DIR = path.join(WEB_ROOT, '.next')

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

/** `/sponsor/(portal)/x/page` → `/sponsor/x`: the route a manifest entry prints as. */
function routeOfEntry(entry) {
  const route = entry.replace(/\/page$/, '').split('/').filter((s) => !/^\(.*\)$/.test(s)).join('/')
  return route === '' ? '/' : route
}

/** Every LAYOUT entry above a page entry, root first: `/admin/x/page` → `/layout`, `/admin/layout`… */
function layoutEntries(entry, pages) {
  const segments = entry.split('/').slice(1, -1)
  const keys = ['/layout']
  for (let i = 1; i <= segments.length; i += 1) keys.push(`/${segments.slice(0, i).join('/')}/layout`)
  return keys.filter((k) => k in pages)
}

/** Next's own sum (`gzip-size`, level 9) of a set of chunk files — JavaScript only, each once. */
function gzipBytes(files, sizeOf) {
  return [...new Set(files)].filter((f) => f.endsWith('.js')).reduce((n, f) => n + sizeOf(f), 0)
}

/**
 * The EXACT readings from `.next/app-build-manifest.json`, per printed route: `{ page, firstPaint }`
 * in kB (1 kB = 1000 bytes, as Next prints). `page` is what Next prints, unrounded; `firstPaint`
 * adds every layout above it. `sizeOf` (file → gzip bytes) is injectable for the jest test.
 */
function manifestReadings(manifest, sizeOf) {
  const out = new Map()
  for (const [entry, files] of Object.entries(manifest.pages || {})) {
    if (!entry.endsWith('/page')) continue
    const layouts = layoutEntries(entry, manifest.pages).flatMap((k) => manifest.pages[k])
    out.set(routeOfEntry(entry), {
      page: gzipBytes(files, sizeOf) / 1000,
      firstPaint: gzipBytes([...files, ...layouts], sizeOf) / 1000,
    })
  }
  return out
}

function gzipFromDisk(file) {
  return zlib.gzipSync(fs.readFileSync(path.join(NEXT_DIR, file)), { level: 9 }).length
}

/** How far a printed figure may honestly sit from the exact one: half its last printed digit. */
function printTolerance(printedKb) {
  return printedKb >= 100 ? 0.5 : printedKb >= 10 ? 0.05 : 0.005
}

/**
 * Each route's printed figure replaced by the EXACT one — after proving they are the same
 * measurement. Throws, naming the routes that disagree, rather than budget a different thing.
 */
function exactRoutes(routes, readings) {
  const drift = []
  const exact = routes.map(({ route, kb }) => {
    const r = readings.get(route)
    if (!r) {
      drift.push(`${route}: printed ${kb} kB, no page entry in the manifest`)
      return { route, kb, firstPaint: kb }
    }
    // +0.001: a figure exactly on a rounding boundary (227.5 printed as 228) is honest.
    if (Math.abs(r.page - kb) > printTolerance(kb) + 0.001) {
      drift.push(`${route}: printed ${kb} kB, manifest ${r.page.toFixed(3)} kB`)
    }
    return { route, kb: r.page, firstPaint: r.firstPaint }
  })
  if (drift.length) {
    throw new Error(
      'the exact reading from .next/app-build-manifest.json does not match the route table for '
      + `${drift.length} route(s), so it would budget something other than what Next prints. Was `
      + 'the manifest left by a DIFFERENT build (a --from-log run against a newer .next)? Did a '
      + 'Next.js upgrade change what it counts? Rebuild and re-run; never loosen this check.\n  '
      + drift.slice(0, 10).join('\n  '))
  }
  return exact
}

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

/**
 * THE TIGHTNESS NOTE — TD-300, 2026-09-28. Informational: it never fails the gate.
 *
 * TD-300 was a median budget with NO room under it: exactly 44 of 87 routes sat at or under
 * 256 kB, so the median WAS the 44th route and the next byte on any route at 256 would have turned
 * the deploy gate red for a reason unrelated to the change that added it. Nothing printed that
 * until someone tripped it. This line prints it on every run, so the trap is seen coming:
 *   - how far the median sits under its budget, in kB;
 *   - how many routes sit within 1 kB of the median (the crowd a small shared change moves);
 *   - how many routes may each cross the budget before the MEDIAN does. The median is under the
 *     budget exactly while at least half the routes are, so that count is the real headroom:
 *     at 0, the next route to cross takes the median with it.
 */
function tightness(kbs, now, medianKb) {
  const need = Math.ceil(kbs.length / 2)
  const underBudget = kbs.filter((kb) => kb <= medianKb).length
  const nearMedian = kbs.filter((kb) => Math.abs(kb - now) <= 1).length
  const spare = underBudget - need
  const gap = medianKb - now
  return `median headroom: ${Math.abs(gap).toFixed(1)} kB ${gap >= 0 ? 'under' : 'OVER'} the `
    + `${medianKb} kB budget; `
    + `${nearMedian} route(s) within 1 kB of the median; ${Math.max(spare, 0)} route(s) may cross `
    + `the budget before the median does${spare <= 0 ? ' — ⚠ NONE: the next one takes the median with it' : ''}\n`
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

function readManifest() {
  const file = path.join(NEXT_DIR, 'app-build-manifest.json')
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch (err) {
    throw new Error(`cannot read ${file}: ${err.message}. The exact reading needs the build's `
      + 'own manifest beside its route table (TD-304); run `npm run bundle-budget`, which builds.')
  }
}

const kb3 = (n) => Number(n.toFixed(3))

function check(output) {
  const parsed = parseRouteTable(output)
  const { shared } = parsed
  const { ledger, medianKb } = readBudget()
  const failures = []
  const notes = []

  // ── the floor ────────────────────────────────────────────────────────────────────────────
  if (parsed.routes.length < MIN_ROUTES) {
    throw new Error(
      `the route table parse found ${parsed.routes.length} routes, which is below the floor of `
      + `${MIN_ROUTES}. Either the build failed (a failed build prints no table), or it printed `
      + 'nothing this parser recognises. Either way the budget is watching nothing, and passing '
      + 'would be a lie. Read the build output above; if Next.js changed its format, fix '
      + 'ROUTE_LINE in scripts/bundle-budget.js.')
  }
  // TD-304: from here on every figure is the EXACT one, proven equal to the print first.
  const routes = exactRoutes(parsed.routes, manifestReadings(readManifest(), gzipFromDisk))

  const byRoute = new Map(routes.map((r) => [r.route, r.kb]))

  // ── 1. nothing new may sit above the ceiling unbudgeted ──────────────────────────────────
  for (const { route, kb } of routes) {
    if (kb >= CEILING_KB && !(route in ledger)) {
      failures.push(
        `${route}: ${kb3(kb)} kB of first-load JS, over the ${CEILING_KB} kB ceiling and NOT in the `
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
        `${route}: ${kb3(kb)} kB of first-load JS, budget ${limit} kB — ${(kb - limit).toFixed(3)} kB `
        + 'over. ⚠ NEVER RAISE THE BUDGET. Find what the route started importing; a static import '
        + 'of a module a single panel needs is paid for by the whole page.')
    } else if (limit > kb + SHRINK_SLACK_KB) {
      notes.push(
        `first_load_js["${route}"]: budget ${limit} kB, build ${kb3(kb)} kB — LOWER it to `
        + `${Math.ceil(kb)} (never below the exact figure)`)
    }
  }

  // ── 3. the median, which is what broad creep moves ───────────────────────────────────────
  const now = median(routes.map((r) => r.kb))
  if (now > medianKb) {
    failures.push(
      `the MEDIAN route is ${kb3(now)} kB of first-load JS; the budget is ${medianKb} kB. No single `
      + 'route has to be at fault for this: it is what happens when a module every page imports '
      + 'gets heavier. Find what the shared chunk or the root layout picked up.')
  } else if (medianKb > now + MEDIAN_SLACK_KB) {
    notes.push(`first_load_js_median_kb: budget ${medianKb} kB, build ${kb3(now)} kB — LOWER it to `
      + `${Math.ceil(now)} (never below the exact figure)`)
  }

  process.stdout.write(
    `\nfirst-load JS (exact, page entry — the budgeted figure): ${routes.length} routes, median `
    + `${kb3(now)} kB, worst ${kb3(Math.max(...routes.map((r) => r.kb)))} kB, shared `
    + `${shared === null ? '?' : shared} kB\n`)
  process.stdout.write(tightness(routes.map((r) => r.kb), now, medianKb))
  // TD-304: what the browser fetches on first paint, layouts included. PRINTED, NOT BUDGETED.
  const paint = routes.map((r) => r.firstPaint)
  const worstPaint = routes.reduce((a, b) => (b.firstPaint > a.firstPaint ? b : a))
  process.stdout.write(
    'first-paint JS (page + every layout above it; printed, NOT budgeted): median '
    + `${kb3(median(paint))} kB, worst ${kb3(worstPaint.firstPaint)} kB (${worstPaint.route}); `
    + `layout code adds ${kb3(median(paint) - now)} kB to the median\n`)

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

module.exports = { routeOfEntry, layoutEntries, manifestReadings, exactRoutes, printTolerance }

const fromLog = process.argv.indexOf('--from-log')
if (require.main !== module) {
  // Required by its jest test (src/lib/__tests__/bundleBudgetReader.test.ts): read nothing.
} else if (fromLog >= 0) {
  verdict(fs.readFileSync(process.argv[fromLog + 1], 'utf8'))
} else {
  // The build's own output, echoed straight back out so the log is not swallowed by the pipe.
  const chunks = []
  process.stdin.setEncoding('utf8')
  process.stdin.on('data', (chunk) => { chunks.push(chunk); process.stdout.write(chunk) })
  process.stdin.on('end', () => verdict(chunks.join('')))
}
