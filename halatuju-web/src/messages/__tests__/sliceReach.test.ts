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
 * Review fixes (2026-10-21): every file is read by the TypeScript PARSER (a `/*` inside a `//`
 * comment had swallowed real imports under the regex stripper); a bare `'admin'` VALUE in a
 * reachable non-admin file is refused too (a namespace joined to a key at run time), with a short
 * declared list of the known non-i18n ones; and the readers of the server-chosen `label_key`
 * (seeded `admin.programme.question.*`) are pinned to the admin side.
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
import * as ts from 'typescript'

import { CORE_KEEPS as KEEPS } from '../../../scripts/messages-slice-loader'

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

/**
 * What one source file says, read by the TYPESCRIPT PARSER — never by regex.
 *
 * ⚠ Review fix (2026-10-21): the first cut stripped `/* … *\/` before `//` with regexes, so a `/*`
 * inside a LINE comment (`app/admin/guide/page.tsx`: `// src/content/manual/* —`) opened a "block"
 * that swallowed the real imports below it, and the walk silently stopped there. The parser knows
 * what a comment, a string and a template are, so no text in either can hide or invent an edge.
 *
 *  - `specifiers`: every RUNTIME module specifier — `import … from`, `import '…'`, `export … from`,
 *    `import()`, `require()`. `import type` / `export type` are skipped: erased, they ship nothing.
 *  - `strings`: every string literal and template in a VALUE position, with its line. A template
 *    is spelled with `${}` for each hole (`` `admin.${h}` `` → `admin.${}`). Literals in a TYPE
 *    position (`type SliceName = 'core' | 'admin'`) are erased at build and are not collected.
 *  - `readsLabelKey`: the file reads a `.label_key` property (a key the SERVER chose; see below).
 *  - `lazy`: the subset of `specifiers` reached by `import()` (TD-416: the scholarship rule needs
 *    to know what evaluates BEFORE a route renders, and an `import()` does not).
 */
interface FileScan {
  specifiers: string[]
  lazy: string[]
  strings: Array<{ text: string; line: number }>
  readsLabelKey: boolean
}

