/**
 * @jest-environment jsdom
 *
 * Mobile M4: the apply form's School field loads its suggesting component lazily. If that chunk never
 * arrives, the field is still a working text field — same value, typed text kept (lessons.md: a lazy
 * piece needs an eager fallback).
 */
import { useState } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import LazySchoolSelect from './LazySchoolSelect'

jest.mock('@/components/SchoolSelect', () => { throw new Error('ChunkLoadError') })
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))

function Harness() {
  const [v, setV] = useState('SMK Contoh')
  return <><LazySchoolSelect value={v} onChange={setV} /><output data-testid="value">{v}</output></>
}

it('chunk failed: a plain field, her value shown, typing still updates the form', async () => {
  render(<Harness />)
  await new Promise((r) => setTimeout(r, 0))
  const input = screen.getByTestId('school-plain') as HTMLInputElement
  expect(input.value).toBe('SMK Contoh')
  expect(input.maxLength).toBe(255)
  fireEvent.change(input, { target: { value: 'SMK Taman Desa' } })
  expect(screen.getByTestId('value').textContent).toBe('SMK Taman Desa')
})
