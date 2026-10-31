/**
 * @jest-environment jsdom
 *
 * The institution combobox (Form 6 schools, matriculation colleges, the reviewer's university):
 *   1. a long form finds a short MOE name — "kolej tingkatan enam" finds "KTE ..." (owner,
 *      2026-10-31; the matching itself is lib/schoolSearch);
 *   2. two schools with the SAME name both render — the Form 6 list has 11 names used twice
 *      ("SMK CHUNG HUA" in Miri and in Sibu), and a key on the name alone let React drop one.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import InstitutionPicker from './InstitutionPicker'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const box = () => screen.getByRole('combobox') as HTMLInputElement
const rows = () => screen.queryAllByRole('option').map((li) => li.textContent)

it('finds a short MOE name by its long form', () => {
  render(<InstitutionPicker value="" onChange={() => {}} options={[
    { name: 'KTE PONTIAN', hint: 'Johor' },
    { name: 'SMK (P) JALAN IPOH', hint: 'Kuala Lumpur' },
    { name: 'KM Perak', hint: 'Perak' },
  ]} />)
  fireEvent.focus(box())
  fireEvent.change(box(), { target: { value: 'kolej tingkatan enam pontian' } })
  expect(rows()).toEqual(['KTE PONTIANJohor'])
  fireEvent.change(box(), { target: { value: 'kolej matrikulasi perak' } })
  expect(rows()).toEqual(['KM PerakPerak'])
  fireEvent.change(box(), { target: { value: 'jln ipoh' } })
  expect(rows()).toEqual(['SMK (P) JALAN IPOHKuala Lumpur'])
  fireEvent.change(box(), { target: { value: 'zzqxv' } })
  expect(rows()).toEqual([])
})

it('draws both of two schools that share a name', () => {
  const error = jest.spyOn(console, 'error').mockImplementation(() => {})
  render(<InstitutionPicker value="" onChange={() => {}} options={[
    { name: 'SMK CHUNG HUA', hint: 'Miri' },
    { name: 'SMK CHUNG HUA', hint: 'Sibu' },
  ]} />)
  fireEvent.focus(box())
  fireEvent.change(box(), { target: { value: 'chung hua' } })
  expect(rows()).toEqual(['SMK CHUNG HUAMiri', 'SMK CHUNG HUASibu'])
  // React reports a duplicate key on console.error; none may be raised.
  expect(error.mock.calls.filter((c) => String(c[0]).includes('same key'))).toEqual([])
  error.mockRestore()
})
