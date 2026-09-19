/**
 * Code health H4 — THE STANDARDS, AS TESTS. The web half.
 *
 * **Why this file exists.** The owner's ruling, 2026-09-18: *"once this is built, future builds
 * would ensure the standards are maintained to prevent bugs or inefficiencies creeping in."*
 * Since H2 the whole jest suite runs inside the Cloud Build deploy gate, so **a standard written
 * as a test cannot be broken by a change that deploys.** A standard written in a document can,
 * and this project's own record says documents are what rot.
 *
 * `Settings/_tools/code_health.py` MEASURES and reports a trend; this file REFUSES. The
 * definitions are deliberately taken from that tool — what counts as source versus test, which
 * directories are skipped, how a suppression or a skipped test or an unused dependency is
 * detected — so the readings in `docs/code-health.md` and the limits enforced here can never
 * describe two different codebases. Where a number differs it is because a THRESHOLD differs,
 * and that is stated at the constant.
 *
 * **⚠ THIS IS A SOURCE-READING TEST, and the house rule says a source-shape guard is not evidence
 * of behaviour.** That rule is right and this file does not break it: the subject here IS the
 * shape of the source. There is nothing to render. It is deliberately ONE file rather than six,
 * so the project gains one source-reading test and not a habit of them — `guard%` is itself a
 * reading the tool watches.
 *
 * **THE RATCHET, AND WHY IT HAS NO GIT.** The Cloud Build checkout is `depth-1`: there is no
 * parent commit to compare against, so "is this worse than before?" is answered by a committed
 * file instead — `halatuju-web/code-standards.json`, which sits INSIDE the web folder so it is
 * inside the path filter of the trigger that runs these tests. It holds two blocks:
 *
 *   - `baseline` — FROZEN. Every number and every ledger as H4 found them on 2026-09-19.
 *   - `budget`   — the CURRENT limits. Starts identical to `baseline`, only ever gets tighter.
 *
 * Four rules hold it shut, and all four are asserted below:
 *   1. `actual <= budget`         — the code may not get worse.
 *   2. `budget <= baseline`       — a limit may never be raised above where H4 found it, and a
 *                                   ledger may never gain a member it did not have then.
 *   3. `budget <= actual + slack` — TIGHTNESS. A limit may not sit loose above reality; when the
 *                                   code improves this FAILS until the budget is lowered.
 *   4. the `baseline` block is PINNED by a SHA-256 held in this file, so rewriting history needs
 *      a second, deliberate edit in a second file that a reviewer cannot miss.
 *
 * **⚠ THE LOOPHOLE THAT REMAINS, STATED.** Without git this file cannot see the PREVIOUS commit,
 * only the frozen baseline. A number ratcheted down to 20 can be raised back to 30 in the same
 * commit that makes the code worse, as long as 30 is still at or below the 2026-09-19 baseline.
 * What it CANNOT do is exceed the baseline, add a ledger member, or leave a budget loose. The
 * remaining window is caught by the lead's sprint-close tool, which does have git.
 *
 * **NOT IN H4, on purpose** (later sprints add them): first-load-JS and database-query budgets
 * are H18; "a new test file may not hand-build a ScholarshipApplication" is H5. Style and
 * formatting are out of scope for ever — a formatter pass rewrites every file and proves nothing
 * about bugs.
 */
import * as crypto from 'crypto'
import * as fs from 'fs'
import * as path from 'path'

// ── Where things are ─────────────────────────────────────────────────────────────────────────
/** `…/halatuju-web`. Three levels up from `src/lib/__tests__/this_file.ts`. */
const WEB_ROOT = path.resolve(__dirname, '..', '..', '..')
const REPO_ROOT = path.resolve(WEB_ROOT, '..')
const SRC_ROOT = path.join(WEB_ROOT, 'src')
const BUDGET_PATH = path.join(WEB_ROOT, 'code-standards.json')

