/**
 * IMPORT LOOPS IN `src/` — the value graph must have none, and the type-only loops are REPORTED
 * (TD-270, 2026-10-04).
 *
 * Code health H13 found 24 type-only cycles in `src/lib/admin-api/` by hand: `AdminScholarshipDetail`
 * (in `applications.ts`) names types owned by `interviews`, `lifecycle`, `resolution` and
 * `verdict`, whose functions in turn return it. Every edge is `import type`, which TypeScript
 * erases, so there is no runtime cycle and no initialisation hazard — and the three ways to
 * remove them were each rejected in writing as worse to read. Nothing reported any of it, so the
 * first VALUE edge closing one of those loops (a function in one module calling a function in
 * another) would have gone in unseen.
 *
 * This test is that report:
 *  1. ZERO value cycles anywhere in `src/` (non-test files). A value cycle is the thing that can
 *     actually break: a module read before it finished initialising.
 *  2. The type-only loops are a CLOSED set, pinned below with their reason. A new module joining
 *     one, or a new loop, fails here; the set may only shrink. A type loop that becomes a value
 *     loop fails rule 1.
 *
 * The graph is built from the source text (static `import`/`export … from`; a `type`-only import
 * or a specifier list that is all `type X` is a TYPE edge, anything else a VALUE edge). Only
 * edges that resolve to a file inside `src/` count — packages cannot loop back into the app.
 * The detector is proved on a synthetic graph first, so a parser that stopped seeing edges would
 * go red there rather than reporting "no cycles" for ever.
 */
import * as fs from 'fs'
import * as path from 'path'
import { WEB_ROOT, walkFloor, floorCount } from '@/test/sourceGuard'

type Edge = { to: string; type: boolean }
type Graph = Record<string, Edge[]>

const IMPORT_RE = /^\s*(import|export)\s+(type\s+)?([^;]*?)\s*from\s*['"]([^'"]+)['"]/gm
const SIDE_EFFECT_RE = /^\s*import\s+['"]([^'"]+)['"]/gm

/** Parse one module's static imports into raw edges `{spec, type}`. */
function parseImports(src: string): Array<{ spec: string; type: boolean }> {
  const out: Array<{ spec: string; type: boolean }> = []
  for (const m of src.matchAll(IMPORT_RE)) {
    let type = Boolean(m[2])
    if (!type) {
      const braces = m[3].trim().match(/^\{([\s\S]*)\}$/)
      if (braces) {
        const specs = braces[1].split(',').map((s) => s.trim()).filter(Boolean)
        type = specs.length > 0 && specs.every((s) => s.startsWith('type '))
      }
    }
    out.push({ spec: m[4], type })
  }
  for (const m of src.matchAll(SIDE_EFFECT_RE)) out.push({ spec: m[1], type: false })
  return out
}

/** Build the graph over `files` (key = POSIX path relative to `src/`, value = source). */
function buildGraph(files: Record<string, string>): Graph {
  const known = new Set(Object.keys(files))
  const resolve = (from: string, spec: string): string | null => {
    let base: string
    if (spec.startsWith('@/')) base = spec.slice(2)
    else if (spec.startsWith('.')) base = path.posix.normalize(path.posix.join(path.posix.dirname(from), spec))
    else return null
    for (const c of [`${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`]) {
      if (known.has(c)) return c
    }
    return null
  }
  const g: Graph = {}
  for (const [file, src] of Object.entries(files)) {
    g[file] = []
    for (const { spec, type } of parseImports(src)) {
      const to = resolve(file, spec)
      if (to) g[file].push({ to, type })
    }
  }
  return g
}

/** Strongly connected components of size > 1 (Tarjan). `valueOnly` drops the type edges. */
function loops(g: Graph, valueOnly: boolean): string[][] {
  let next = 0
  const index: Record<string, number> = {}
  const low: Record<string, number> = {}
  const stack: string[] = []
  const onStack = new Set<string>()
  const out: string[][] = []
  const visit = (v: string): void => {
    index[v] = low[v] = next++
    stack.push(v)
    onStack.add(v)
    for (const e of g[v] ?? []) {
      if (valueOnly && e.type) continue
      if (index[e.to] === undefined) {
        visit(e.to)
        low[v] = Math.min(low[v], low[e.to])
      } else if (onStack.has(e.to)) {
        low[v] = Math.min(low[v], index[e.to])
      }
    }
    if (low[v] === index[v]) {
      const comp: string[] = []
      let w: string
      do {
        w = stack.pop() as string
        onStack.delete(w)
        comp.push(w)
      } while (w !== v)
      if (comp.length > 1) out.push(comp.sort())
    }
  }
  for (const v of Object.keys(g).sort()) if (index[v] === undefined) visit(v)
  return out
}

