/**
 * I18N HYGIENE FOR EVERY NAMESPACE — one parameterised suite.
 *
 * ⚠ **THIS FILE REPLACES ELEVEN NEAR-IDENTICAL GUARDS** (`admin-administration-i18n`,
 * `admin-billing-i18n`, `admin-contracts-i18n`, `admin-programme-overview-i18n`,
 * `admin-requests-i18n`, `admin-scholarship-i18n`, `admin-sources-i18n`, `admin-spending-i18n`,
 * `admin-sponsors-i18n`, `sponsor-i18n`, `sponsor-spending-i18n`). Each was a copy of the same
 * ~60 lines with one namespace string changed, so eleven namespaces were watched and the other
 * twenty-four were not — including `authGate` and the flat `admin.*` surface, both of which turn
 * out to be rendering raw dotted strings today (see `KNOWN_MISSING`). Every special case the
 * eleven encoded is carried over below, named, with the reason it exists.
 *
 * Two claims, for each of the **35 top-level namespaces in `en.json`**:
 *
 *  1. **NO MISSING KEYS** — every `t('<ns>.…')` literal in production source resolves to a STRING
 *     in `en.json`.
 *  2. **PARITY** — en / ms / ta hold the identical key set under the namespace.
 *
 * ⚠ **PARITY IS NOT EXISTENCE, AND THAT IS WHY (1) EXISTS.** en/ms/ta parity proves the three
 * locales agree; it says nothing about whether a key the code CALLS was ever added. The sponsor
 * redesign referenced ~47 `sponsorPortal.*` keys that existed in no locale and rendered raw dotted
 * strings for FOUR SPRINTS, undetected, because parity passed — all three were equally missing —
 * and nobody was looking at the surface yet.
 *
 * ⚠ **A STATIC SCAN CANNOT SEE A KEY BUILT AT RUNTIME**, so each dynamic family is enumerated in
 * `DYNAMIC` against the values the code can actually produce. That is not a wish list: it is the
 * server's own choice lists. Add a status or a category on the Python side and the missing
 * translation surfaces here rather than on an org admin's screen.
 *
 * `no-icu-messageformat.test.ts` stays separate: it is about the SHAPE of a message value, not
 * about which keys exist.
 */
import * as fs from 'fs'
import * as path from 'path'

import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { APPLICATION_STATUSES, statusLabelKey } from '@/lib/applicationStatus'
import { SECTION_KEYS } from '@/lib/overviewLayout'
import { MERCHANT_SORT_LABEL, STUDENT_SORT_LABEL } from '@/lib/spendingTable'

const SRC_DIR = path.join(__dirname, '..', '..')     // .../src
const LOCALES = [['en', en], ['ms', ms], ['ta', ta]] as const

// ── Reading the tree ─────────────────────────────────────────────────────────────────────────
function collectSource(dir: string, acc: string[], keepTests: boolean): string[] {
  fs.readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') return
      collectSource(full, acc, keepTests)
    } else if (/\.tsx?$/.test(entry.name)) {
      if (!keepTests && /\.test\.tsx?$/.test(entry.name)) return
      acc.push(full)
    }
  })
  return acc
}

/**
 * Comment text is PROSE, not a usage.
 *
 * Carried over from `admin-sponsors-i18n`, which needed it because `sponsorDetail.ts` documents
 * its error fallback by naming a key that deliberately does NOT exist — reading that as a
 * reference would make the guard demand the very key the comment describes. Applied to every
 * namespace here, which also retires a second special case: `ActionCentre`'s docblock, the theme
 * guard's own explanation and several "see lib/x.ts" notes all name dotted paths in prose.
 * Replaced by spaces, so line numbers in a failure message still point at the real line.
 */
function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, lead: string) => lead + ' '.repeat(m.length - lead.length))
}

function captureGroup1(re: RegExp, s: string): string[] {
  const out: string[] = []
  s.replace(re, (full: string, g1: string): string => { out.push(g1); return full })
  return out
}