// ── The definitions, taken from Settings/_tools/code_health.py ───────────────────────────────
/** Verbatim from `code_health.EXCLUDE_DIRS`. */
const EXCLUDE_DIRS = new Set([
  'migrations', 'node_modules', '.next', '__pycache__', 'archive', '.worktrees', '.git',
  'venv', '.venv', 'staticfiles', 'coverage', 'out', 'build', 'dist',
])
const TEST_DIRS = new Set(['tests', '__tests__'])
/** Verbatim from `code_health.DEP_IGNORE` — the framework itself, imported implicitly. */
const DEP_IGNORE = new Set(['next', 'react', 'react-dom'])
/** Verbatim from `code_health.SUPPRESS_TS` and `code_health.SKIP_TS`. */
const TS_IGNORE = /@ts-ignore/
const TS_EXPECT_ERROR = /@ts-expect-error/
const ANY_ANNOTATION = /:\s*any\b/
const ANY_CAST = /\bas\s+any\b/
const SKIP_TS = /\b(it|test|describe)\.(skip|todo)\b|\bx(it|describe|test)\(/
const ESLINT_DISABLE = /eslint-disable(?:-next-line|-line)?/

// ── The thresholds this file OWNS ────────────────────────────────────────────────────────────
/**
 * ⚠ The tool reports files over 1,000 lines (`code_health.BIG_FILE_LINES`); the STANDARD is 600.
 * Different jobs: 1,000 is "one of the worst files in the project", a triage list a person reads;
 * 600 is "no human or agent should have to hold this in one head", a line a NEW file may not
 * cross. Because the standard is stricter this ledger is longer than the tool's list.
 */
const MAX_FILE_LINES = 600
/**
 * One fixed allowance for a file already in the ledger: a hotfix on a 4,000-line file must not be
 * blocked by a guard whose real target is the NEXT giant file. The recorded number can never
 * rise, so total creep is capped at 20 lines for ever, per file, however many hotfixes there are.
 */
const FILE_GROWTH_ALLOWANCE = 20
/** Tightness: a file that has shrunk by more than this is no longer described by its entry. */
const FILE_SHRINK_SLACK = 50
/**
 * Tightness slack per counted number. Two matches `code_health.TOL_COUNT`, the tolerance the
 * trend tool already uses for a count. ZERO where the number is already small enough that every
 * unit matters — a budget of 1 with a slack of 2 would sit loose above a real answer of 0, which
 * is exactly the looseness rule 3 exists to stop.
 */
const COUNT_SLACK: Record<string, number> = {
  ts_ignore: 0,
  ts_expect_error: 0,
  any: 0,
  eslint_disable: 2,
  unused_dependencies: 0,
  skip_sites: 0,
}

/**
 * The SHA-256 of the canonical JSON of the `baseline` block (sorted keys, no whitespace, UTF-8).
 * ⚠ If you are here because this failed: the baseline is the frozen record of what H4 found. It
 * is not a number to keep current. Lower a limit in `budget`, never in `baseline`.
 */
const BASELINE_SHA256 = '788bd164999fd2428101b4457b215d27a8ce16cd6a9bde2b1361a888eb400f5e'

/**
 * ⚠ THIS FILE EXCLUDES ITSELF FROM THE TEST-FILE SKIP SCAN, and only from that scan. It has to:
 * the skip patterns are written out in full here, so they appear as source text on the very lines
 * that DEFINE them. A guard that fires on its own documentation gets deleted within a month. The
 * cost is a hole exactly one file wide, which "the self-exclusion is one file wide" keeps honest.
 */
const SELF = 'src/lib/__tests__/codeStandards.test.ts'

// ── Reading the tree, once ───────────────────────────────────────────────────────────────────
/**
 * ⚠ CRLF is collapsed on every read. The authoring machine is Windows (411 of the .ts files are
 * CRLF today) and the gate runs on Linux; a line count or a regex that saw a stray `\r` would
 * give two different answers for the same file. `code_health._read` opens with `newline=None` for
 * exactly this reason. Never match a multi-line literal against this text — match line by line.
 */
function read(file: string): string {
  return fs.readFileSync(file, 'utf8').replace(/\r\n?/g, '\n')
}

/** `splitlines()`'s count, not `split('\n')`'s: a trailing newline does not add a line. */
function countLines(text: string): number {
  const lines = text.split('\n')
  if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop()
  return lines.length
}

/**
 * Relative to the web root, forward slashes ALWAYS, so a ledger key written on Windows is the
 * same string the Linux gate computes. ⚠ Never glob these paths: real folders here are named
 * `[id]` and `(portal)`, which a glob reads as a character class and a group.
 */
function rel(file: string): string {
  return path.relative(WEB_ROOT, file).split(path.sep).join('/')
}

/** `code_health.is_test_path`, less the Python half. */
function isTestPath(relpath: string): boolean {
  const parts = relpath.split('/')
  const base = parts[parts.length - 1]
  if (parts.slice(0, -1).some((p) => TEST_DIRS.has(p))) return true
  return /\.test\.(ts|tsx|js|jsx)$/.test(base)
}

/** `code_health.walk`: every file under root with one of exts, EXCLUDE_DIRS skipped. */
function walk(root: string, exts: string[]): string[] {
  const out: string[] = []
  const stack: string[] = [root]
  while (stack.length) {
    const dir = stack.pop() as string
    let entries: fs.Dirent[] = []
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true })
    } catch {
      entries = []
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        if (!EXCLUDE_DIRS.has(entry.name)) stack.push(full)
      } else if (exts.some((e) => entry.name.endsWith(e))) {
        out.push(full)
      }
    }
  }
  return out.sort()
}

function countOf(text: string, pattern: RegExp): number {
  return [...text.matchAll(new RegExp(pattern.source, 'g'))].length
}

// ── What counts as a comment line ────────────────────────────────────────────────────────────
/**
 * Which lines of a file are comment, as a mask.
 *
 * ⚠ A marker test on each line ALONE is not enough, and `src/app/layout.tsx` is the proof: its
 * JSX comment opens with `{` + block-open on one line, runs four lines of plain prose with no
 * marker at all, and closes on its own line. Judged line by line, the four best lines of the
 * explanation are invisible and the disable below it reads as reasonless — a guard crying wolf
 * over the most carefully justified suppression in the codebase. So the block state is tracked.
 *
 * The known limit: a block-open sequence inside a string literal or a regex would be read as
 * opening a comment. No file in `src` does that today, and the floor tests would notice the
 * collapse in counts if one ever did.
 */
function commentMask(lines: string[]): boolean[] {
  const mask: boolean[] = []
  let inBlock = false
  for (const line of lines) {
    const trimmed = line.trim()
    if (inBlock) {
      mask.push(true)
      if (trimmed.includes('*/')) inBlock = false
      continue
    }
    const opensBlock = trimmed.startsWith('/*') || trimmed.startsWith('{/*')
    mask.push(trimmed.startsWith('//') || opensBlock)
    if (opensBlock && !trimmed.slice(2).includes('*/')) inBlock = true
  }
  return mask
}

// ── eslint-disable: does it carry a written reason? ──────────────────────────────────────────

// Strip the comment markers — line, block-open, block-continue, block-close, and the JSX-wrapped
// forms of both — from one comment line, leaving the prose behind.
function stripMarkers(line: string): string {
  return line.trim()
    .replace(/^\{?\/\*+/, '')
    .replace(/^\/\/+/, '')
    .replace(/^\*+/, '')
    .replace(/\*+\/\}?$/, '')
    .trim()
}

/**
 * The reason rule, stated once: a disable carries a reason when there is explanatory text on the
 * SAME line after `--` (eslint's own convention), or a comment block on the line(s) directly
 * ABOVE with at least three words of prose in it. Three words rather than "any comment at all",
 * because a lone block-close marker on the preceding line is not a reason — but the block it
 * closes may well be, so the walk goes up through the whole run of comment lines.
 * `src/app/layout.tsx` is exactly that shape and is why this is not a single-line look-back.
 */
const MIN_REASON_WORDS = 3

