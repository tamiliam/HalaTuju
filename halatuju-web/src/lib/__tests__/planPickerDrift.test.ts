/**
 * DRIFT: the MARA division id the picker uses is the server's `MARA_DIVISION` (`views_offerings.py`).
 * The picker's rules are tested by behaviour in `planPicker.test.ts`.
 */
import { MARA_DIVISION_ID } from '@/lib/planPicker'
import { readApi } from '@/test/apiSource'

describe('the plan picker mirrors the server', () => {
  it('the MARA division id is the server MARA_DIVISION', () => {
    const src = readApi('apps/courses/views_offerings.py')
    expect(src).toMatch(new RegExp(`^MARA_DIVISION = '${MARA_DIVISION_ID}'`, 'm'))
  })
})