function leafPaths(obj: Record<string, unknown>, prefix: string, out: string[]): string[] {
  Object.keys(obj).forEach((k) => {
    const p = prefix ? `${prefix}.${k}` : k
    const v = obj[k]
    if (v !== null && typeof v === 'object') leafPaths(v as Record<string, unknown>, p, out)
    else out.push(p)
  })
  return out
}

function resolve(obj: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((cur, part) => {
    if (cur && typeof cur === 'object' && part in (cur as Record<string, unknown>)) {
      return (cur as Record<string, unknown>)[part]
    }
    return undefined
  }, obj)
}

const leavesUnder = (loc: unknown, ns: string) =>
  leafPaths((resolve(loc, ns) ?? {}) as Record<string, unknown>, '', [])

// ── The reference scan ───────────────────────────────────────────────────────────────────────
const NAMESPACES = Object.keys(en as Record<string, unknown>).sort()
const NS_ALTERNATION = NAMESPACES.join('|')

/** A literal that is a FILE PATH, not a key — `theme.test.ts`, `subjects.ts`, `scholarship.ts`.
 *  Several files name their own guard or their own module in a string. */
const LOOKS_LIKE_A_FILE = /\.(ts|tsx|js|jsx|json|py|md|css|sql)$/

interface Reference { key: string; where: string }

/**
 * Every `'<namespace>.<dotted path>'` literal in production source, with the file and line it
 * came from — a missing key is only actionable if you can be told where it is asked for.
 *
 * Co-located `*.test.tsx` files are EXCLUDED, carried over from `admin-sponsors-i18n`: a test may
 * legitimately name a key to assert its ABSENCE (`page.test.tsx` pins the dropped Organisation
 * column, `CommandPalette.test.tsx` pins a removed nav row, `icEditor.test.ts` proves an unmapped
 * code falls back). Reading those as references would make this guard demand the very keys those
 * tests exist to keep out.
 */
function scanReferences(): Reference[] {
  const out: Reference[] = []
  for (const file of collectSource(SRC_DIR, [], false)) {
    const where = path.relative(SRC_DIR, file).split(path.sep).join('/')
    stripComments(fs.readFileSync(file, 'utf8')).split('\n').forEach((line, i) => {
      const re = new RegExp(`['"\`]((?:${NS_ALTERNATION})\\.[\\w.]+?)(?=['"\`])`, 'g')
      for (const key of captureGroup1(re, line)) {
        if (!key.endsWith('.') && !LOOKS_LIKE_A_FILE.test(key)) {
          out.push({ key, where: `${where}:${i + 1}` })
        }
      }
    })
  }
  return out
}

const REFERENCES = scanReferences()

/**
 * A literal that resolves to an OBJECT is a NAMESPACE PROP, not a key reference.
 *
 * `TemplateEditor` takes `prefix="admin.sources.emails"` and builds `${prefix}.subject` itself;
 * the Programme Overview page writes `const K = 'admin.programmeOverview'`. Both were hand-listed
 * exclusions in the old guards (`NAMESPACE_PROPS`); resolving the literal generalises them, and a
 * prop pointing at a namespace that does NOT exist still fails, which the hand-list could not do.
 */
const isNamespaceProp = (key: string) => {
  const v = resolve(en, key)
  return v !== null && v !== undefined && typeof v === 'object'
}