/**
 * ⚠ **THE KEY-ECHO FALLBACK: `t('some.key') || 'English fallback'`.**
 *
 * `t` returns THE KEY ITSELF when it cannot resolve one (`getNestedValue` in `lib/i18n.tsx`),
 * and a dotted key is a non-empty string — so `||` never fires and the student reads
 * `authGate.icNotMe` where a button label should be. Four keys shipped exactly that way on the
 * sign-in gate and rendered as raw dotted paths for months; nothing was red, because every
 * other use of the idiom happened to have a key that existed (TD-259). The fallback was not
 * broken in one place, it was never a fallback anywhere.
 *
 * `tOr(t, key, fallback)` in `lib/i18n.tsx` is the replacement, and it knows about the echo.
 *
 * ⚠ **THIS MUST NOT CRY WOLF ON `a || b`.** It matches only a call to a bare `t(` — not
 * `count(x) || 0`, not `searchParams.get('q') || ''`, not `tOr(…)` — immediately followed by
 * `||`. `(?:[^()]|\([^()]*\))*` allows ONE level of nesting inside the argument, which is what
 * a template literal like `t(\`a.${b}\`)` needs. Known limit, stated: a `t(` whose `||` is on
 * the NEXT line is not seen (the scan is line by line), and neither is `obj.t(k) || x` — both
 * are shapes nothing in `src` uses. `the idiom rule, proven both ways` pins both directions.
 */
const KEY_ECHO_FALLBACK = /(^|[^\w.$])t\((?:[^()]|\([^()]*\))*\)\s*\|\|/

function hasReason(lines: string[], mask: boolean[], index: number, after: string): boolean {
  if (after.includes('--')) return true
  const above: string[] = []
  for (let i = index - 1; i >= 0 && mask[i]; i -= 1) {
    above.unshift(stripMarkers(lines[i]))
  }
  const prose = above.filter((l) => !l.includes('eslint-disable')).join(' ')
  return (prose.match(/[A-Za-z]{2,}/g) || []).length >= MIN_REASON_WORDS
}

interface Disable { key: string; where: string; reasoned: boolean }

/** Key = `path::rule::nth`. NOT a line number: a line number moves the moment anything above it
 *  changes, and a ledger that must be rewritten after every edit is a ledger nobody reads. */
function disablesIn(relpath: string, text: string): Disable[] {
  const lines = text.split('\n')
  const mask = commentMask(lines)
  const nth: Record<string, number> = {}
  const out: Disable[] = []
  lines.forEach((line, i) => {
    for (const match of line.matchAll(new RegExp(ESLINT_DISABLE.source, 'g'))) {
      const at = (match.index ?? 0) + match[0].length
      const after = line.slice(at)
      const ruleText = after.split('--')[0].replace(/\*+\/\}?/, '').trim()
      const rule = (ruleText.split(',')[0] || '').trim() || 'all'
      const stem = `${relpath}::${rule}`
      nth[stem] = (nth[stem] || 0) + 1
      out.push({
        key: `${stem}::${nth[stem]}`,
        where: `${relpath}:${i + 1}`,
        reasoned: hasReason(lines, mask, i, after),
      })
    }
  })
  return out
}

// ── Mirrors: a rule copied from the backend must name the test that guards it ────────────────
/** A comment claiming a duplicated rule. */
const MIRROR = /mirror|keep\s+(?:the\s+two\s+)?in\s+(?:sync|step)/i
/**
 * ⚠ THE EXCLUSION, DEFINED PRECISELY, because the opposite of a mirror is written with the same
 * word. `documentLimits.ts` says "THE LIMITS ARE SERVED, NOT MIRRORED"; `adminStaff.ts` says
 * "there is deliberately no server mirror of it"; `admin-auth-context.tsx` says "never a
 * hard-coded mirror of the platform's 7". Those are the GOOD pattern — the very thing H9 and H10
 * convert the others into — and a guard that flagged them would fight the work it exists to
 * support.
 *
 * ⚠ The honest cost, stated: this is judged over the whole comment block, so a block that BOTH
 * claims a mirror and disclaims one is excused (two exist today, and both say plainly that the
 * server is the authority). An author could also evade the guard by writing "no mirror" in a
 * block that does mirror. This guard is against forgetting, not against a determined evader.
 */
const NOT_MIRRORED: RegExp[] = [
  /\bnot\s+mirrored\b/i,
  /\bno\s+(?:[\w-]+\s+){0,2}mirror(?:s|ed|ing)?\b/i,
  /\bnever\s+(?:[\w-]+\s+){0,3}mirror(?:s|ed|ing)?\b/i,
  /\bmirrors?\s+no\b/i,
]
/** The marker that discharges the claim, e.g. `drift-test: halatuju-web/src/lib/__tests__/x.ts`. */
const DRIFT_TEST = /drift-test:\s*(\S+)/

interface CommentBlock { start: number; text: string }

/** Consecutive comment lines, as one block. A claim and the marker that discharges it have to be
 *  able to sit in the same docblock without the author counting lines. */
function commentBlocks(text: string): CommentBlock[] {
  const lines = text.split('\n')
  const mask = commentMask(lines)
  const out: CommentBlock[] = []
  let current: string[] = []
  let start = 0
  const flush = () => {
    if (current.length) out.push({ start, text: current.join(' ') })
    current = []
  }
  lines.forEach((line, i) => {
    if (mask[i]) {
      if (!current.length) start = i + 1
      current.push(stripMarkers(line))
    } else {
      flush()
    }
  })
  flush()
  return out
}

interface MirrorClaim { key: string; where: string; guarded: boolean; driftTest: string | null }

/**
 * The key is the first eight words of the block, lowercased — NOT a line number, which moves the
 * moment anything above it changes, and not the whole text, which changes on every reword. It is
 * stable while the block moves or its tail is edited, and changes only when its opening sentence
 * is rewritten — at which point the author is restating the claim and should restate the
 * justification with it. A `::2` suffix separates two blocks in one file that open identically.
 */
function mirrorKey(block: CommentBlock): string {
  return (block.text.toLowerCase().match(/[a-z0-9_]+/g) || []).slice(0, 8).join('-')
}

