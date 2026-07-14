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

const ALL_STATUSES = [...APPLICATION_STATUSES, ...SYNTHETIC_STATUSES]
const DEFAULT_TONE = 'bg-gray-100 text-gray-600'

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