/**
 * ⚠ **THE MISSING-KEY LEDGER. IT MAY ONLY EVER SHRINK — AND IT IS NOW EMPTY.**
 *
 * Extending this guard from eleven namespaces to all thirty-five found eight keys that production
 * source asked for and no locale had (TD-259). All eight are gone, on 2026-09-19:
 *
 *   * the five `authGate` keys were the IC step of the sign-in gate, which TD-254 rebuilt. Four
 *     of them reached the screen as raw dotted paths, because they were written
 *     `t(key) || 'English fallback'` and `t` returns THE KEY when it cannot resolve one — a
 *     truthy string, so `||` never fires. The copy is written for the NEW flow, in three
 *     languages, and deliberately without the holder's name that the old English fallback
 *     interpolated. The idiom itself is now refused by `lib/__tests__/codeStandards.test.ts`;
 *     `tOr` in `lib/i18n.tsx` is the replacement;
 *   * `admin.householdIncome` / `admin.householdSize` now read `admin.familyIncome` (which
 *     already existed) and `admin.familySize` (added in all three locales);
 *   * the Story save-error map points at `…cardA.parentsHeading`, a leaf that exists, instead of
 *     a leaf the roster redesign removed.
 *
 * Same manners as `NOT_YET_EXERCISED` in the api suite: a key listed here that STARTS resolving
 * fails with "remove me", so the ledger cannot quietly outlive the defect it records. Keep it
 * empty. A new entry is a decision to ship a raw dotted path to a student.
 */
const KNOWN_MISSING: Record<string, string> = {}

// ── The namespace table ──────────────────────────────────────────────────────────────────────
interface NamespaceSpec {
  /** The top-level namespace. */
  ns: string
  /** Floor on the parity leaf count — a namespace emptied by a bad merge must not pass. */
  minLeaves: number
}

/**
 * Every top-level namespace of `en.json`, with a floor under its size. The floors are the counts
 * H6 measured, rounded down hard: they exist to stop a namespace vanishing, not to freeze it.
 */
const SPECS: NamespaceSpec[] = [
  { ns: 'common', minLeaves: 20 },
  { ns: 'header', minLeaves: 5 },
  { ns: 'theme', minLeaves: 3 },
  { ns: 'getStarted', minLeaves: 5 },
  { ns: 'sponsorAuth', minLeaves: 40 },
  { ns: 'sponsorPortal', minLeaves: 150 },
  { ns: 'sponsorPool', minLeaves: 20 },
  { ns: 'sponsorLanding', minLeaves: 30 },
  { ns: 'footer', minLeaves: 5 },
  { ns: 'landing', minLeaves: 10 },
  { ns: 'onboarding', minLeaves: 60 },
  { ns: 'verifyEmail', minLeaves: 5 },
  { ns: 'dashboard', minLeaves: 30 },
  { ns: 'report', minLeaves: 5 },
  { ns: 'search', minLeaves: 15 },
  { ns: 'login', minLeaves: 10 },
  { ns: 'subjects', minLeaves: 10 },
  { ns: 'settings', minLeaves: 8 },
  { ns: 'courseDetail', minLeaves: 15 },
  { ns: 'saved', minLeaves: 5 },
  { ns: 'scholarship', minLeaves: 900 },
  { ns: 'authGate', minLeaves: 20 },
  { ns: 'profile', minLeaves: 60 },
  { ns: 'quiz', minLeaves: 10 },
  { ns: 'stpmQuiz', minLeaves: 4 },
  { ns: 'outcomes', minLeaves: 12 },
  { ns: 'pathways', minLeaves: 15 },
  { ns: 'pathwayDetail', minLeaves: 15 },
  { ns: 'about', minLeaves: 10 },
  { ns: 'errors', minLeaves: 10 },
  { ns: 'stpm', minLeaves: 20 },
  { ns: 'courses', minLeaves: 8 },
  { ns: 'contactForm', minLeaves: 10 },
  { ns: 'apiErrors', minLeaves: 25 },
  { ns: 'admin', minLeaves: 1800 },
]

