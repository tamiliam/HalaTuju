/**
 * TD-360 Sprint 1 (2026-10-21): NO ROUTE OUTSIDE THE ADMIN CONSOLE REACHES AN `admin.*` KEY.
 *
 * ⚠ **WHY THIS GUARD EXISTS.** The admin console's words (`admin.*`, more than half of every
 * message file) are no longer in the English catalogue every route downloads: they are a slice
 * that only `app/admin/layout.tsx` (and the sandbox layout) loads, through `lib/messagesAdmin.ts`.
 * That is safe for exactly as long as no student, public or sponsor screen ever asks for an
 * `admin.*` key — and the day a shared component starts to, that screen renders a RAW DOTTED KEY
 * in production while every jest render test passes (jest hands every slice the whole file).
 *
 * So this walks the IMPORT GRAPH (static `import` / `export … from`, `import()` and `require()`,
 * `@/` and relative) from every route entry outside `app/admin` — `page`, `layout`, `error`,
 * `not-found`, `loading`, `template`, `global-error`, `default` — and fails, naming the file AND the
 * import chain, if any reachable production file holds an `admin.`-prefixed string literal or
 * template prefix (`'admin.x'`, `` `admin.${h}` ``), or reaches `lib/messagesAdmin.ts` itself.
 *
 * ⚠ CONSERVATIVE ON PURPOSE: a key in a reachable file fails even if that branch never renders on
 * the route. Moving the key, or the import, is the fix — never an exemption list.
 *
 * The second claim is the converse: every file holding an `admin.*` key IS reachable from an
 * admin (or sandbox) entry — so an `admin.*` key cannot sit in a file the console does not load.
 *
 * Floors against a blind walk (TD-276): enough non-admin entries, enough reachable files, enough
 * `admin.*`-holding files seen, and the one bare-namespace template (`admin.${h}` in
 * `components/admin/InvitationsTable.tsx`) must be among them.
 */
import * as fs from 'fs'
import * as path from 'path'

const SRC = path.join(__dirname, '..', '..')              // .../src
const APP = path.join(SRC, 'app')
const ADMIN_LOADER = path.join(SRC, 'lib', 'messagesAdmin.ts')

/** Floors, set from the tree on 2026-10-21 (56 non-admin entries, 41 admin, ~150 admin-key files). */
const NON_ADMIN_ENTRY_FLOOR = 45
const ADMIN_ENTRY_FLOOR = 30
const REACHABLE_FLOOR = 150
const ADMIN_KEY_FILE_FLOOR = 100

const ENTRY = /^(page|layout|error|not-found|loading|template|global-error|default)\.(tsx|ts|jsx|js)$/
/** The sandbox's route files only exist in a sandbox build (`*.sandbox.tsx`, see next.config.js). */
const SANDBOX_ENTRY = /^(page|layout)\.sandbox\.tsx$/

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, lead: string) => lead + ' '.repeat(m.length - lead.length))
}

function walk(dir: string, acc: string[]): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      // `src/test/` holds jest helpers (fixtures, render wrappers) — shipped to nobody.
      if (entry.name === '__tests__' || entry.name === 'node_modules'
        || (entry.name === 'test' && dir === SRC)) continue
      walk(full, acc)
    } else if (/\.(tsx?|jsx?)$/.test(entry.name) && !/\.test\.(tsx?|jsx?)$/.test(entry.name)) {
      acc.push(full)
    }
  }
  return acc
}

const rel = (f: string) => path.relative(SRC, f).split(path.sep).join('/')

const FILES = walk(SRC, [])
const TEXT = new Map(FILES.map((f) => [f, stripComments(fs.readFileSync(f, 'utf8'))]))

/** Every module specifier a file names: static, re-export, side-effect, `import()`, `require()`. */
const SPECIFIER = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+|\brequire\s*\(\s*)['"]([^'"\n]+)['"]/g

function resolveSpecifier(from: string, spec: string): string | null {
  const bare = spec.split('?')[0]
  let base: string
  if (bare.startsWith('@/')) base = path.join(SRC, bare.slice(2))
  else if (bare.startsWith('.')) base = path.join(path.dirname(from), bare)
  else return null                                       // a package — not ours to walk
  for (const cand of [base, `${base}.ts`, `${base}.tsx`, `${base}.js`, `${base}.jsx`,
    path.join(base, 'index.ts'), path.join(base, 'index.tsx')]) {
    if (TEXT.has(cand)) return cand
  }
  return null                                            // JSON, CSS, an asset — no code to walk
}

