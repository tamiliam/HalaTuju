/**
 * THE BUDGET FOR CODE HEALTH H17, WRITTEN WHERE IT CAN ACTUALLY BITE.
 *
 * ⚠ **WHY THIS IS A SOURCE GUARD AND NOT A NUMBER OF KILOBYTES.** H18 owns the measured
 * first-load-JS budget, and it has to, because the only place that number exists is the route
 * table `next build` prints — and jest runs with no build output to read. A byte budget recorded
 * here would be a number nothing measures, which is worse than no budget: it reads as enforced.
 *
 * What CAN be enforced today is the thing that actually causes the regression. The 1.53 MB did
 * not arrive by accident or by drift; it arrived because somebody wrote
 * `import ta from '@/messages/ta.json'` at the top of a module every page loads, which is an
 * entirely reasonable line to write. This guard is the sentence "you may not do that again,
 * except in the one module whose job is to do it lazily".
 *
 * Three claims:
 *
 *  1. **Exactly ONE production module statically imports a message catalogue** — `lib/messages.ts`,
 *     and only English, the static fallback the first paint needs. Two exemptions are DECLARED
 *     below with the reason each is paid for by one route rather than by every route.
 *  2. **Malay and Tamil are reached through `import()`**, in `lib/messages.ts`, with literal
 *     specifiers — a computed one makes webpack emit a context module holding every JSON in the
 *     folder, which is the same bug spelled differently.
 *  3. **The scan really read the tree** (the floor). A walk that finds nothing asserts nothing,
 *     and this arc has met that failure four times (TD-276).
 *
 * Test files are exempt throughout: a test runs in node, ships to nobody, and several i18n guards
 * exist precisely to read all three catalogues at once.
 */
import * as fs from 'fs'
import * as path from 'path'

const SRC = path.join(__dirname, '..', '..')

/**
 * ⚠ A FLOOR, not a count. The number only ever moves DOWN by a deliberate edit that says why.
 * Set from the tree on 2026-09-20, which held 388 production source files (tests, the `messages`
 * folder and `*.test.*` excluded), with room to shrink.
 */
const SOURCE_FILE_FLOOR = 330

/**
 * The modules allowed to name a catalogue in a STATIC import, each with what it costs.
 *
 * ⚠ ADDING A LINE HERE IS THE REGRESSION. It is not a list to be extended when a guard is
 * inconvenient — each entry is a route (or every route) paying for a megabyte of words. Two of
 * the three were removed by H17 and the third is the loader itself.
 */
const STATIC_IMPORT_ALLOWED: Record<string, string> = {
  'src/lib/messages.ts':
    'THE LOADER. English only, and static on purpose: it is what the server renders, what the '
    + 'first client paint shows, and what `t()` answers with while another chunk is in the air.',
  // ⚠ `src/lib/preUPlan.ts` WAS HERE, and it is gone — TD-280, closed by code health H18. The
  // officer cockpit's Malay pre-U track label is now RESOLVED BY THE API and served on the
  // payload (`pre_u_track_label`), so the browser downloads no Malay catalogue for it and there
  // is no module to exempt. `/admin/scholarship/[id]` fell from 389 kB of first-load JS to the
  // level of every other route. THIS LIST GOT SHORTER, which is the only direction it may move.
  'src/lib/applyCopyPlatform.ts':
    'The platform default wording in all three languages at once — the one screen whose job is to '
    + 'show an administrator what a Malay or Tamil applicant would read. `ApplyCopyTab` reaches '
    + 'it through an `import()`, so it is a chunk of that PANEL, not of `/admin/programme`.',
}

/** `import x from '@/messages/xx.json'` — the shape that puts a whole catalogue in a bundle. */
const STATIC_CATALOGUE_IMPORT = /(?:^|\n)\s*import\s[^\n;]*?from\s*['"]@\/messages\/(en|ms|ta)\.json['"]/g

/**
 * Comment text is PROSE, not code — the `codeStandards` mirror guard's rule, and this guard
 * needed it on its first run. `messages.ts` documents the computed-specifier trap by WRITING the
 * forbidden line inside a comment, and the check below read its own explanation as the offence.
 * Replaced by spaces, so a failure still points at the right line.
 */
function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:])\/\/[^\n]*/g, (m, lead: string) => lead + ' '.repeat(m.length - lead.length))
}