describe('the scan found the tree and the catalogue (the floor)', () => {
  it('covers every top-level namespace in en.json, and invents none', () => {
    // ⚠ A namespace added to `en.json` and not to `SPECS` would be silently unguarded, which is
    // the exact hole this file closes. The two lists must be the same list.
    expect(SPECS.map((s) => s.ns).sort()).toEqual(NAMESPACES)
    expect(NAMESPACES.length).toBeGreaterThan(30)
  })

  it('actually read some source', () => {
    // A path change that matched nothing would make every "no missing keys" test below pass while
    // watching nothing at all.
    expect(collectSource(SRC_DIR, [], false).length).toBeGreaterThan(200)
    expect(REFERENCES.length).toBeGreaterThan(2_000)
  })

  it('finds the keys the busiest surfaces are built from', () => {
    // Named anchors, one per scan rule, so a regex change that quietly stopped matching a SHAPE
    // (a plain literal, a `${K}` template) is caught rather than reported as "nothing is missing".
    const keys = new Set(REFERENCES.map((r) => r.key))
    expect(keys.has('admin.spending.title')).toBe(true)
    expect(keys.has('admin.scholarship.decision.title')).toBe(true)
    expect(keys.has('sponsorPortal.myStudents.title')).toBe(true)
  })
})

describe.each(SPECS)('$ns', ({ ns, minLeaves }) => {
  const referenced = REFERENCES.filter(
    (r) => r.key === ns || r.key.startsWith(`${ns}.`))

  it('every referenced key resolves to a string in en.json', () => {
    const missing = referenced
      .filter((r) => typeof resolve(en, r.key) !== 'string')
      .filter((r) => !isNamespaceProp(r.key))
      .filter((r) => !(r.key in KNOWN_MISSING))
      .map((r) => `${r.key}  (${r.where})`)
    expect(Array.from(new Set(missing)).sort()).toEqual([])
  })

  it('en / ms / ta hold the identical key set', () => {
    const e = leavesUnder(en, ns)
    expect(e.length).toBeGreaterThanOrEqual(minLeaves)
    expect(leavesUnder(ms, ns).sort()).toEqual(e.slice().sort())
    expect(leavesUnder(ta, ns).sort()).toEqual(e.slice().sort())
  })
})

// ── The dynamic families: keys a static scan is blind to ─────────────────────────────────────
/**
 * Keys BUILT at runtime, enumerated against the values the code can actually produce. Carried
 * over from `admin-spending-i18n`, `admin-programme-overview-i18n` and `sponsor-spending-i18n`,
 * which is where each list's reasoning is preserved beside it.
 */
const OV = 'admin.programmeOverview'
const SPEND = 'sponsorPortal.myStudents.detail.spend'

/** The ELEVEN slices `by_category` always sends: the ten `SPEND_CATEGORY_CHOICES`, plus the
 *  `none` a blank category travels as. `unsorted` and `none` are DIFFERENT states. */
const CATEGORY_CODES = ['food', 'groceries', 'transport', 'study', 'phone', 'hostel',
                        'health', 'clothing', 'transfer', 'unsorted', 'none']

