/**
 * THE DRIFT TEST for `adminApplicationDetail.ts` — named by its `drift-test:` marker.
 *
 * The front-end fixture and `halatuju_api/apps/scholarship/tests/factories.py` describe the SAME
 * funnel from two sides. A stage added, renamed or removed on the Python side and not here would
 * leave the cockpit tested against a state the product no longer reaches — which is exactly the
 * class of defect (BrightPath #24) both files were built to stop.
 *
 * ⚠ IT COMPARES THE STAGE **NAMES**, AND DELIBERATELY NOTHING ELSE. The two sides carry different
 * shapes — a Django row versus the serialiser's JSON — so a field-by-field comparison would be a
 * second mapping to maintain and would rot faster than the thing it guards. What must never drift
 * is the vocabulary: the stages, which of them have two roads, and where each terminal branch
 * leaves the main line. All three are read out of the Python source below.
 *
 * ⚠ IT READS SOURCE TEXT, which the house rule otherwise reserves for structural claims. This IS
 * one: the subject is a literal tuple in another language's source, and there is nothing to
 * render. If the file cannot be found the test FAILS rather than skipping — a drift guard that
 * quietly passes when it cannot see its subject is worse than no guard.
 */
import * as fs from 'fs'
import * as path from 'path'

import { BRANCHES, OUTCOME_STAGES, STAGES } from '@/test/adminApplicationDetail'

const FACTORY = path.resolve(
  __dirname, '..', '..', '..', 'halatuju_api', 'apps', 'scholarship', 'tests', 'factories.py')

/** CRLF collapsed on read: the authoring machine is Windows and the gate is Linux. */
const source = (): string => fs.readFileSync(FACTORY, 'utf8').replace(/\r\n?/g, '\n')

/** The quoted names inside the first `NAME = (...)` tuple, comments stripped. */
function pythonTuple(src: string, name: string): string[] {
  const at = src.indexOf(`\n${name} = (`)
  if (at < 0) throw new Error(`${name} is no longer a tuple in factories.py`)
  const open = src.indexOf('(', at)
  const close = src.indexOf('\n)', open)
  const body = src.slice(open, close).replace(/#[^\n]*/g, '')
  return (body.match(/'([a-z_]+)'/g) || []).map((q) => q.slice(1, -1))
}

/** The quoted names inside a `NAME = frozenset({...})` / `= {...}` literal. */
function pythonSet(src: string, name: string): string[] {
  const at = src.indexOf(`\n${name} = `)
  if (at < 0) throw new Error(`${name} is no longer defined in factories.py`)
  const open = src.indexOf('{', at)
  const close = src.indexOf('}', open)
  const body = src.slice(open, close).replace(/#[^\n]*/g, '')
  return (body.match(/'([a-z_]+)'/g) || []).map((q) => q.slice(1, -1))
}

describe('the fixture mirrors the backend factory', () => {
  it('can see the factory at all (the floor)', () => {
    // A path that resolved to nothing would make every assertion below vacuous.
    expect(fs.existsSync(FACTORY)).toBe(true)
    expect(source().length).toBeGreaterThan(5_000)
  })

  it('⚠ NAMES THE SAME STAGES, IN THE SAME ORDER', () => {
    expect(pythonTuple(source(), 'STAGES')).toEqual([...STAGES])
  })

  it('agrees about which stages have two roads to QC', () => {
    // `verdict_recorded` and `awaiting_qc`, and nothing else. A third would mean the funnel grew
    // a decision point the fixture cannot describe.
    expect(pythonSet(source(), 'OUTCOME_STAGES').sort())
      .toEqual([...OUTCOME_STAGES].sort())
  })

  it('agrees where each terminal branch leaves the main line', () => {
    // `rejected` comes off the decline road at AWAITING QC; `expired` never got past
    // `shortlisted`. Getting this wrong is how a rejected fixture acquires `recommended_at`.
    const src = source()
    const at = src.indexOf('\nBRANCHES = {')
    expect(at).toBeGreaterThan(-1)
    const body = src.slice(src.indexOf('{', at), src.indexOf('}', at))
    const pairs: Record<string, string> = {}
    for (const m of body.matchAll(/'([a-z_]+)'\s*:\s*'([a-z_]+)'/g)) pairs[m[1]] = m[2]
    expect(pairs).toEqual(BRANCHES)
  })
})