function mirrorsIn(relpath: string, text: string): MirrorClaim[] {
  const seen: Record<string, number> = {}
  const out: MirrorClaim[] = []
  for (const block of commentBlocks(text)) {
    if (!MIRROR.test(block.text)) continue
    if (NOT_MIRRORED.some((r) => r.test(block.text))) continue
    const stem = mirrorKey(block)
    seen[stem] = (seen[stem] || 0) + 1
    const marker = block.text.match(DRIFT_TEST)
    out.push({
      key: `${relpath}::${stem}${seen[stem] > 1 ? `::${seen[stem]}` : ''}`,
      where: `${relpath}:${block.start}`,
      guarded: marker !== null,
      driftTest: marker ? marker[1] : null,
    })
  }
  return out
}

// ── The scan ─────────────────────────────────────────────────────────────────────────────────
export interface WebScan {
  sourceFiles: number
  testFiles: number
  excusedFromTheSkipScan: string[]
  oversizeFiles: Record<string, number>
  eslintDisables: Disable[]
  mirrors: MirrorClaim[]
  unusedDependencies: string[]
  skipSites: string[]
  brokenDriftTestMarkers: string[]
  keyEchoFallbacks: string[]
  counts: Record<string, number>
}

/**
 * `code_health.m_unused_deps`, definition for definition: the framework packages are excused, the
 * haystack is every source-ish file under `src` PLUS the four root config files, and a package
 * counts as imported when its name appears inside quotes (or as a path prefix).
 */
function findUnusedDependencies(): string[] {
  const pkg = JSON.parse(read(path.join(WEB_ROOT, 'package.json'))) as {
    dependencies?: Record<string, string>
  }
  const deps = Object.keys(pkg.dependencies || {}).sort()
  const haystack: string[] = walk(SRC_ROOT, ['.ts', '.tsx', '.js', '.jsx', '.css', '.mjs']).map(read)
  for (const name of fs.readdirSync(WEB_ROOT).sort()) {
    if (/^(tailwind|next|postcss|jest)\.config\./.test(name)) {
      haystack.push(read(path.join(WEB_ROOT, name)))
    }
  }
  const blob = haystack.join('\n')
  return deps.filter((d) => {
    if (DEP_IGNORE.has(d)) return false
    const escaped = d.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return !new RegExp(`['"]${escaped}['"/]`).test(blob)
  })
}

function sortedNumbers(o: Record<string, number>): Record<string, number> {
  const out: Record<string, number> = {}
  for (const k of Object.keys(o).sort()) out[k] = o[k]
  return out
}

export function scanWeb(): WebScan {
  const all = walk(SRC_ROOT, ['.ts', '.tsx'])
  const sources = all.filter((f) => !isTestPath(rel(f)))
  const tests = all.filter((f) => isTestPath(rel(f)))

  const oversizeFiles: Record<string, number> = {}
  const eslintDisables: Disable[] = []
  const mirrors: MirrorClaim[] = []
  const brokenDriftTestMarkers: string[] = []
  const keyEchoFallbacks: string[] = []
  let tsIgnore = 0
  let tsExpectError = 0
  let anyUses = 0

  for (const file of sources) {
    const relpath = rel(file)
    const text = read(file)
    const lines = countLines(text)
    if (lines > MAX_FILE_LINES) oversizeFiles[relpath] = lines
    tsIgnore += countOf(text, TS_IGNORE)
    tsExpectError += countOf(text, TS_EXPECT_ERROR)
    anyUses += countOf(text, ANY_ANNOTATION) + countOf(text, ANY_CAST)
    eslintDisables.push(...disablesIn(relpath, text))
    const mask = commentMask(text.split('\n'))
    text.split('\n').forEach((line, i) => {
      // A comment explaining the idiom is prose, not a use of it — the same rule the i18n
      // guard applies, and the reason this file can document what it refuses.
      if (!mask[i] && KEY_ECHO_FALLBACK.test(line)) {
        keyEchoFallbacks.push(`${relpath}:${i + 1}  ${line.trim().slice(0, 110)}`)
      }
    })
    if (relpath.startsWith('src/lib/')) {
      for (const claim of mirrorsIn(relpath, text)) {
        mirrors.push(claim)
        if (claim.driftTest && !fs.existsSync(path.join(REPO_ROOT, claim.driftTest))) {
          brokenDriftTestMarkers.push(
            `${claim.where} names ${claim.driftTest}, which does not exist`)
        }
      }
    }
  }

  const excusedFromTheSkipScan: string[] = []
  const skipSites: string[] = []
  for (const file of tests) {
    const relpath = rel(file)
    if (relpath === SELF) {
      excusedFromTheSkipScan.push(relpath)
      continue
    }
    read(file).split('\n').forEach((line, i) => {
      if (SKIP_TS.test(line)) skipSites.push(`${relpath}:${i + 1}  ${line.trim().slice(0, 110)}`)
    })
  }

  const unusedDependencies = findUnusedDependencies()

  return {
    sourceFiles: sources.length,
    testFiles: tests.length,
    excusedFromTheSkipScan,
    oversizeFiles: sortedNumbers(oversizeFiles),
    eslintDisables,
    mirrors,
    unusedDependencies,
    skipSites,
    brokenDriftTestMarkers,
    keyEchoFallbacks,
    counts: {
      ts_ignore: tsIgnore,
      ts_expect_error: tsExpectError,
      any: anyUses,
      eslint_disable: eslintDisables.length,
      unused_dependencies: unusedDependencies.length,
      skip_sites: skipSites.length,
    },
  }
}

// ── The budget file ──────────────────────────────────────────────────────────────────────────
export interface StandardsBlock {
  recorded_on?: string
  last_tightened_on?: string
  counts: Record<string, number>
  oversize_files: Record<string, number>
  eslint_disable_without_reason: string[]
  unguarded_mirrors: string[]
}
export interface StandardsFile {
  _how_this_works: string
  baseline: StandardsBlock
  budget: StandardsBlock
}

