/**
 * Guardrail (verification-model V5, audit #11): the FE `SOFT_EVIDENCE` denylist
 * (`officerCockpit.ts`) must mirror the SOFT evidence codes the backend verdict engine
 * emits. "Blue needs a green" — a fact backed only by soft signals must NOT read Probable
 * (blue); it drops to Unsure (amber). The denylist had rotted because nothing enforced the
 * mirror: Phase-2B/2C soft codes (`unemployment_epf_corroborated`, `household_size_confirm`)
 * were absent, so a tile carrying only those leaked to blue.
 *
 * This reads the backend `verdict_engine.py` and pins the mirror in BOTH directions:
 *   - every `_item('code', …)  # SOFT` code in the engine is in SOFT_EVIDENCE, and
 *   - every SOFT_EVIDENCE entry is a `# SOFT`-marked code in the engine.
 * Like `test_subject_drift.py`, it sanity-checks its own parse (a minimum count) so a
 * refactor that stops matching can't silently turn it into a 0-assert no-op.
 *
 * Convention: tag any soft evidence line in `_utility_context` / `_verdict_*` with a
 * trailing `# SOFT` comment. Jest runs in node (no jsdom); fs/path reads are fine.
 */
import * as fs from 'fs'
import * as path from 'path'

import { SOFT_EVIDENCE } from '@/lib/officerCockpit'

const ENGINE = path.join(
  __dirname, '..', '..', '..', '..',
  'halatuju_api', 'apps', 'scholarship', 'verdict_engine.py',
)

// A soft evidence line: `_item('code', …)` on a line whose trailing comment is `# SOFT`.
function softCodesFromEngine(): string[] {
  const src = fs.readFileSync(ENGINE, 'utf8')
  const codes: string[] = []
  src.split(/\r?\n/).forEach((line) => {
    if (!/#\s*SOFT\b/.test(line)) return
    const m = line.match(/_item\(\s*'([a-z0-9_]+)'/)
    if (m) codes.push(m[1])
  })
  return codes
}

describe('SOFT_EVIDENCE mirrors the backend # SOFT markers (blue needs a green)', () => {
  const engineSoft = softCodesFromEngine()

  test('the engine parse found the expected soft markers (parse sanity)', () => {
    // Guards against a silent 0-match no-op if the marker convention or _item shape changes.
    expect(engineSoft.length).toBeGreaterThanOrEqual(6)
  })

  test('every backend # SOFT code is in the FE SOFT_EVIDENCE denylist', () => {
    const missing = engineSoft.filter((c) => !SOFT_EVIDENCE.has(c))
    expect(missing).toEqual([])
  })

  test('every FE SOFT_EVIDENCE entry is a backend # SOFT code', () => {
    const engineSet = new Set(engineSoft)
    const orphan = [...SOFT_EVIDENCE].filter((c) => !engineSet.has(c))
    expect(orphan).toEqual([])
  })
})