function scanSource(fileName: string, source: string): FileScan {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true,
    /\.[jt]sx$/.test(fileName) ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const out: FileScan = { specifiers: [], lazy: [], strings: [], readsLabelKey: false }
  const specifierNodes = new Set<ts.Node>()
  const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
  const inTypePosition = (n: ts.Node) => ts.isLiteralTypeNode(n.parent)

  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      specifierNodes.add(node.moduleSpecifier)
      if (!node.importClause?.isTypeOnly) out.specifiers.push(node.moduleSpecifier.text)
    } else if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
      specifierNodes.add(node.moduleSpecifier)
      if (!node.isTypeOnly) out.specifiers.push(node.moduleSpecifier.text)
    } else if (ts.isCallExpression(node) && node.arguments.length > 0
      && ts.isStringLiteralLike(node.arguments[0])
      && (node.expression.kind === ts.SyntaxKind.ImportKeyword
        || (ts.isIdentifier(node.expression) && node.expression.text === 'require'))) {
      specifierNodes.add(node.arguments[0])
      out.specifiers.push(node.arguments[0].text)
      if (node.expression.kind === ts.SyntaxKind.ImportKeyword) out.lazy.push(node.arguments[0].text)
    } else if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node))
      && !specifierNodes.has(node) && !inTypePosition(node)) {
      out.strings.push({ text: node.text, line: lineOf(node) })
    } else if (ts.isTemplateExpression(node)) {
      const text = node.head.text + node.templateSpans.map((s) => '${}' + s.literal.text).join('')
      out.strings.push({ text, line: lineOf(node) })
    } else if (ts.isPropertyAccessExpression(node) && node.name.text === 'label_key') {
      out.readsLabelKey = true
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
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
const SCAN = new Map(FILES.map((f) => [f, scanSource(f, fs.readFileSync(f, 'utf8'))]))

function resolveSpecifier(from: string, spec: string): string | null {
  const bare = spec.split('?')[0]
  let base: string
  if (bare.startsWith('@/')) base = path.join(SRC, bare.slice(2))
  else if (bare.startsWith('.')) base = path.join(path.dirname(from), bare)
  else return null                                       // a package — not ours to walk
  for (const cand of [base, `${base}.ts`, `${base}.tsx`, `${base}.js`, `${base}.jsx`,
    path.join(base, 'index.ts'), path.join(base, 'index.tsx')]) {
    if (SCAN.has(cand)) return cand
  }
  return null                                            // JSON, CSS, an asset — no code to walk
}

const EDGES = new Map(FILES.map((f) => {
  const out = new Set<string>()
  for (const spec of (SCAN.get(f) as FileScan).specifiers) {
    const to = resolveSpecifier(f, spec)
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

/**
 * An `admin.` key: a literal or template that STARTS with `admin.` and a key segment (or a hole) —
 * `'admin.x'`, `` `admin.x` ``, `` `admin.${h}` `` — or a template that BUILDS one after a hole
 * (`` `${ns}admin.` ``). A file name (`'admin.ts'`) is not a key.
 */
const ADMIN_KEY = /^admin\.(?:\$\{\}|[A-Za-z_])|\$\{\}admin\./
const LOOKS_LIKE_A_FILE = /^admin\.(ts|tsx|js|jsx|json|py|md|css|html)$/

/** The namespace NAME alone — `'admin'` joined to `'.x'` at run time (`[ns, k].join('.')`). */
const BARE_ADMIN = /^admin$/

function hitsIn(f: string, rule: RegExp, skip?: RegExp): string[] {
  return (SCAN.get(f) as FileScan).strings
    .filter((s) => rule.test(s.text) && !(skip && skip.test(s.text)))
    .map((s) => `${rel(f)}:${s.line}  ${JSON.stringify(s.text.slice(0, 40))}`)
}

function adminKeysIn(f: string): string[] {
  return hitsIn(f, ADMIN_KEY, LOOKS_LIKE_A_FILE)
}

/**
 * Reachable non-admin files where a bare `'admin'` VALUE is known to be something other than an
 * i18n namespace — each with what it is. A new one is a question, not a line to add: if the value
 * can reach `t()` (joined with `'.'`), the screen shows a raw key. Literals in TYPE positions
 * (`SliceName = 'core' | 'admin'` in `lib/messageChunks.ts`) are erased and never collected.
 */
const BARE_ADMIN_ALLOWED: Record<string, string> = {
  'lib/sessionPolicy.ts':
    'The privileged SESSION SCOPE (`enforceSingleScope(\'admin\' | \'sponsor\')`) and the superseded '
    + 'flag it stores — an auth scope name, never joined into a message key.',
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
      .toContain('"admin.${}"')
  })

  test('the patterns catch each shape and ignore paths, prose and file names', () => {
    const keys = (src: string) => scanSource('x.ts', src).strings
      .filter((s) => ADMIN_KEY.test(s.text) && !LOOKS_LIKE_A_FILE.test(s.text)).map((s) => s.text)
    expect(keys("t('admin.save')")).toEqual(['admin.save'])
    expect(keys('t("admin.nav.home")')).toEqual(['admin.nav.home'])
    expect(keys('t(`admin.${h}`)')).toEqual(['admin.${}'])
    expect(keys('t(`${ns}admin.x`)')).toEqual(['${}admin.x'])
    expect(keys("router.push('/admin/login')")).toEqual([])
    expect(keys("const KEY = 'administration.x'")).toEqual([])
    expect(keys("const f = 'admin.ts'")).toEqual([])
    // Comments are not code, and a string is not a comment.
    expect(keys("// t('admin.save')\n/* 'admin.x' */\nconst s = '// admin.y'")).toEqual([])
    const bare = (src: string) => scanSource('x.ts', src).strings.filter((s) => BARE_ADMIN.test(s.text)).length
    expect(bare("const ns = 'admin'; t([ns, 'save'].join('.'))")).toBe(1)
    // A literal in a TYPE position is erased at build, so it is not collected.
    expect(bare("type SliceName = 'core' | 'admin'")).toBe(0)
  })

  test('⚠ review fix: a `/*` inside a LINE comment does not swallow the imports below it', () => {
    const src = "// src/content/manual/* — the chapters\nimport x from '@/lib/real'\n"
      + "const y = import('./lazy')\nexport { z } from '../reexported'\n"
    expect(scanSource('fixture.tsx', src).specifiers).toEqual(['@/lib/real', './lazy', '../reexported'])
    // …and the real file that met it: every import of the Guide page is followed.
    const guide = path.join(SRC, 'app', 'admin', 'guide', 'page.tsx')
    const text = fs.readFileSync(guide, 'utf8')
    const literalImports = [...text.matchAll(/^import [^\n]*from '(@\/[^']+)'/gm)].map((m) => m[1])
    expect(literalImports.length).toBeGreaterThan(0)
    for (const spec of literalImports) expect((SCAN.get(guide) as FileScan).specifiers).toContain(spec)
  })

  test('type-only imports are not edges — they ship nothing', () => {
    expect(scanSource('x.ts', "import type { A } from '@/lib/a'\nexport type { B } from './b'\n").specifiers)
      .toEqual([])
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

  test('⚠ no reachable non-admin file holds a bare "admin" value, except the declared ones', () => {
    // `'admin'` joined to a key at run time is the shape the admin.* rule above cannot see.
    const offenders = [...FROM_NON_ADMIN.keys()]
      .filter((f) => !(rel(f) in BARE_ADMIN_ALLOWED))
      .flatMap((f) => hitsIn(f, BARE_ADMIN).map((h) => `${h}\n    via ${chain(FROM_NON_ADMIN, f)}`))
    expect({ bareAdminOnNonAdminRoutes: offenders }).toEqual({ bareAdminOnNonAdminRoutes: [] })
  })

  test('each bare-"admin" allowance is real, still needed, still reachable, and says why', () => {
    for (const [f, why] of Object.entries(BARE_ADMIN_ALLOWED)) {
      const full = path.join(SRC, ...f.split('/'))
      expect(hitsIn(full, BARE_ADMIN).length).toBeGreaterThan(0)
      expect(FROM_NON_ADMIN.has(full)).toBe(true)
      expect(why.length).toBeGreaterThan(60)
    }
  })

  test('a key the SERVER chooses as `label_key` (seeded `admin.programme.question.*`) is rendered on the admin side only', () => {
    // `seed_application_catalogue.py` seeds question labels as `admin.programme.question.<code>`
    // and serves them as `label_key`; no static scan can see a key that arrives in a payload. So
    // the READERS are pinned: every production file that reads `.label_key` must be one no route
    // outside /admin reaches. A student-side reader of that payload would show a raw dotted key.
    const readers = FILES.filter((f) => (SCAN.get(f) as FileScan).readsLabelKey)
    expect(readers.map(rel)).toContain('components/admin/ProgrammeConfigTab.tsx')
    const leaking = readers.filter((f) => FROM_NON_ADMIN.has(f))
      .map((f) => `${rel(f)}\n    via ${chain(FROM_NON_ADMIN, f)}`)
    expect({ labelKeyReadersOnNonAdminRoutes: leaking }).toEqual({ labelKeyReadersOnNonAdminRoutes: [] })
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

/**
 * ═══ TD-416 (2026-10-29): THE SCHOLARSHIP AND SPONSOR SLICES ══════════════════════════════════
 *
 * Two more slices left the English core every route downloads: `scholarship.*` (~30 kB gz) and the
 * four `sponsor*` namespaces (~6 kB gz). Each is loaded by its own module (`lib/messagesScholarship.ts`,
 * `lib/messagesSponsor.ts`), which the PAGE of each route that shows those words imports — so the
 * slice is counted in exactly those routes' first-load JS and in no other's. `scholarship` keeps
 * the children `CORE_KEEPS` names in core (`scholarship.nav` / `.subnav` for `AppHeader`,
 * `.banner` for `/dashboard`).
 *
 * The same failure as the admin slice, if this breaks: a screen shows a RAW DOTTED KEY in
 * production while every jest render passes (jest hands every slice the whole file). So, for each
 * slice and each ROUTE (a page plus every layout above it — what evaluates before the page renders):
 *
 *  A. if anything the route can reach — statically OR through an `import()` — holds a key of the
 *     slice, the route reaches the slice's loader STATICALLY (the words are merged before render);
 *  B. the shared special files (`error`, `loading`, `not-found`, …) reach no key of the slice —
 *     they render on routes that never load it (`loading.tsx` even before the page's module runs);
 *  C. the routes that load it are exactly the slice's declared `owners` — a slice costs first-load
 *     JS wherever it goes, so putting it on another route is a decision that edits this list;
 *  D. only `'use client'` route files (a page or a layout) import the loader: a server component
 *     would merge the words on the server only, and a shared component would carry the slice to
 *     every route that mounts it;
 *  E. a route whose LAYOUT loads the slice loads it from its PAGE too, so the budgeted page figure
 *     counts it (TD-304: weight a layout carries is printed, not budgeted). The sandbox is exempt:
 *     it is compiled out of production, so it has no budgeted figure.
 *
 * Conservative on purpose, like the admin rule: a key in a reachable file counts even if that
 * branch never renders there. For `scholarship` a key is any literal or template starting
 * `scholarship.` whose child is not kept — `'scholarship.'` alone and `` `scholarship.${x}` `` count,
 * since the child cannot be known.
 */
const CORE_KEEPS = KEEPS as Record<string, string[]>
const KEPT = CORE_KEEPS.scholarship

interface SliceRule {
  loader: string
  /** A literal or template that is a key of this slice. */
  key: RegExp
  /** …except these (file names that happen to start like a namespace). */
  notKey: RegExp
  /** The routes that load it — the production routes, plus the sandbox where it mounts one. */
  owners: string[]
}

const SLICE_RULES: Record<'scholarship' | 'sponsor', SliceRule> = {
  scholarship: {
    loader: path.join(SRC, 'lib', 'messagesScholarship.ts'),
    key: new RegExp(`^scholarship\\.(?!(?:${KEPT.join('|')})(?:\\.|$))|\\$\\{\\}scholarship\\.`),
    notKey: /^scholarship\.(ts|tsx|js|jsx|json|py|md|css|html)$/,
    // The 17 routes that show these words on 2026-10-29, plus the sandbox.
    owners: [
      '/admin/profile', '/admin/programme', '/admin/requests', '/admin/requests/[id]',
      '/admin/scholarship', '/admin/scholarship/[id]', '/admin/sources', '/admin/students',
      '/admin/students/[id]', '/onboarding/profile', '/profile', '/sandbox', '/sandbox/[surface]',
      '/scholarship', '/scholarship/application', '/scholarship/apply', '/scholarship/award',
      '/scholarship/bursary', '/scholarship/onboarding',
    ],
  },
  sponsor: {
    loader: path.join(SRC, 'lib', 'messagesSponsor.ts'),
    key: /^sponsor(Portal|Auth|Pool|Landing)\.|\$\{\}sponsor(Portal|Auth|Pool|Landing)\./,
    notKey: /^sponsor\w*\.(ts|tsx|js|jsx|json|py|md|css|html)$/,
    // The 10 sponsor routes that show these words on 2026-10-29, plus the sandbox (it mounts the
    // sponsor Students PAGE itself, which brings the slice with it).
    owners: [
      '/sandbox', '/sandbox/[surface]',
      '/sponsor', '/sponsor/account', '/sponsor/auth/reset', '/sponsor/login', '/sponsor/my-students/[id]',
      '/sponsor/register', '/sponsor/students', '/sponsor/students/[id]', '/sponsor/terms', '/sponsor/trust',
    ],
  },
}

const PAGE_FILE = /^page(\.sandbox)?\.(tsx|ts|jsx|js)$/
const LAYOUT_FILE = /^layout(\.sandbox)?\.(tsx|ts|jsx|js)$/
const SPECIAL_FILE = /^(error|not-found|loading|template|global-error|default)\.(tsx|ts|jsx|js)$/
const PAGES = FILES.filter((f) => f.startsWith(APP + path.sep) && PAGE_FILE.test(path.basename(f)))
const SPECIALS = FILES.filter((f) => f.startsWith(APP + path.sep) && SPECIAL_FILE.test(path.basename(f)))

/** `app/sponsor/(portal)/students/[id]/page.tsx` → `/sponsor/students/[id]` (groups dropped). */
function routeOf(page: string): string {
  const segs = path.relative(APP, path.dirname(page)).split(path.sep)
    .filter((s) => s && !/^\(.*\)$/.test(s))
  return `/${segs.join('/')}`
}

/** Every layout above a page, nearest first. */
function layoutsAbove(page: string): string[] {
  const out: string[] = []
  for (let dir = path.dirname(page); dir.startsWith(APP); dir = path.dirname(dir)) {
    for (const f of FILES) if (path.dirname(f) === dir && LAYOUT_FILE.test(path.basename(f))) out.push(f)
    if (dir === APP) break
  }
  return out
}

/** Breadth-first like `reach`, but over STATIC edges only (no `import()`). */
function reachStatic(entries: string[]): Map<string, string | null> {
  const parent = new Map<string, string | null>(entries.map((e) => [e, null]))
  const queue = [...entries]
  while (queue.length) {
    const f = queue.shift() as string
    // Each `import()` removes ONE occurrence, so a module imported both ways is still static.
    const lazy = [...(SCAN.get(f) as FileScan).lazy]
    for (const spec of (SCAN.get(f) as FileScan).specifiers) {
      const at = lazy.indexOf(spec)
      if (at >= 0) { lazy.splice(at, 1); continue }
      const to = resolveSpecifier(f, spec)
      if (to && !parent.has(to)) { parent.set(to, f); queue.push(to) }
    }
  }
  return parent
}

const ROUTES = PAGES.map((page) => {
  const files = [page, ...layoutsAbove(page)]
  return { route: routeOf(page), page, all: reach(files), stat: reachStatic(files), pageOnly: reachStatic([page]) }
})

const keysOf = (rule: SliceRule, f: string) => hitsIn(f, rule.key, rule.notKey)
const isClientRouteFile = (f: string) => f.startsWith(APP + path.sep)
  && (PAGE_FILE.test(path.basename(f)) || LAYOUT_FILE.test(path.basename(f)))
  && /^\s*['"]use client['"]/.test(fs.readFileSync(f, 'utf8'))

describe('TD-416: the slice patterns', () => {
  test('scholarship: every unkept child counts; kept children and file names do not', () => {
    const rule = SLICE_RULES.scholarship
    const keys = (src: string) => scanSource('x.ts', src).strings
      .filter((s) => rule.key.test(s.text) && !rule.notKey.test(s.text)).map((s) => s.text)
    expect(keys("t('scholarship.apply.title')")).toEqual(['scholarship.apply.title'])
    expect(keys('t(`scholarship.docs.type.${c}`)')).toEqual(['scholarship.docs.type.${}'])
    expect(keys('t(`scholarship.${area}.title`)')).toEqual(['scholarship.${}.title'])
    expect(keys("const p = 'scholarship.'")).toEqual(['scholarship.'])
    expect(keys('t(`${ns}scholarship.x`)')).toEqual(['${}scholarship.x'])
    expect(keys("t('scholarship.nav.home'); t('scholarship.subnav.x'); t('scholarship.banner.cta')")).toEqual([])
    expect(keys("t('scholarship.navigator.x')")).toEqual(['scholarship.navigator.x'])
    expect(keys("router.push('/scholarship/apply'); const f = 'scholarship.ts'")).toEqual([])
  })

  test('sponsor: the four namespaces count; admin.sponsors and paths do not', () => {
    const rule = SLICE_RULES.sponsor
    const keys = (src: string) => scanSource('x.ts', src).strings
      .filter((s) => rule.key.test(s.text) && !rule.notKey.test(s.text)).map((s) => s.text)
    expect(keys("t('sponsorPortal.nav.home'); t('sponsorAuth.email')")).toEqual(['sponsorPortal.nav.home', 'sponsorAuth.email'])
    expect(keys('t(`sponsorPool.${k}`); t(`sponsorLanding.hero.${x}`)')).toEqual(['sponsorPool.${}', 'sponsorLanding.hero.${}'])
    expect(keys("t('admin.sponsors.title'); router.push('/sponsor/login'); t('sponsorship.x')")).toEqual([])
  })

  test('static and lazy edges are told apart', () => {
    const s = scanSource('x.tsx', "import a from '@/lib/a'\nconst b = import('@/lib/b')\n")
    expect(s.specifiers).toEqual(['@/lib/a', '@/lib/b'])
    expect(s.lazy).toEqual(['@/lib/b'])
  })
})

describe.each(Object.entries(SLICE_RULES))('TD-416: the %s slice is loaded wherever its words are read', (name, rule) => {
  const keyFiles = FILES.filter((f) => keysOf(rule, f).length > 0)
  const loaders = ROUTES.filter((r) => r.stat.has(rule.loader))

  test('the walk really read the tree (floors)', () => {
    expect(PAGES.length).toBeGreaterThanOrEqual(80)
    expect(SPECIALS.map(rel)).toContain('app/loading.tsx')
    expect(keyFiles.length).toBeGreaterThanOrEqual(name === 'scholarship' ? 40 : 10)
    expect(loaders.length).toBeGreaterThanOrEqual(10)
  })

  test('⚠ A: every route that can reach a key of the slice loads it before it renders', () => {
    const offenders = ROUTES.filter((r) => !r.stat.has(rule.loader)).flatMap((r) => {
      const holder = [...r.all.keys()].find((f) => keysOf(rule, f).length > 0)
      return holder ? [`${r.route}: ${keysOf(rule, holder)[0]}\n    via ${chain(r.all, holder)}`] : []
    })
    // ⚠ If this fails, that route would show RAW DOTTED KEYS in production. Either the route really
    // shows these words — import the slice's module from its page (and add the route to the
    // slice's owners: the slice now costs that route its weight) — or a widely shared component
    // has started reading a key of the slice, and the key belongs in that component's own namespace.
    expect({ routesReadingTheSliceWithoutLoadingIt: offenders })
      .toEqual({ routesReadingTheSliceWithoutLoadingIt: [] })
  })

  test('B: the shared special files (error, loading, not-found…) reach no key of the slice', () => {
    const offenders = SPECIALS.flatMap((s) => {
      const from = reach([s])
      const holder = [...from.keys()].find((f) => keysOf(rule, f).length > 0)
      return holder ? [`${rel(s)}: ${keysOf(rule, holder)[0]}\n    via ${chain(from, holder)}`] : []
    })
    expect({ specialFilesReadingTheSlice: offenders }).toEqual({ specialFilesReadingTheSlice: [] })
  })

  test('C: the routes that load the slice are exactly its declared owners', () => {
    // A route here that is not declared carries the slice's weight; see A for the other way round.
    expect(loaders.map((r) => r.route).sort()).toEqual([...rule.owners].sort())
  })

  test('D: only client route files (a page or a layout) import the loader', () => {
    const importers = FILES.filter((f) => (EDGES.get(f) ?? []).includes(rule.loader))
    expect(importers.length).toBeGreaterThanOrEqual(10)
    expect(importers.filter((f) => !isClientRouteFile(f)).map(rel)).toEqual([])
  })

  test('E: a production route that loads the slice loads it from its PAGE, so the budget counts it', () => {
    const hidden = loaders.filter((r) => !r.route.startsWith('/sandbox') && !r.pageOnly.has(rule.loader))
      .map((r) => `${r.route}: loaded by a layout only (${chain(r.stat, rule.loader)})`)
    expect({ sliceHiddenInALayout: hidden }).toEqual({ sliceHiddenInALayout: [] })
  })

  test('the admin slice is untouched by this: no student or sponsor owner reaches the admin loader', () => {
    const leaking = loaders.filter((r) => !r.route.startsWith('/admin') && !r.route.startsWith('/sandbox')
      && r.all.has(ADMIN_LOADER)).map((r) => r.route)
    expect(leaking).toEqual([])
  })
})

describe('every admin.* key lives where the console loads it', () => {
  test('each file holding an admin.* key is reachable from an admin (or sandbox) entry', () => {
    const stranded = ADMIN_KEY_FILES.filter((f) => !FROM_ADMIN.has(f)).map(rel)
      .filter((f) => !(f in UNROUTED))
    expect({ adminKeysOutsideTheConsole: stranded }).toEqual({ adminKeysOutsideTheConsole: [] })
  })

  test('each declared unrouted file is real, holds admin keys, and is still mounted by no route', () => {
    for (const [f, why] of Object.entries(UNROUTED)) {
      const full = path.join(SRC, ...f.split('/'))
      expect(SCAN.has(full)).toBe(true)
      expect(adminKeysIn(full).length).toBeGreaterThan(0)
      expect(FROM_ADMIN.has(full) || FROM_NON_ADMIN.has(full)).toBe(false)
      expect(why.length).toBeGreaterThan(60)
    }
  })
})