const EDGES = new Map(FILES.map((f) => {
  const out = new Set<string>()
  for (const m of (TEXT.get(f) as string).matchAll(SPECIFIER)) {
    const to = resolveSpecifier(f, m[1])
    if (to) out.add(to)
  }
  return [f, [...out]]
}))

/** Breadth-first from `entries`; each reached file remembers who reached it, for the chain. */
function reach(entries: string[]): Map<string, string | null> {
  const parent = new Map<string, string | null>(entries.map((e) => [e, null]))
  const queue = [...entries]
  while (queue.length) {
    const f = queue.shift() as string
    for (const to of EDGES.get(f) ?? []) {
      if (!parent.has(to)) { parent.set(to, f); queue.push(to) }
    }
  }
  return parent
}

function chain(parent: Map<string, string | null>, f: string): string {
  const out: string[] = []
  for (let cur: string | null | undefined = f; cur; cur = parent.get(cur)) out.unshift(rel(cur))
  return out.join(' → ')
}

/** An `admin.` key literal or template prefix: `'admin.x'`, `"admin.x"`, `` `admin.x` ``, `` `admin.${h}` ``. */
const ADMIN_KEY = /['"`]admin\.(?:\$\{|[A-Za-z_][\w]*)/g
const LOOKS_LIKE_A_FILE = /['"`]admin\.(ts|tsx|js|jsx|json|py|md|css|html)['"`]/

function adminKeysIn(f: string): string[] {
  const text = TEXT.get(f) as string
  const out: string[] = []
  text.split('\n').forEach((line, i) => {
    if (LOOKS_LIKE_A_FILE.test(line)) return
    for (const m of line.matchAll(ADMIN_KEY)) out.push(`${rel(f)}:${i + 1}  ${m[0]}…`)
  })
  return out
}

const isAdminSide = (f: string) => f.startsWith(path.join(APP, 'admin') + path.sep)
const isSandboxSide = (f: string) => f.startsWith(path.join(APP, 'sandbox') + path.sep)

const ENTRIES = FILES.filter((f) => f.startsWith(APP + path.sep) && ENTRY.test(path.basename(f)))
const NON_ADMIN_ENTRIES = ENTRIES.filter((f) => !isAdminSide(f) && !isSandboxSide(f))
const ADMIN_ENTRIES = ENTRIES.filter(isAdminSide)
const SANDBOX_ENTRIES = FILES.filter((f) => isSandboxSide(f) && SANDBOX_ENTRY.test(path.basename(f)))

const FROM_NON_ADMIN = reach(NON_ADMIN_ENTRIES)
const FROM_ADMIN = reach([...ADMIN_ENTRIES, ...SANDBOX_ENTRIES])
const ADMIN_KEY_FILES = FILES.filter((f) => adminKeysIn(f).length > 0)

describe('the walk really read the tree (floors, TD-276)', () => {
  test('enough entries on both sides, enough reachable files, enough admin.* files', () => {
    expect(NON_ADMIN_ENTRIES.length).toBeGreaterThanOrEqual(NON_ADMIN_ENTRY_FLOOR)
    expect(ADMIN_ENTRIES.length).toBeGreaterThanOrEqual(ADMIN_ENTRY_FLOOR)
    expect(SANDBOX_ENTRIES.map(rel)).toContain('app/sandbox/layout.sandbox.tsx')
    expect(FROM_NON_ADMIN.size).toBeGreaterThanOrEqual(REACHABLE_FLOOR)
    expect(ADMIN_KEY_FILES.length).toBeGreaterThanOrEqual(ADMIN_KEY_FILE_FLOOR)
  })

  test('the walk follows @/ and relative imports, import() and the provider tree', () => {
    // Root layout → providers → the i18n provider and the sign-in gate every page mounts.
    for (const f of ['app/providers.tsx', 'lib/i18n.tsx', 'lib/messages.ts', 'components/AuthGateModal.tsx']) {
      expect([...FROM_NON_ADMIN.keys()].map(rel)).toContain(f)
    }
    // The admin layout reaches the admin slice's loader.
    expect(FROM_ADMIN.has(ADMIN_LOADER)).toBe(true)
  })

  test('a whole-namespace TEMPLATE key is seen, not just literals', () => {
    expect(adminKeysIn(path.join(SRC, 'components', 'admin', 'InvitationsTable.tsx')).join('\n'))
      .toContain('`admin.${')
  })

  test('the pattern catches each shape and ignores prose and file names', () => {
    const shapes = (s: string) => [...s.matchAll(ADMIN_KEY)].map((m) => m[0])
    // The match is the quote, the namespace and the first segment — enough to name the key.
    expect(shapes("t('admin.save')")).toEqual(["'admin.save"])
    expect(shapes('t("admin.nav.home")')).toEqual(['"admin.nav'])
    expect(shapes('t(`admin.${h}`)')).toEqual(['`admin.${'])
    expect(shapes("router.push('/admin/login')")).toEqual([])
    expect(shapes("const KEY = 'administration.x'")).toEqual([])
  })
})

describe('no route outside /admin reaches the admin slice', () => {
  test('⚠ no file reachable from a student, public or sponsor route holds an admin.* key', () => {
    const offenders = [...FROM_NON_ADMIN.keys()].flatMap((f) => {
      const keys = adminKeysIn(f)
      return keys.length ? [`${keys[0]}${keys.length > 1 ? ` (+${keys.length - 1} more)` : ''}\n    via ${chain(FROM_NON_ADMIN, f)}`] : []
    })
    // ⚠ If this fails: that screen will show a RAW DOTTED KEY in production, because only the admin
    // layout loads the admin words. Move the string into the namespace its readers own (a key in
    // `common.*` or the route's own namespace), or stop importing the admin module from there.
    // Never add an exemption here.
    expect({ adminKeysOnNonAdminRoutes: offenders }).toEqual({ adminKeysOnNonAdminRoutes: [] })
  })

  test('no route outside /admin imports the admin slice loader', () => {
    expect(FROM_NON_ADMIN.has(ADMIN_LOADER)
      ? chain(FROM_NON_ADMIN, ADMIN_LOADER) : 'not reached').toBe('not reached')
  })

  test('only the admin layout and the sandbox layout import it', () => {
    const importers = FILES.filter((f) => (EDGES.get(f) ?? []).includes(ADMIN_LOADER)).map(rel).sort()
    expect(importers).toEqual(['app/admin/layout.tsx', 'app/sandbox/layout.sandbox.tsx'])
  })
})

/**
 * Files that hold `admin.*` keys and that NO route loads at all — kept on purpose, each with why.
 * Not an exemption from the rule above (a non-admin route reaching one still fails there); this
 * only says "no route mounts it today". The test below fails the day one IS mounted, so the line
 * cannot go stale.
 */
const UNROUTED: Record<string, string> = {
  'components/AiReliabilityCard.tsx':
    'Hidden from /admin/scholarship on 2026-06-13 pending the owner\'s placement decision; the '
    + 'component is kept (see the comment at its old import in app/admin/scholarship/page.tsx).',
}

describe('every admin.* key lives where the console loads it', () => {
  test('each file holding an admin.* key is reachable from an admin (or sandbox) entry', () => {
    const stranded = ADMIN_KEY_FILES.filter((f) => !FROM_ADMIN.has(f)).map(rel)
      .filter((f) => !(f in UNROUTED))
    expect({ adminKeysOutsideTheConsole: stranded }).toEqual({ adminKeysOutsideTheConsole: [] })
  })

  test('each declared unrouted file is real, holds admin keys, and is still mounted by no route', () => {
    for (const [f, why] of Object.entries(UNROUTED)) {
      const full = path.join(SRC, ...f.split('/'))
      expect(TEXT.has(full)).toBe(true)
      expect(adminKeysIn(full).length).toBeGreaterThan(0)
      expect(FROM_ADMIN.has(full) || FROM_NON_ADMIN.has(full)).toBe(false)
      expect(why.length).toBeGreaterThan(60)
    }
  })
})
