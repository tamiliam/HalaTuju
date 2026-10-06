/**
 * TD-352 — the cockpit's Close card offers exactly the reasons the api accepts, stage by stage.
 *
 * The rule (`closeOffer`) and its DRIFT half: the reasons-by-stage table is read from the api's
 * `closure.py`, so a change to what the server accepts turns this file red instead of leaving a
 * dropdown that answers `reason_not_allowed`.
 */
import {
  closeErrorKey, closeOffer, POST_AWARD_REASONS, POST_AWARD_STATUSES, PRE_AWARD_REASONS,
  PRE_AWARD_STATUSES,
} from '@/lib/closeOffer'
import { pyChoiceValues, pySeq, readApi } from '@/test/apiSource'

const sorted = (xs: readonly string[]) => [...xs].sort()

describe('closeOffer', () => {
  test.each(PRE_AWARD_STATUSES)('%s → shown, pre-award, stalled + withdrawn only', (status) => {
    expect(closeOffer(status, true)).toEqual({ show: true, preAward: true, reasons: ['stalled', 'withdrawn'] })
  })
  test('awarded → no Close card: the offer is always out and nothing releases it (TD-366)', () => {
    expect(closeOffer('awarded', true)).toEqual({ show: false, preAward: false, reasons: [] })
  })
  test.each(['active', 'maintenance'])('%s → shown, the post-award list plus stalled', (status) => {
    expect(closeOffer(status, true)).toEqual({
      show: true, preAward: false,
      reasons: ['graduated', 'completed', 'withdrawn', 'lapsed', 'terminated', 'stalled'],
    })
  })
  test.each(PRE_AWARD_STATUSES)('%s, viewer not super/org_admin → no Close card (the api answers 403)', (status) => {
    expect(closeOffer(status, false)).toEqual({ show: false, preAward: true, reasons: [] })
  })
  test.each(POST_AWARD_STATUSES)('%s, any writer → unchanged by the role', (status) => {
    expect(closeOffer(status, false)).toEqual(closeOffer(status, true))
  })
  test.each(['rejected', 'withdrawn', 'closed', 'expired', ''])('%s → no Close card', (status) => {
    expect(closeOffer(status, true).show).toBe(false)
    expect(closeOffer(status, true).reasons).toEqual([])
  })
})

describe('closeErrorKey', () => {
  test.each(['bad_reason', 'not_closeable', 'sponsorship_open'])(
    '%s has its own sentence', (code) => {
      expect(closeErrorKey(code)).toBe(`admin.closure.error.${code}`)
    })
  test('reason_not_allowed shares the bad-reason sentence (a stale tab; no new en.json weight)', () => {
    expect(closeErrorKey('reason_not_allowed')).toBe('admin.closure.error.bad_reason')
  })
  test.each([undefined, '', 'Not found', 'forbidden', 'constructor'])('%s → generic', (code) => {
    expect(closeErrorKey(code)).toBe('admin.closure.error.generic')
  })
})

describe('drift — closure.py holds the same table', () => {
  const src = readApi('apps/scholarship/closure.py')

  test('the stage sets', () => {
    expect(sorted(pySeq(src, 'PRE_AWARD_STATUSES'))).toEqual(sorted(PRE_AWARD_STATUSES))
    expect(sorted(pySeq(src, 'POST_AWARD_STATUSES'))).toEqual(sorted(POST_AWARD_STATUSES))
  })

  test('the reasons for each stage, in order', () => {
    expect(pySeq(src, 'PRE_AWARD_REASONS')).toEqual([...PRE_AWARD_REASONS])
    expect(pySeq(src, 'POST_AWARD_REASONS')).toEqual([...POST_AWARD_REASONS])
  })

  test('the two stages together are exactly the apply gate’s in-play set, and that is what closes', () => {
    expect(src).toMatch(/^CLOSEABLE_FROM = IN_PLAY_STATUSES$/m)
    const inPlay = pySeq(readApi('apps/scholarship/services/apply_gate.py'), 'IN_PLAY_STATUSES')
    expect(inPlay.length).toBeGreaterThanOrEqual(9)
    expect(sorted([...PRE_AWARD_STATUSES, ...POST_AWARD_STATUSES])).toEqual(sorted(inPlay))
  })

  test('every reason offered is a model closure reason, and every model reason is offered somewhere', () => {
    const model = pyChoiceValues(readApi('apps/scholarship/models/applications.py'), 'CLOSURE_REASONS')
    expect(model.length).toBeGreaterThanOrEqual(6)
    expect(sorted(POST_AWARD_REASONS)).toEqual(sorted(model))
    for (const r of PRE_AWARD_REASONS) expect(model).toContain(r)
  })

  test('every refusal code the api raises has a sentence of its own kind, never the generic one', () => {
    const raised = [...src.matchAll(/ClosureError\('([a-z_]+)'/g)].map((m) => m[1])
    expect(raised.length).toBeGreaterThanOrEqual(4)
    for (const code of new Set(raised)) expect(closeErrorKey(code)).not.toBe('admin.closure.error.generic')
  })
})
