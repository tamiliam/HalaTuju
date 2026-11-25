/**
 * S4a review — the scholar file's sub-state buttons offer a move on `can_hold` exactly when the server's
 * `hold_is_money_move` (views_admin/base.py) calls it a money move; every other move on `can_set_substate`.
 *
 * DRIFT, both directions: the server's rule is read from source and pinned word for word, and the web's
 * `isHoldMoneyMove` is pinned over every pair of sub-states the server knows (`maintenance.SUBSTATES`).
 * A change on either side turns this file red instead of drawing a button the door refuses.
 */
import { isHoldMoneyMove, SUBSTATES } from '@/components/admin/ScholarControls'
import { pySeq, readApi } from '@/test/apiSource'

const SERVER_RULE = "return target == 'on_hold' or (current == 'on_hold' and target == 'on_track')"

function serverBody(): string {
  const src = readApi('apps/scholarship/views_admin/base.py')
  const at = src.indexOf('def hold_is_money_move(current, target):')
  expect(at).toBeGreaterThan(-1)
  const end = src.indexOf('\ndef ', at + 1)
  return src.slice(at, end === -1 ? undefined : end)
}

describe('hold money move: web offer = server door', () => {
  test('the server rule is the one the web mirrors (word for word)', () => {
    const body = serverBody()
    const returns = body.split('\n').map((l) => l.trim()).filter((l) => l.startsWith('return'))
    expect(returns).toEqual([SERVER_RULE])
  })

  test('the web knows the same sub-states as the server', () => {
    const server = pySeq(readApi('apps/scholarship/maintenance.py'), 'SUBSTATES')
    expect([...SUBSTATES].sort()).toEqual([...server].sort())
  })

  test('every pair: a money move only to on_hold, or from on_hold to on_track', () => {
    const states = [...SUBSTATES, null]
    for (const current of states) {
      for (const target of SUBSTATES) {
        const expected = target === 'on_hold' || (current === 'on_hold' && target === 'on_track')
        expect([current, target, isHoldMoneyMove(current, target)]).toEqual([current, target, expected])
      }
    }
    expect(isHoldMoneyMove('on_hold', 'probation')).toBe(false)
    expect(isHoldMoneyMove('on_hold', 'ready_to_close')).toBe(false)
    expect(isHoldMoneyMove('probation', 'on_track')).toBe(false)
  })
})