/**
 * The exact bytes the pin is taken over: sorted keys, no whitespace. The Python half of H4 uses
 * `json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=False)`, which is this.
 */
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value !== null && typeof value === 'object') {
    const o = value as Record<string, unknown>
    const pairs = Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`)
    return `{${pairs.join(',')}}`
  }
  return JSON.stringify(value)
}

export function sha256(text: string): string {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex')
}

const FILE = JSON.parse(read(BUDGET_PATH)) as StandardsFile
const BUDGET = FILE.budget
const BASELINE = FILE.baseline
const SCAN = scanWeb()
const EDIT = 'Edit "budget" in halatuju-web/code-standards.json exactly as each line says.'

/** A message is the whole user interface of a failing standard, so each assertion compares a
 *  string that is EMPTY when the standard holds and is the full instruction when it does not. */
function say(broken: boolean, lines: string[]): string {
  return broken ? lines.join(' ') : ''
}

// ── THE FLOOR ────────────────────────────────────────────────────────────────────────────────
describe('the scan actually found the code (the floor)', () => {
  test('the tree is where this file thinks it is', () => {
    expect(fs.existsSync(path.join(SRC_ROOT, 'lib'))).toBe(true)
    expect(SCAN.sourceFiles).toBeGreaterThan(300)
    expect(SCAN.testFiles).toBeGreaterThan(100)
  })

  test('the readings are not all empty', () => {
    // A scan that matched nothing would report no violations and pass for ever while watching
    // nothing — the failure mode every guard in this repo carries a floor against.
    expect(Object.keys(SCAN.oversizeFiles).length).toBeGreaterThan(5)
    expect(SCAN.eslintDisables.length).toBeGreaterThan(20)
    expect(SCAN.mirrors.length).toBeGreaterThan(20)
  })

  test('the self-exclusion is one file wide', () => {
    expect(SCAN.excusedFromTheSkipScan).toEqual([SELF])
  })

  test('the budget file is the shape this file expects', () => {
    expect(typeof FILE._how_this_works).toBe('string')
    for (const block of [BASELINE, BUDGET]) {
      expect(typeof block.counts).toBe('object')
      expect(typeof block.oversize_files).toBe('object')
      expect(Array.isArray(block.eslint_disable_without_reason)).toBe(true)
      expect(Array.isArray(block.unguarded_mirrors)).toBe(true)
    }
  })
})

// ── STANDARD: no new giant file ──────────────────────────────────────────────────────────────
describe('no new giant file', () => {
  test(`no unlisted source file passes ${MAX_FILE_LINES} lines`, () => {
    const unlisted = Object.keys(SCAN.oversizeFiles)
      .filter((f) => !(f in BUDGET.oversize_files))
      .map((f) => `${SCAN.oversizeFiles[f]} lines  ${f}`)
    expect(say(unlisted.length > 0, [
      `Source file(s) over ${MAX_FILE_LINES} lines that are not in the oversize_files ledger.`,
      'A file this size is where bugs land: nobody holds it in one head and nobody reviews it',
      'properly. SPLIT IT into modules under the limit, in its own commit with no behaviour',
      'change. Do NOT add it to the ledger — the ledger is frozen at what H4 found and may only',
      `shrink.\n${unlisted.join('\n')}`,
    ])).toBe('')
  })

  test('a listed file has not grown past its allowance', () => {
    const grown = Object.keys(BUDGET.oversize_files)
      .filter((f) => (SCAN.oversizeFiles[f] ?? 0) > BUDGET.oversize_files[f] + FILE_GROWTH_ALLOWANCE)
      .map((f) => `${f}: ${SCAN.oversizeFiles[f]} lines, recorded at ${BUDGET.oversize_files[f]}, `
        + `allowance ${BUDGET.oversize_files[f] + FILE_GROWTH_ALLOWANCE}`)
    expect(say(grown.length > 0, [
      `File(s) in the oversize_files ledger have grown more than ${FILE_GROWTH_ALLOWANCE} lines`,
      'past their recorded size. That allowance is for a hotfix, not for new work. SPLIT THE FILE',
      'FIRST, in its own commit, then add your change to the smaller module. The recorded number',
      `may only go down.\n${grown.join('\n')}`,
    ])).toBe('')
  })

  test('a listed file that shrank has its entry lowered', () => {
    // Tightness: a budget sitting loose above reality re-permits the growth the split removed.
    const stale = Object.keys(BUDGET.oversize_files).flatMap((f) => {
      const limit = BUDGET.oversize_files[f]
      const now = SCAN.oversizeFiles[f]
      if (now === undefined) {
        return [`${f}: now ${MAX_FILE_LINES} lines or fewer (or gone) — REMOVE this entry from `
          + '"oversize_files" in budget']
      }
      if (limit > now + FILE_SHRINK_SLACK) {
        return [`${f}: now ${now} lines but recorded at ${limit} — LOWER this entry to ${now}`]
      }
      return []
    })
    expect(say(stale.length > 0, [
      `The oversize_files budget is looser than the code. ${EDIT}`,
      'This is the ratchet catching up with your improvement, not a complaint about it.',
      `\n${stale.join('\n')}`,
    ])).toBe('')
  })
})

// ── STANDARD: no blind spots ─────────────────────────────────────────────────────────────────
describe('no blind spots', () => {
  test('there is no @ts-ignore anywhere in source', () => {
    expect(say(SCAN.counts.ts_ignore > BUDGET.counts.ts_ignore, [
      `@ts-ignore found ${SCAN.counts.ts_ignore} time(s); the budget is`,
      `${BUDGET.counts.ts_ignore}. @ts-ignore silences the type checker AND hides the next error`,
      'on that line for ever. Fix the type, or use @ts-expect-error, which at least fails once the',
      'error goes away. The budget may not be raised.',
    ])).toBe('')
  })

  test('the @ts-expect-error count has not risen', () => {
    expect(say(SCAN.counts.ts_expect_error > BUDGET.counts.ts_expect_error, [
      `@ts-expect-error count is ${SCAN.counts.ts_expect_error}; the budget is`,
      `${BUDGET.counts.ts_expect_error}. Fix the type rather than expecting the error.`,
      'The budget may not be raised.',
    ])).toBe('')
  })

  test('the `any` count has not risen', () => {
    expect(say(SCAN.counts.any > BUDGET.counts.any, [
      '`: any` / `as any` count is', `${SCAN.counts.any}; the budget is ${BUDGET.counts.any}.`,
      'Every `any` turns the type checker off for that value, and tsc is a deploy gate here.',
      'Type it properly — `unknown` plus a narrowing check if the shape is genuinely unknown.',
      'The budget may not be raised.',
    ])).toBe('')
  })
})

// ── STANDARD: every eslint-disable carries a written reason ──────────────────────────────────
describe('every eslint-disable carries a written reason', () => {
  const reasonless = SCAN.eslintDisables.filter((d) => !d.reasoned)

  test('a disable without a reason is either new or on the ledger', () => {
    const ledger = new Set(BUDGET.eslint_disable_without_reason)
    const unlisted = reasonless.filter((d) => !ledger.has(d.key))
      .map((d) => `${d.where}  ${d.key}`)
    expect(say(unlisted.length > 0, [
      'eslint-disable comment(s) with no written reason. A rule switched off without a reason is',
      'indistinguishable from a rule switched off by accident, and nobody can ever tell whether it',
      'is still needed. ADD THE REASON: put ` -- why` at the end of the same line, or a sentence in',
      'a comment on the line above. Do NOT add the disable to the ledger — the ledger is frozen at',
      `what H4 found and may only shrink.\n${unlisted.join('\n')}`,
    ])).toBe('')
  })

  test('the ledger only shrinks: a disable that gained a reason is removed', () => {
    const live = new Set(reasonless.map((d) => d.key))
    const stale = BUDGET.eslint_disable_without_reason.filter((k) => !live.has(k))
    expect(say(stale.length > 0, [
      'These are no longer reasonless disables — each was given a reason, removed, or the rule it',
      'names changed. REMOVE each line from "eslint_disable_without_reason" in budget, so the list',
      `cannot outlive the debt it records. ${EDIT}\n${stale.join('\n')}`,
    ])).toBe('')
  })

  test('the total eslint-disable count has not risen', () => {
    expect(say(SCAN.counts.eslint_disable > BUDGET.counts.eslint_disable, [
      `eslint-disable count is ${SCAN.counts.eslint_disable}; the budget is`,
      `${BUDGET.counts.eslint_disable}. A reason makes a suppression honest, not free. Fix what`,
      'the rule is objecting to — on 2026-07-30 two disables naming a rule this config never loads',
      'failed the web build while the api deployed. The budget may not be raised.',
    ])).toBe('')
  })
})

// ── STANDARD: no unguarded mirror ────────────────────────────────────────────────────────────
describe('no unguarded mirror', () => {
  const unguarded = SCAN.mirrors.filter((m) => !m.guarded)

  test('a comment claiming a mirrored rule names the drift test that guards it', () => {
    const ledger = new Set(BUDGET.unguarded_mirrors)
    const unlisted = unguarded.filter((m) => !ledger.has(m.key)).map((m) => `${m.where}  ${m.key}`)
    expect(say(unlisted.length > 0, [
      'Comment(s) in src/lib claiming a rule is mirrored or kept in sync, with nothing enforcing',
      'it. A comment asking two files to stay in step is a request; only a test is a rule — the',
      'SOFT_EVIDENCE denylist rotted for exactly this reason and leaked a tile to blue. WRITE THE',
      'DRIFT TEST (soft-evidence-drift.test.ts is the model: read the other side and assert both',
      'directions), then put `drift-test: <repo-relative path to it>` inside the same comment.',
      'Better still, do not mirror at all — have the server SERVE the value. If the comment does',
      'not in fact describe a duplicated rule, reword it so it stops saying so. Do NOT add it to',
      `the ledger.\n${unlisted.join('\n')}`,
    ])).toBe('')
  })

  test('the ledger only shrinks: a mirror that gained a guard is removed', () => {
    const live = new Set(unguarded.map((m) => m.key))
    const stale = BUDGET.unguarded_mirrors.filter((k) => !live.has(k))
    expect(say(stale.length > 0, [
      'These are no longer unguarded mirrors — each gained a drift test, was reworded, or the rule',
      'moved to the server. REMOVE each line from "unguarded_mirrors" in budget, so the list',
      `cannot outlive the debt it records. ${EDIT}\n${stale.join('\n')}`,
    ])).toBe('')
  })

  test('every drift-test marker names a file that exists', () => {
    expect(say(SCAN.brokenDriftTestMarkers.length > 0, [
      'A `drift-test:` marker names a path that is not in the repository. The marker is what',
      'discharges the mirror claim, so a marker pointing at nothing is worse than no marker at',
      'all. Correct the path (it is relative to the repository root) or write the test.',
      `\n${SCAN.brokenDriftTestMarkers.join('\n')}`,
    ])).toBe('')
  })
})

// ── STANDARD: no dead weight ─────────────────────────────────────────────────────────────────
describe('no dead weight', () => {
  test('every package in dependencies is imported somewhere', () => {
    expect(say(SCAN.unusedDependencies.length > BUDGET.counts.unused_dependencies, [
      'Package(s) in package.json "dependencies" that nothing imports. Every one is downloaded on',
      'every build, audited on every scan, and read by the next person as something this app uses.',
      'REMOVE it with `npm uninstall`, or import it. The budget is',
      `${BUDGET.counts.unused_dependencies} and may not be raised.`,
      `\n${SCAN.unusedDependencies.join('\n')}`,
    ])).toBe('')
  })
})

// ── STANDARD: no key-echo fallback ───────────────────────────────────────────────────────────
describe('no key-echo fallback', () => {
  test('the `t(…) || \'fallback\'` idiom appears in no non-test source file', () => {
    // ⚠ HARD ZERO, with no budget line: there is no number of these that is acceptable, because
    // every one of them is a fallback that cannot fire. Four shipped to students (TD-259).
    expect(say(SCAN.keyEchoFallbacks.length > 0, [
      '`t(key) || \'fallback\'` found. `t` returns THE KEY when it cannot resolve one, and a key',
      'is a truthy string — so the `||` never fires and the student reads a raw dotted path.',
      'Use `tOr(t, key, fallback)` from `@/lib/i18n` where the key may legitimately be absent,',
      'or a plain `t(key)` where it exists (the i18n ledger guards that it does).',
      `\n${SCAN.keyEchoFallbacks.join('\n')}`,
    ])).toBe('')
  })
})