function walk(dir: string, acc: string[]): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules' || entry.name === 'messages') continue
      walk(full, acc)
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
      acc.push(full)
    }
  }
  return acc
}

function relative(file: string): string {
  return path.relative(path.join(SRC, '..'), file).split(path.sep).join('/')
}

const SOURCE_FILES = walk(SRC, [])

describe('one locale per visitor', () => {
  test('the scan really walked the tree (the floor)', () => {
    // Without this, a walk that started in the wrong folder would find no static imports at all
    // and every claim below would pass over an empty room.
    expect(SOURCE_FILES.length).toBeGreaterThanOrEqual(SOURCE_FILE_FLOOR)
    expect(SOURCE_FILES.map(relative)).toContain('src/lib/i18n.tsx')
    expect(SOURCE_FILES.map(relative)).toContain('src/lib/messages.ts')
  })

  test('only the declared modules statically import a message catalogue', () => {
    const offenders: string[] = []
    for (const file of SOURCE_FILES) {
      const rel = relative(file)
      const text = stripComments(fs.readFileSync(file, 'utf8'))
      const hits = [...text.matchAll(STATIC_CATALOGUE_IMPORT)].map((m) => m[1])
      if (!hits.length) continue
      if (!(rel in STATIC_IMPORT_ALLOWED)) {
        offenders.push(`${rel}  imports  ${hits.join(', ')}`)
      }
    }
    // ⚠ Bite (d). Put `import ta from '@/messages/ta.json'` back into `i18n.tsx` and this is red.
    expect({ modulesShippingAWholeCatalogueToEveryVisitor: offenders })
      .toEqual({ modulesShippingAWholeCatalogueToEveryVisitor: [] })
  })

  test('the provider itself imports no catalogue at all', () => {
    // Named separately because `i18n.tsx` is the one module every route loads, so a static import
    // there is a cost to EVERY visitor rather than to one route. It is worth its own failure.
    const text = stripComments(fs.readFileSync(path.join(SRC, 'lib', 'i18n.tsx'), 'utf8'))
    expect([...text.matchAll(STATIC_CATALOGUE_IMPORT)].map((m) => m[1])).toEqual([])
  })

  test('the loader keeps English static and reaches ms and ta through import()', () => {
    const text = stripComments(fs.readFileSync(path.join(SRC, 'lib', 'messages.ts'), 'utf8'))
    const statics = [...text.matchAll(STATIC_CATALOGUE_IMPORT)].map((m) => m[1])
    expect(statics).toEqual(['en'])
    // Literal specifiers, one per locale — never `import('@/messages/' + locale + '.json')`.
    expect(text).toContain("import('@/messages/ms.json')")
    expect(text).toContain("import('@/messages/ta.json')")
    expect(text).not.toMatch(/import\(\s*['"`]@\/messages\/['"`]\s*\+/)
    expect(text).not.toMatch(/import\(\s*`@\/messages\/\$\{/)
  })

  test('every declared exemption names a real file and says what it costs', () => {
    // A stale exemption is a hole the next author walks through without noticing.
    for (const [rel, why] of Object.entries(STATIC_IMPORT_ALLOWED)) {
      expect(fs.existsSync(path.join(SRC, '..', ...rel.split('/')))).toBe(true)
      expect(why.length).toBeGreaterThan(60)
    }
  })

  test('ApplyCopyTab reaches the platform wording lazily, so its catalogues are a PANEL chunk', () => {
    const text = stripComments(fs.readFileSync(
      path.join(SRC, 'components', 'admin', 'ApplyCopyTab.tsx'), 'utf8'))
    expect(text).toContain("import('@/lib/applyCopyPlatform')")
    expect(text).not.toMatch(/(?:^|\n)\s*import\s[^\n;]*?from\s*['"]@\/lib\/applyCopyPlatform['"]/)
  })

  test('lib/applyCopy stays catalogue-free, because a STUDENT page imports it', () => {
    // ⚠ The measurement that forced the split: with the rest of H17 in place, `/scholarship/apply`
    // was still 539 kB while every other route had fallen to ~260 kB, because `applyCard` and
    // `platformApplyCard` shared a file and only the second one reads the message files.
    const text = stripComments(fs.readFileSync(path.join(SRC, 'lib', 'applyCopy.ts'), 'utf8'))
    expect([...text.matchAll(STATIC_CATALOGUE_IMPORT)].map((m) => m[1])).toEqual([])
    expect(text).not.toContain('platformApplyCard')
  })
})
