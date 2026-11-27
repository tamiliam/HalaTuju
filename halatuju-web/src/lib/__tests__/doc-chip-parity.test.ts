/**
 * Document chip standard S0: today's officer-drawer chips against the SHARED parity fixture.
 *
 * The api's `doc_chips.chips_for` / `pill_for` (halatuju_api/apps/scholarship/doc_chips.py) is checked
 * against the same file by `test_doc_chips.py`. This half runs TODAY's web: `documentFacts` /
 * `documentPill` (cockpitDocFacts.ts, which calls offerFacts.ts and higherResultsFacts.ts), and the
 * drawer's own `factClass` / `yearChip` / `yearClass`, lifted out of DocumentsDrawer.tsx with a stub
 * `t` (no component change). So the server can only serve what the drawer draws today, or one side
 * goes red. Sprint 1+ moves the screens onto the served chips; this test then retires with them.
 */
import * as fs from 'fs'
import * as path from 'path'
import * as vm from 'vm'
import * as ts from 'typescript'
import { documentFacts, documentPill } from '@/lib/cockpitDocFacts'
import type { AdminApplicantDocument } from '@/lib/admin-api'
import { readApi } from '@/test/apiSource'

type Chip = { key: string; status?: string; state: string; kind: string; value?: string }
type Case = { name: string; doc: Record<string, unknown>; chips: Chip[]; pill: string }
type Lifted = {
  factClass: (s: string) => string
  yearChip: (d: AdminApplicantDocument) => { text: string; status: string } | null
  yearClass: (s: string) => string
}

const DRAWER = path.resolve(__dirname, '..', '..', 'app', 'admin', 'scholarship', '[id]', 'view', 'DocumentsDrawer.tsx')

// The drawer's text colours, as the chip standard's four states.
const STATE: Record<string, string> = {
  'text-positive-700': 'green',
  'text-caution-700': 'amber',
  'text-critical-600': 'red',
  'text-ground-400': 'grey',
  'text-ground-500': 'grey',
}

function slice(src: string, start: string, end: string): string {
  const a = src.indexOf(start)
  const b = a < 0 ? -1 : src.indexOf(end, a)
  if (a < 0 || b < 0) throw new Error(`doc-chip parity: ${start} moved in DocumentsDrawer.tsx - re-point the lift`)
  return src.slice(a, b)
}

function liftDrawer(): Lifted {
  const src = fs.readFileSync(DRAWER, 'utf8').replace(/\r\n/g, '\n')
  const body = [
    slice(src, 'const factClass =', 'const subLabel ='),
    slice(src, 'const yearChip =', 'const factLine ='),   // yearChip, then yearClass
  ].join('\n')
  const js = ts.transpileModule(body, { compilerOptions: { target: ts.ScriptTarget.ES2019 } }).outputText
  // A stub t: the i18n key's last part, then '|' and the year it was given.
  const t = (key: string, p?: { year?: string }) => `${key.split('.').pop()}${p?.year ? `|${p.year}` : ''}`
  return vm.runInNewContext(`${js}
;({ factClass, yearChip, yearClass })`, { t }) as Lifted
}

function tone(cls: string): string {
  const s = STATE[cls]
  if (!s) throw new Error(`doc-chip parity: unknown drawer colour ${cls}`)
  return s
}

const cases: Case[] = JSON.parse(readApi('apps/scholarship/tests/fixtures/doc_chip_parity.json')).cases
const drawer = liftDrawer()

describe('document chip parity (today\'s web vs the shared fixture)', () => {
  test('the fixture is big enough to mean something', () => {
    expect(cases.length).toBeGreaterThanOrEqual(70)
  })

  test.each(cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const doc = c.doc as unknown as AdminApplicantDocument
    const web: Chip[] = documentFacts(doc).map((f) => ({
      key: f.key, status: f.status, state: tone(drawer.factClass(f.status)), kind: 'fact',
    }))
    const yc = drawer.yearChip(doc)
    if (yc) {
      const [key, value] = yc.text.split('|')
      web.push({ key, state: tone(drawer.yearClass(yc.status)), kind: 'year', value })
    }
    // The year chip's status word is the server's own (the web keeps the raw 'current' / 'off').
    const want = c.chips.map((ch) => (ch.kind === 'year' ? { key: ch.key, state: ch.state, kind: ch.kind, value: ch.value } : ch))
    expect(web).toEqual(want)
    expect(documentPill(doc)).toBe(c.pill)
  })
})
