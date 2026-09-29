/**
 * Static guard: `tabular-nums` marks FIGURES, and figures in a column carry it (TD-310 review).
 *
 * Why. Since TD-310 the product paints in Lexend, which has no tabular figures: its digits are
 * different widths, so a column of numbers stops lining up ("1,111,111" measured 56.5 px against
 * "8,000,000" at 66.6 px). `globals.css` therefore paints every `.tabular-nums` in IBM Plex Sans
 * (or the sponsor portal's Inter). Two things follow, and this file pins both:
 *
 *  1. A right-aligned table cell holding a figure must carry `tabular-nums`, or its column
 *     jitters in Lexend.
 *  2. `tabular-nums` must sit on the figure, not on a container or a sentence — otherwise the
 *     WORDS around it change face too (a table body, a chart legend, "Showing 3 of 12"). A lone
 *     figure in running text ("Merit 87") does not need even digits, so it carries nothing.
 *
 * What it does NOT prove: how anything looks. That was measured in a browser (CHANGELOG TD-310).
 */
import * as fs from 'fs'
import * as path from 'path'
import { WEB_ROOT, floorCount, walkFloor } from '@/test/sourceGuard'

const files = walkFloor(path.join(WEB_ROOT, 'src'), 300,
  'every .tsx file is scanned for how it uses tabular-nums (TD-310 review)', { exts: ['.tsx'] })
  .filter((f) => !/\.test\.tsx$/.test(f))
const rel = (f: string) => path.relative(WEB_ROOT, f).split(path.sep).join('/')
const sources = files.map((f) => ({ file: rel(f), text: fs.readFileSync(f, 'utf8').replace(/\r\n/g, '\n') }))

describe('a right-aligned figure cell carries tabular-nums', () => {
  // `<td className="…">` or `<td className={`…`}>`, then the cell's first text.
  const TD = /<td\s+className=(?:"([^"]*)"|\{`([^`]*)`\})[^>]*>\s*([^<\n]*)/g
  const cells: { where: string; cls: string; body: string }[] = []
  for (const { file, text } of sources) {
    for (const m of Array.from(text.matchAll(TD))) {
      const cls = m[1] ?? m[2]
      const body = m[3].trim()
      if (!/(^|\s)text-right(\s|$)/.test(cls)) continue
      // A figure: an expression, a digit or a signed amount. A dash-only cell is not a figure.
      if (!/^(\{|[-−]?\{|\d)/.test(body) || /^\{dash\}$|^—$/.test(body)) continue
      const line = text.slice(0, m.index).split('\n').length
      cells.push({ where: `${file}:${line}`, cls, body })
    }
  }

  it('finds the figure cells it guards', () => {
    // 2026-09-29: billing usage (5), course-data coverage (6), invoice lines and totals (8), and
    // the cells that already carried it. A walk that finds fewer has stopped seeing them.
    floorCount(cells, 25, 'right-aligned figure cells', 'the billing, coverage and invoice tables')
  })

  it('every one of them carries tabular-nums', () => {
    const bare = cells.filter((c) => !/(^|\s)tabular-nums(\s|$)/.test(c.cls)).map((c) => `${c.where}  ${c.body}`)
    expect(bare).toEqual([])
  })
})

describe('tabular-nums sits on the figure, not around it', () => {
  it('never on a table, row group, row or list — the words inside would change face', () => {
    const CONTAINER = /<(table|thead|tbody|tfoot|tr|ol|ul|dl)\b[^>]*className=(?:"[^"]*|\{`[^`]*)\btabular-nums\b/g
    const hits = sources.flatMap(({ file, text }) =>
      Array.from(text.matchAll(CONTAINER), (m) => `${file}:${text.slice(0, m.index).split('\n').length} <${m[1]}>`))
    expect(hits).toEqual([])
  })

  it('never on a figure inside a translated sentence ("Visits 12", "Merit 87")', () => {
    // A t(…) label followed straight by a tabular span is a figure in running text.
    const INLINE = /t\([^()]*\)\}\s*(?:\{' '\})?\s*<span className="(?:[^"]*\s)?tabular-nums\b/g
    const hits = sources.flatMap(({ file, text }) =>
      Array.from(text.matchAll(INLINE), (m) => `${file}:${text.slice(0, m.index).split('\n').length}`))
    expect(hits).toEqual([])
  })

  it('never on a whole translated sentence ("Showing 3 of 12")', () => {
    const SENTENCE = /className="[^"]*\btabular-nums\b[^"]*"[^>]*>\s*\{t\(/g
    const hits = sources.flatMap(({ file, text }) =>
      Array.from(text.matchAll(SENTENCE), (m) => `${file}:${text.slice(0, m.index).split('\n').length}`))
    expect(hits).toEqual([])
  })
})