const DYNAMIC: Array<[string, string[]]> = [
  // ── admin.spending: the sorter's rungs, the four headline figures, the three refusal codes
  //    `spend_report.set_owner_category` can return. Add one on the Python side → it surfaces here.
  ['admin.spending figures, verdict sources and refusals', [
    ...['spent', 'sorted', 'unsorted', 'toCheck'].map((k) => `admin.spending.stat.${k}`),
    ...['none', 'duitnow', 'rule', 'inferred', 'ai', 'owner'].map((k) => `admin.spending.by.${k}`),
    ...['unknown_merchant', 'unknown_category', 'merchant_required']
      .map((k) => `admin.spending.error.${k}`),
  ]],
  // ⚠ An ACCESSIBLE NAME is invisible twice over: never drawn, so no screenshot shows it missing,
  // and parity cannot see it either — an invented key is absent from all three locales
  // identically. Five keys of exactly this shape shipped unresolved on 2026-09-08.
  ['admin.spending tabs and the tab bar’s accessible name', [
    'admin.spending.tabs.aria', 'admin.spending.tab.shops', 'admin.spending.tab.students',
    'admin.spending.tab.unsorted', 'admin.spending.unplaced.title',
    'admin.spending.unplaced.help', 'admin.spending.unplaced.empty',
    // The registry holds the nav row by `labelKey`, which no page-level scan would ever reach.
    'admin.spending.nav',
  ]],
  // ⚠ These arrive at a column header through `label={t(MERCHANT_SORT_LABEL[col])}` — a lookup in
  // a map in another file. Asserting the MAPS is the version that survives somebody building a
  // key by hand there.
  ['admin.spending sortable column names',
    [...Object.values(MERCHANT_SORT_LABEL), ...Object.values(STUDENT_SORT_LABEL)]],
  // ── admin.programmeOverview: the strip, the donut, the bands, the months, the customisable
  //    sections (from the SAME list the server validates against) and the four round states.
  ['admin.programmeOverview dynamic families', [
    ...['unassigned', 'withReviewer', 'dueSoon', 'overdue', 'awaitingQc']
      .map((k) => `${OV}.attention.${k}`),
    ...CATEGORY_CODES.map((c) => `${OV}.category.${c}`),
    ...['open', 'due_soon', 'overdue'].map((b) => `${OV}.band.${b}`),
    ...[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((m) => `${OV}.months.${m}`),
    ...SECTION_KEYS.map((k) => `${OV}.sections.${k}`),
    ...['draft', 'open', 'closed', 'finished'].map((s) => `${OV}.intakes.state.${s}`),
  ]],
  // ⚠ The customise editor builds every one of these off `${K}`, so the static scan above is
  //   blind to all of them — and `moveUp` / `moveDown` are ACCESSIBLE NAMES, invisible twice over
  //   (never drawn, and missing from all three locales identically, so parity cannot see it).
  ['admin.programmeOverview customise, arrows included',
    ['button', 'title', 'hint', 'orderHint', 'moveUp', 'moveDown', 'hidden', 'visible',
     'save', 'discard', 'saved', 'error', 'refused'].map((k) => `${OV}.customise.${k}`)],
  ['admin.programmeOverview chart accessible names',
    ['applicationsLabel', 'awardsLabel', 'moneyLabel', 'averageLabel', 'transactionsLabel',
     'categoryLabel', 'yRinggit', 'yTransactions', 'yApplications', 'yAwards']
      .map((k) => `${OV}.chart.${k}`)],
  // ── The Administration hub cards and roles, and the sponsor tabs: keys OUTSIDE the namespace
  //    whose page depends on them, which is why each old guard asserted them by hand.
  ['the Administration panel’s roles and Sources card',
    ['admin.role.org_admin', 'admin.role.qc',
     'admin.administration.sources', 'admin.administration.sourcesSub']],
  ['the three sponsor tab labels',
    ['admin.sponsors.tabSponsors', 'admin.sponsors.tabEmails', 'admin.sponsors.tabTerms']],
  // ── sponsorPortal…spend: the ten codes the server can send, plus the card's own folded bucket.
  ['the sponsor spending card', [
    ...['title', 'asAt', 'promised', 'released', 'spent', 'left', 'barLabel', 'chartLabel',
        'other', 'none', 'noteTitle', 'note'].map((k) => `${SPEND}.${k}`),
    ...CATEGORY_CODES.filter((c) => c !== 'none').map((c) => `${SPEND}.cat.${c}`),
  ]],
]

describe.each(DYNAMIC)('%s resolves in all three locales', (_label, keys) => {
  it('has no gaps', () => {
    expect(keys.length).toBeGreaterThan(0)
    const missing: string[] = []
    for (const key of keys) {
      for (const [name, loc] of LOCALES) {
        if (typeof resolve(loc, key) !== 'string') missing.push(`${name}: ${key}`)
      }
    }
    expect(missing).toEqual([])
  })
})

describe('the funnel names every status it can draw', () => {
  it('all THIRTEEN, in all three locales', () => {
    // ⚠ Through `statusLabelKey()`, in a namespace this check does not own — which is exactly why
    // it is asserted: the funnel is zero-filled to all thirteen, so a status with no label renders
    // a raw dotted string in a tile that reads "0".
    expect(APPLICATION_STATUSES.length).toBe(13)
    const missing: string[] = []
    for (const status of APPLICATION_STATUSES) {
      for (const [name, loc] of LOCALES) {
        if (typeof resolve(loc, statusLabelKey(status)) !== 'string') {
          missing.push(`${name}: ${statusLabelKey(status)}`)
        }
      }
    }
    expect(missing).toEqual([])
  })
})

// ── The copy rules the old guards asserted on the TEXT itself ────────────────────────────────
describe('the wording promises the eleven files kept', () => {
  it('the overview charts say TRANSACTIONS, and no locale still says purchases', () => {
    // ⚠ Owner, 2026-09-15: a Vircle row is a card transaction; "purchase" implied a basket we
    // never see. The old keys are GONE, not orphaned — an orphan is a key somebody reuses later.
    for (const [, loc] of LOCALES) {
      expect(typeof resolve(loc, `${OV}.series.transactions`)).toBe('string')
      for (const gone of ['series.purchases', 'series.purchasesNote', 'chart.purchasesLabel',
                          'series.month', 'intake']) {
        expect(resolve(loc, `${OV}.${gone}`)).toBeUndefined()
      }
    }
    // "active": only a student who spent that week is counted (owner, 2026-09-18).
    expect(resolve(en, `${OV}.series.transactions`))
      .toBe('Transactions per active student, per week')
  })

  it('the overview REUSES the existing nav label rather than minting a second one', () => {
    // ⚠ `admin.nav.programmeOverview` already existed in all three locales — an orphaned
    // "Overview" from an earlier arc. Two menu rows saying the same word is how they end up
    // disagreeing about their name.
    for (const [, loc] of LOCALES) {
      expect(typeof resolve(loc, 'admin.nav.programmeOverview')).toBe('string')
    }
    expect(resolve(en, 'admin.nav.programmeOverview')).toBe('Overview')
  })

  it('the sponsor spending note states no threshold, in any language', () => {
    // ⚠ A number in prose rots the day it is tuned, so it says "small amounts" — never RM8 / RM20
    // / three visits. And it never apologises.
    for (const [, loc] of LOCALES) {
      const note = String(resolve(loc, `${SPEND}.note`) ?? '')
      expect(note).not.toMatch(/\d/)
      expect(note.toUpperCase()).not.toContain('RM')
      expect(note.length).toBeGreaterThan(80)          // a real explanation, not a stub
    }
  })

  it('the sponsor spending note names no shop, in any language', () => {
    // Real merchants from the corpus. The whole privacy ruling is that a shop is never named to
    // a sponsor.
    const SHOPS = ['SPEEDMART', 'KOPERASI', 'KTMB', 'ENGINEER', 'ECONSAVE', 'MYDIN']
    for (const [, loc] of LOCALES) {
      const note = String(resolve(loc, `${SPEND}.note`) ?? '').toUpperCase()
      for (const shop of SHOPS) expect(note).not.toContain(shop)
    }
  })

  it('no locale still says the spending feature is coming soon', () => {
    // ⚠ Copy asserting a capability's ABSENCE goes stale the day it ships, and this repo has been
    // caught by that three times.
    for (const [, loc] of LOCALES) {
      expect(resolve(loc, 'sponsorPortal.myStudents.detail.spendingSoon')).toBeUndefined()
      expect(resolve(loc, 'sponsorPortal.myStudents.detail.soon')).toBeUndefined()
      // The new block is a SIBLING called `spend`; turning `spending` into an object would break
      // the existing heading with no error anywhere.
      expect(typeof resolve(loc, 'sponsorPortal.myStudents.detail.spending')).toBe('string')
    }
  })
})

// ── The orphan sweep: admin.scholarship only ─────────────────────────────────────────────────
/**
 * NO ORPHANED KEYS under `admin.scholarship` (TD-120) — every leaf must be referenced in source,
 * by its full dotted path or under a dynamically-built prefix.
 *
 * ⚠ KEPT EXACTLY AS IT WAS, on its OWN blob: comments included, test files included, no filename
 * rule. Every one of those exclusions would REMOVE usages, and a removed usage turns a live key
 * into a reported orphan — this sweep is the one place where reading too much is the safe error.
 * It is dynamic-aware on purpose: a naive version is what made the TD-120 bulk-delete dangerous.
 *
 * It stays scoped to this one namespace. Running it everywhere would flag the hundreds of keys
 * that are genuinely reached only through a helper's lookup table, and a guard that reports a
 * hundred false orphans is a guard nobody reads.
 */
describe('admin.scholarship has no orphaned keys', () => {
  const blob = collectSource(SRC_DIR, [], true)
    .map((f) => fs.readFileSync(f, 'utf8')).join('\n')

  // Dynamically-built prefixes: `admin.scholarship.<X>.` immediately before a closing quote or `${`.
  const dynPrefixes: string[] = []
  captureGroup1(/admin\.scholarship\.((?:\w+\.)+)(?=['"`]|\$\{)/g, blob).forEach((p) => {
    if (dynPrefixes.indexOf(p) < 0) dynPrefixes.push(p)
  })
  // Also a prefix ending just before `${` even when it ends in a NON-dot word char (e.g.
  // `recordVerdict.noAmountReason_${disqualifier}`), which the first regex cannot match.
  captureGroup1(/admin\.scholarship\.([\w.]+?)(?=\$\{)/g, blob).forEach((p) => {
    if (dynPrefixes.indexOf(p) < 0) dynPrefixes.push(p)
  })
  const topLevelDynamic = /admin\.scholarship\.(?=['"`]|\$\{)/.test(blob)

  const staticPaths: string[] = []
  captureGroup1(/admin\.scholarship\.([\w.]+?)(?=['"`])/g, blob).forEach((p) => {
    if (!p.endsWith('.') && staticPaths.indexOf(p) < 0) staticPaths.push(p)
  })

  const isDynamic = (relKey: string): boolean => topLevelDynamic
    || dynPrefixes.some((p) => relKey === p.slice(0, -1) || relKey.indexOf(p) === 0)

  it('every leaf is referenced somewhere (dynamic-aware)', () => {
    const leaves = leavesUnder(en, 'admin.scholarship')
    expect(leaves.length).toBeGreaterThan(400)
    expect(leaves.filter((k) => staticPaths.indexOf(k) < 0 && !isDynamic(k))).toEqual([])
  })
})

describe('the missing-key ledger only shrinks', () => {
  // ⚠ Not `it.each`: jest refuses an empty table, and the ledger being EMPTY is the good state
  // (TD-259 cleared it on 2026-09-19). One test over the whole ledger says the same thing and
  // survives the day it holds nothing.
  it('every listed key is still missing, or REMOVE ME', () => {
    // If this fails the key now resolves — delete its line from KNOWN_MISSING. A ledger that
    // outlives the defect it records is how an exemption becomes permanent.
    const resolved = Object.keys(KNOWN_MISSING).sort()
      .filter((key) => typeof resolve(en, key) === 'string')
    expect(resolved).toEqual([])
  })

  it('every listed key is still referenced somewhere, or REMOVE ME', () => {
    // The other direction: a call site deleted is a ledger line to delete too.
    const referenced = new Set(REFERENCES.map((r) => r.key))
    const stale = Object.keys(KNOWN_MISSING).filter((k) => !referenced.has(k))
    expect(stale).toEqual([])
  })

  it('and today it is empty — every key production asks for now resolves', () => {
    // The floor under the two rules above: they both pass trivially on an empty ledger, so the
    // emptiness is asserted rather than assumed. If a future change has to add an entry, this
    // line is the one that makes that a decision somebody took, not a drift.
    expect(Object.keys(KNOWN_MISSING)).toEqual([])
  })
})