// ── STANDARD: tests can fail ─────────────────────────────────────────────────────────────────
describe('tests can fail', () => {
  test('no test is skipped, todo, xit or xdescribe', () => {
    expect(say(SCAN.counts.skip_sites > BUDGET.counts.skip_sites, [
      'Skipped test(s) found. A test that cannot fail is not a test, and it sits in a suite people',
      'read as green — both golden masters used to skip themselves on the run straight after a',
      'regenerate, so the least supervised moment in the process passed green. DELETE it, or FIX',
      `what it was waiting for. The budget is ${BUDGET.counts.skip_sites} and may not be raised.`,
      `\n${SCAN.skipSites.join('\n')}`,
    ])).toBe('')
  })
})

// ── THE RATCHET ITSELF ───────────────────────────────────────────────────────────────────────
describe('the ratchet itself', () => {
  test('no budget number is above the baseline', () => {
    const raised = Object.keys(BUDGET.counts)
      .filter((k) => BUDGET.counts[k] > (BASELINE.counts[k] ?? BUDGET.counts[k]))
      .map((k) => `counts.${k}: budget ${BUDGET.counts[k]}, baseline ${BASELINE.counts[k]}`)
      .concat(Object.keys(BUDGET.oversize_files)
        .filter((k) => k in BASELINE.oversize_files
          && BUDGET.oversize_files[k] > BASELINE.oversize_files[k])
        .map((k) => `oversize_files["${k}"]: budget ${BUDGET.oversize_files[k]}, `
          + `baseline ${BASELINE.oversize_files[k]}`))
    expect(say(raised.length > 0, [
      'A limit in "budget" has been raised above the frozen "baseline". A budget may only go DOWN.',
      'If the code genuinely needs more room it needs a smaller change instead — split the file,',
      `give the rule one home, write the reason.\n${raised.join('\n')}`,
    ])).toBe('')
  })

  test('no ledger has gained a member', () => {
    const added: string[] = Object.keys(BUDGET.oversize_files)
      .filter((k) => !(k in BASELINE.oversize_files))
      .map((k) => `oversize_files: "${k}"`)
    const pairs: Array<[string, string[], string[]]> = [
      ['eslint_disable_without_reason',
        BUDGET.eslint_disable_without_reason, BASELINE.eslint_disable_without_reason],
      ['unguarded_mirrors', BUDGET.unguarded_mirrors, BASELINE.unguarded_mirrors],
    ]
    for (const [name, budgetList, baselineList] of pairs) {
      const base = new Set(baselineList)
      added.push(...budgetList.filter((k) => !base.has(k)).map((k) => `${name}: "${k}"`))
    }
    expect(say(added.length > 0, [
      'An exemption list has gained a member. A ledger records what H4 found on 2026-09-19 and can',
      'only ever shrink — adding to it is how a list of known debts turns into a list of',
      'permissions. Fix the code instead: split the file, write the reason, guard the mirror.',
      `\n${added.join('\n')}`,
    ])).toBe('')
  })

  test('no budget counter sits loose above the code', () => {
    const loose = Object.keys(BUDGET.counts)
      .filter((k) => BUDGET.counts[k] > SCAN.counts[k] + (COUNT_SLACK[k] ?? 0))
      .map((k) => `counts.${k}: budget ${BUDGET.counts[k]}, code ${SCAN.counts[k]} — `
        + `LOWER it to ${SCAN.counts[k]}`)
    expect(say(loose.length > 0, [
      `A budget number sits loose above the code. ${EDIT}`,
      `This is the ratchet catching up with your improvement.\n${loose.join('\n')}`,
    ])).toBe('')
  })

  test('the baseline block has not been rewritten', () => {
    const now = sha256(canonical(BASELINE))
    expect(say(now !== BASELINE_SHA256, [
      'The frozen "baseline" block in halatuju-web/code-standards.json has changed. The baseline is',
      'the record of what H4 found on 2026-09-19 and is not maintained — the thing you lower is',
      '"budget". If this change really is intended (a whole file was deleted, say), say so in the',
      `sprint retro and set BASELINE_SHA256 in this test file to ${now} in the SAME commit, so a`,
      'reviewer sees both halves.',
    ])).toBe('')
  })
})

