/**
 * Document chip standard S0: today's officer-drawer chips against the SHARED parity fixture.
 *
 * The api's `doc_chips.chips_for` / `pill_for` (halatuju_api/apps/scholarship/doc_chips.py) is checked
 * against the same file by `test_doc_chips.py`. This half runs TODAY's web: `documentFacts` /
 * `documentPill` (cockpitDocFacts.ts, which calls offerFacts.ts and higherResultsFacts.ts), and the
 * drawer's fallback `drawerChips` (docChipRow.tsx). So the server can only serve what the drawer draws today, or one side
 * goes red. Sprint 1+ moves the screens onto the served chips; this test then retires with them.
 */
import { documentPill } from '@/lib/cockpitDocFacts'
import type { AdminApplicantDocument } from '@/lib/admin-api'
import { readApi } from '@/test/apiSource'
// The drawer's FALLBACK drawing (today's functions, for a payload with no `chips`): deleted in Sprint 9.
import { drawerChips } from '../../app/admin/scholarship/[id]/view/docChipRow'

type Chip = { key: string; status?: string; state: string; kind: string; value?: string }
type Case = { name: string; doc: Record<string, unknown>; chips: Chip[]; pill: string }
const cases: Case[] = JSON.parse(readApi('apps/scholarship/tests/fixtures/doc_chip_parity.json')).cases

describe('document chip parity (today\'s web vs the shared fixture)', () => {
  test('the fixture is big enough to mean something', () => {
    expect(cases.length).toBeGreaterThanOrEqual(70)
  })

  test.each(cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const doc = c.doc as unknown as AdminApplicantDocument
    const web: Chip[] = drawerChips(doc).map((c) => (c.kind === 'year'
      ? { key: c.key, state: c.state, kind: 'year', value: String(c.value) }
      : c.kind === 'plain'
        ? { key: c.key, status: c.status, state: c.state, kind: 'plain', value: String(c.value) }
        : { key: c.key, status: c.status, state: c.state, kind: 'fact' }))
    // The year chip's status word is the server's own (the web keeps the raw 'current' / 'off').
    const want = c.chips.map((ch) => (ch.kind === 'year' ? { key: ch.key, state: ch.state, kind: ch.kind, value: ch.value } : ch))
    expect(web).toEqual(want)
    expect(documentPill(doc)).toBe(c.pill)   // today's web: no Problem pill (the server's 'problem' is the one change)
  })
})