/**
 * THE CLOSED SET — the one type-only loop the codebase holds, and why it stays (TD-270): the
 * widest type in the app, `AdminScholarshipDetail`, names types from four domain modules whose
 * functions return it. Moving the types apart would separate each domain's types from its own
 * functions. All edges are `import type`. It may only SHRINK — delete a module from this list
 * when it leaves the loop; never add one.
 */
const KNOWN_TYPE_LOOP = [
  'lib/admin-api/applications.ts',
  'lib/admin-api/interviews.ts',
  'lib/admin-api/lifecycle.ts',
  'lib/admin-api/resolution.ts',
  'lib/admin-api/verdict.ts',
]

describe('the detector bites (a synthetic graph)', () => {
  const files = {
    'lib/a.ts': "import { b } from './b'\nexport const a = 1\n",
    'lib/b.ts': "import { a } from '@/lib/a'\nexport const b = 2\n",
    'lib/t1.ts': "import type { T2 } from './t2'\nexport type T1 = { t: T2 }\n",
    'lib/t2.ts': "import { type T1 } from './t1'\nexport type T2 = { t?: T1 }\n",
    'lib/m.ts': "import {\n  type T1,\n  b,\n} from './b'\nexport const m = b\n",
    'lib/x.ts': "import React from 'react'\nexport const x = React\n",
  }
  const g = buildGraph(files)

  it('reads a value edge, a type edge, a mixed multi-line edge and an alias', () => {
    expect(g['lib/a.ts']).toEqual([{ to: 'lib/b.ts', type: false }])
    expect(g['lib/b.ts']).toEqual([{ to: 'lib/a.ts', type: false }])
    expect(g['lib/t1.ts']).toEqual([{ to: 'lib/t2.ts', type: true }])
    expect(g['lib/t2.ts']).toEqual([{ to: 'lib/t1.ts', type: true }])
    expect(g['lib/m.ts']).toEqual([{ to: 'lib/b.ts', type: false }])   // one value specifier = value
    expect(g['lib/x.ts']).toEqual([])                                    // a package is not a node
  })

  it('finds the value loop and only it, and the type loop only when types count', () => {
    expect(loops(g, true)).toEqual([['lib/a.ts', 'lib/b.ts']])
    expect(loops(g, false)).toEqual(expect.arrayContaining([['lib/a.ts', 'lib/b.ts'], ['lib/t1.ts', 'lib/t2.ts']]))
    expect(loops(g, false)).toHaveLength(2)
  })
})

describe('src/ import loops', () => {
  const SRC = path.join(WEB_ROOT, 'src')
  const paths = walkFloor(SRC, 350,
    'every non-test module is a node of the import graph; a walk that narrowed would report no '
    + 'loops for ever',
    { exts: ['.ts', '.tsx'], skip: ['__tests__', 'test'] })
    .filter((f) => !/\.test\.tsx?$/.test(f))
  const files: Record<string, string> = {}
  for (const f of paths) {
    files[path.relative(SRC, f).split(path.sep).join('/')] = fs.readFileSync(f, 'utf8')
  }
  const g = buildGraph(files)
  floorCount(Object.values(g).flat(), 1000, 'in-app import edges',
    'the loops below are only as real as the edges the parser found; on 2026-10-04 it found ~1,700')

  it('has NO value cycle anywhere (the one that can break at start-up)', () => {
    expect(loops(g, true)).toEqual([])
  })

  it('holds only the one known type-only loop, which may only shrink', () => {
    const typeLoops = loops(g, false)
    const unknown = typeLoops.filter((c) => !c.every((m) => KNOWN_TYPE_LOOP.includes(m)))
    expect(unknown).toEqual([])
    // The ledger names nothing that has left the loop: delete a module from KNOWN_TYPE_LOOP when
    // it does, so the set keeps meaning what it says.
    const inLoops = new Set(typeLoops.flat())
    expect(KNOWN_TYPE_LOOP.filter((m) => !inLoops.has(m))).toEqual([])
  })
})
