/**
 * Guardrail for the single status vocabulary (see
 * docs/plans/2026-07-14-status-vocabulary-and-stage-colours.md).
 *
 * The existing admin.scholarship i18n orphan test CANNOT catch label drift: `[id]/page.tsx`
 * contains the literal `` t(`admin.scholarship.statuses.${s}`) ``, so the whole `statuses.`
 * prefix is treated as dynamic and every key under it counts as "used" whether or not anything
 * reads it. These tests close that hole:
 *
 * 1. Label parity — every known status has a `statuses.<s>` key in en / ms / ta, and that block
 *    holds NO key that isn't a known status. This is the assertion that would have caught the
 *    original drift.
 * 2. Tone coverage — statusTone returns a non-default tone for every known status, so a new
 *    status added to the enum without a colour fails loudly instead of shipping grey.
 * 3. No regrowth — neither admin screen carries a local status→label or status→colour map, in the
 *    same spirit as no-icu-messageformat.test.ts's source scan.
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import {
  APPLICATION_STATUSES,
  SYNTHETIC_STATUSES,
  statusLabelKey,
  statusTone,
  hasStatusTone,
} from '@/lib/applicationStatus'
import { QC_ACCEPTED_STATES, isQcAccepted } from '@/lib/officerCockpit'

const ALL_STATUSES = [...APPLICATION_STATUSES, ...SYNTHETIC_STATUSES]
const DEFAULT_TONE = 'bg-ground-100 text-ground-600'

const statusesBlock = (m: {
  admin: { scholarship: { statuses: Record<string, string> } }
}) => m.admin.scholarship.statuses

describe('applicationStatus vocabulary', () => {
  test('statusLabelKey wraps the canonical prefix', () => {
    expect(statusLabelKey('profile_complete')).toBe('admin.scholarship.statuses.profile_complete')
  })

  describe.each([
    ['en', en],
    ['ms', ms],
    ['ta', ta],
  ])('%s labels', (_lang, messages) => {
    const block = statusesBlock(messages as never)

    test('every known status has a label', () => {
      const missing = ALL_STATUSES.filter((s) => !block[s])
      expect(missing).toEqual([])
    })

    test('no label for an unknown status', () => {
      const extra = Object.keys(block).filter((k) => ALL_STATUSES.indexOf(k) < 0)
      expect(extra).toEqual([])
    })
  })

  test('every known status has an explicit tone', () => {
    // Membership, not "differs from grey": the ended states (closed/withdrawn/expired) are
    // legitimately grey too, so a new status shipping the grey default is only caught here.
    const unmapped = ALL_STATUSES.filter((s) => !hasStatusTone(s))
    expect(unmapped).toEqual([])
  })

  test('statusTone falls back to a safe grey for an unknown status', () => {
    expect(statusTone('nonsense')).toBe(DEFAULT_TONE)
  })

  test('neither admin screen regrows a local status map', () => {
    const screens = [
      path.join(__dirname, '..', '..', 'app', 'admin', 'scholarship', 'page.tsx'),
      path.join(__dirname, '..', '..', 'app', 'admin', 'scholarship', '[id]', 'page.tsx'),
    ]
    const BANNED = /STATUS_LABELS|STATUS_TONE|statusBadge/
    const offenders = screens.filter((f) => BANNED.test(fs.readFileSync(f, 'utf8')))
    expect(offenders).toEqual([])
  })
})

/**
 * The `awarded` gap (2026-07-30). `awarded` was inserted in the MIDDLE of the lifecycle by the
 * post-award sprints, and three inline conditions in the cockpit listed the states either side
 * of it — so 47 of 143 production records showed a bare "recommended by …" with no tick and no
 * QC attribution. The records where money had already moved.
 */
describe('isQcAccepted', () => {
  it('includes every state after a QC has accepted — awarded above all', () => {
    for (const s of ['recommended', 'awarded', 'active', 'maintenance', 'closed']) {
      expect(isQcAccepted(s)).toBe(true)
    }
  })

  it('excludes everything before a QC decision, and the ended states', () => {
    // The negative half matters as much: if this returned true for `interviewed` the sign-off
    // would claim an acceptance that has not happened.
    for (const s of ['submitted', 'shortlisted', 'profile_complete', 'interviewing',
                     'interviewed', 'rejected', 'withdrawn', 'expired', 'reopened']) {
      expect(isQcAccepted(s)).toBe(false)
    }
  })

  it('agrees with the lifecycle order rather than a hand-written list', () => {
    // `awarded` sits between recommended and active. A set that contains both neighbours and
    // not the middle is the bug, so assert the contiguity directly.
    const i = (s: string) => QC_ACCEPTED_STATES.indexOf(s)
    expect(i('awarded')).toBeGreaterThan(i('recommended'))
    expect(i('awarded')).toBeLessThan(i('active'))
  })
})