// ── The scanners' own rules, proven on throwaway text ────────────────────────────────────────
//
// The standards above can only exercise the scanners against the REAL tree, where everything
// happens to pass. These prove the rules themselves fire, without anyone having to break the repo.
describe('the key-echo rule, proven both ways', () => {
  // ⚠ A guard that only ever says "clean" is indistinguishable from a guard that matches
  // nothing. These are the exact shapes `src` contained before TD-259, and the exact shapes it
  // contains now and must never be accused of.
  const FIRES = [
    "      setError(t('authGate.claimError') || 'Failed to claim NRIC')",
    "                      {t('authGate.icNotMe') || 'No, not me'}",
    '                      {loading ? \'...\' : (t(\'authGate.icYesMe\') || "Yes, that\'s me")}',
    '      out[k] = t(`scholarship.actionCentre.pathwayName.${v}`) || String(v)',
    "  const label = t('a.b') ||",
    "  {t('authGate.icExistsMessage') || `This NRIC is already registered. Is this you?`}",
  ]
  const QUIET = [
    "  const [query, setQuery] = useState(searchParams.get('q') || '')",
    '  out[k] = tOr(t, `scholarship.actionCentre.pathwayName.${v}`, String(v))',
    "  <p>{t('authGate.icExistsMessage')}</p>",
    '  const n = count(rows) || 0',
    '  return a || b',
    "  const x = format(t('a.b')) // no fallback at all",
    "  title={a.referral_source ? t(`scholarship.apply.org.${a.referral_source}`) : ''}",
    "  const name = first || last || 'anonymous'",
  ]

  test.each(FIRES)('fires on %s', (line) => {
    expect(KEY_ECHO_FALLBACK.test(line)).toBe(true)
  })

  test.each(QUIET)('stays quiet on %s', (line) => {
    expect(KEY_ECHO_FALLBACK.test(line)).toBe(false)
  })

  test('and the live scan agrees the codebase is clean', () => {
    expect(SCAN.keyEchoFallbacks).toEqual([])
  })
})

