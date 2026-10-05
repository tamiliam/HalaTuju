/**
 * @jest-environment jsdom
 *
 * Request #26 — the postcode table loads on demand, so its answer is LATE. Second review E: a late
 * answer is applied only if nothing moved since it was asked (a newer postcode, or a City/State the
 * student edited, or Cancel).
 */
import { renderHook } from '@testing-library/react'
import { usePostcodeAutofill } from '@/lib/usePostcodeAutofill'

jest.mock('malaysia-postcodes', () => ({
  findPostcode: (p: string) => (p === '08000'
    ? { found: true, city: 'Sungai Petani', state: 'Kedah' } : { found: false }),
}))

const hook = () => {
  const apply = jest.fn()
  const { result } = renderHook(() => usePostcodeAutofill(apply))
  return { apply, autofill: result.current }
}

it('fills City and State from a five-digit postcode', async () => {
  const { apply, autofill } = hook()
  await autofill.lookup('08000')
  expect(apply).toHaveBeenCalledWith('Sungai Petani', 'Kedah')
})

it('does not look anything up before the fifth digit', async () => {
  const { apply, autofill } = hook()
  await autofill.lookup('0800')
  expect(apply).not.toHaveBeenCalled()
})

it('drops a late answer once the student has edited City or State', async () => {
  const { apply, autofill } = hook()
  const pending = autofill.lookup('08000')
  autofill.edited()
  await pending
  expect(apply).not.toHaveBeenCalled()
})

it('drops a late answer once the postcode box has moved on', async () => {
  const { apply, autofill } = hook()
  const pending = autofill.lookup('08000')
  await autofill.lookup('0800')
  await pending
  expect(apply).not.toHaveBeenCalled()
})