describe('the reason rule, proven both ways', () => {
  const at = (src: string) => disablesIn('x.ts', src)

  test('a reason after -- on the same line counts', () => {
    expect(at('// eslint-disable-next-line no-console -- the CLI prints here\n')[0].reasoned)
      .toBe(true)
  })

  test('a sentence on the line above counts', () => {
    expect(at('// The API returns this shape before the token exists.\n'
      + '// eslint-disable-next-line react-hooks/exhaustive-deps\n')[0].reasoned).toBe(true)
  })

  test('a block above whose last line is just the close marker still counts', () => {
    // src/app/layout.tsx is exactly this shape: a long JSX comment explaining the exception, then
    // the directive. A single-line look-back would have failed it, which is why the walk goes up
    // through the whole run of comment lines.
    expect(at('{/*\n  The synchronous-script rule is suppressed below as a deliberate exception.\n'
      + '*/}\n{/* eslint-disable-next-line @next/next/no-sync-scripts */}\n')[0].reasoned).toBe(true)
  })

  test('a bare directive with nothing above it does not count', () => {
    expect(at('const x = 1\n// eslint-disable-next-line react-hooks/exhaustive-deps\n')[0].reasoned)
      .toBe(false)
  })

  test('another directive above is not a reason', () => {
    expect(at('// eslint-disable-next-line no-console\n'
      + '// eslint-disable-next-line no-alert\n')[1].reasoned).toBe(false)
  })

  test('the key is the rule and its ordinal, never a line number', () => {
    const found = at('const a = 1\n// eslint-disable-next-line no-console\n'
      + 'const b = 2\n// eslint-disable-next-line no-console\n')
    expect(found.map((d) => d.key)).toEqual(['x.ts::no-console::1', 'x.ts::no-console::2'])
  })
})

describe('the mirror rule, proven both ways', () => {
  const at = (src: string) => mirrorsIn('src/lib/x.ts', src)

  test('a plain mirror claim is caught', () => {
    const found = at('/** Mirrors `STATUS_CHOICES` in models.py. */\nexport const A = 1\n')
    expect(found.length).toBe(1)
    expect(found[0].guarded).toBe(false)
  })

  test('"keep the two in sync" is caught too', () => {
    expect(at('// Keep the two in sync with the backend.\nconst a = 1\n').length).toBe(1)
  })

  test('a drift-test marker discharges the claim', () => {
    const found = at('/**\n * Mirrors `STATUS_CHOICES` in models.py.\n'
      + ' * drift-test: halatuju-web/src/lib/__tests__/soft-evidence-drift.test.ts\n */\n'
      + 'const a = 1\n')
    expect(found[0].guarded).toBe(true)
    expect(found[0].driftTest).toBe('halatuju-web/src/lib/__tests__/soft-evidence-drift.test.ts')
  })

  test('SERVED, NOT MIRRORED is the good pattern and is never flagged', () => {
    expect(at('/** ⚠ THE LIMITS ARE SERVED, NOT MIRRORED (Org Config Sprint E). */\nconst a = 1\n'))
      .toEqual([])
  })

  test('"no server mirror of it" is not a mirror claim', () => {
    expect(at('// presentation, never a permission rule, and there is deliberately no server\n'
      + '// mirror of it.\nconst a = 1\n')).toEqual([])
  })

  test('"never a hard-coded mirror" is not a mirror claim', () => {
    expect(at('/** The login gate reads THIS — never a hard-coded mirror of the platform. */\n'
      + 'const a = 1\n')).toEqual([])
  })

  test('"mirrors no rule the server would refuse" is not a mirror claim', () => {
    expect(at('/** this deliberately mirrors no rule the server would refuse. */\nconst a = 1\n'))
      .toEqual([])
  })

  test('a comment with no mirror word is not a claim', () => {
    expect(at('/** The eight statuses, in flow order. */\nconst a = 1\n')).toEqual([])
  })

  test('the key is the opening words, so the block may move without churn', () => {
    const a = at('/** Mirrors `STATUS_CHOICES` in models.py. */\nconst a = 1\n')
    const b = at('const filler = 1\nconst more = 2\n'
      + '/** Mirrors `STATUS_CHOICES` in models.py. */\nconst a = 1\n')
    expect(a[0].key).toBe(b[0].key)
  })
})

describe('the file scanner, proven on throwaway text', () => {
  test('a CRLF file counts the same lines as an LF one', () => {
    expect(countLines('a\r\nb\r\nc\r\n'.replace(/\r\n?/g, '\n'))).toBe(3)
    expect(countLines('a\nb\nc\n')).toBe(3)
    expect(countLines('a\nb\nc')).toBe(3)
  })

  test('a test path is recognised the way code_health.py recognises it', () => {
    expect(isTestPath('src/lib/__tests__/x.test.ts')).toBe(true)
    expect(isTestPath('src/components/X.test.tsx')).toBe(true)
    expect(isTestPath('src/app/admin/scholarship/[id]/view.tsx')).toBe(false)
    expect(isTestPath('src/app/sponsor/(portal)/students/page.tsx')).toBe(false)
  })

  test('the canonical form ignores key order and whitespace', () => {
    expect(sha256(canonical({ b: 1, a: { d: 2, c: 3 } })))
      .toBe(sha256(canonical(JSON.parse('{ "a" : { "c" : 3 , "d" : 2 } , "b" : 1 }'))))
    expect(sha256(canonical({ b: 1 }))).not.toBe(sha256(canonical({ b: 2 })))
  })
})
