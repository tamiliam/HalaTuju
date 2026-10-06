/**
 * @jest-environment jsdom
 *
 * The school list that cannot be fetched (TD-352, 2026-10-06): the field still works — what she
 * types is the value — and there are simply no suggestions. Nothing thrown, no alert. Its own
 * file because it needs a different hoisted mock of the same module.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import SchoolSelect from './SchoolSelect'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/data/secondary-schools', () => {
  throw new Error('ChunkLoadError: Loading chunk 5793 failed.')
})

function Field() {
  const [school, setSchool] = useState('')
  return <SchoolSelect value={school} onChange={setSchool} />
}

it('keeps the typed value and shows no suggestions', async () => {
  render(<Field />)
  const box = screen.getByRole('combobox') as HTMLInputElement
  fireEvent.focus(box)
  fireEvent.change(box, { target: { value: 'SMK Not Listed' } })
  await act(async () => { await Promise.resolve(); await Promise.resolve() })
  expect(box.value).toBe('SMK Not Listed')
  expect(screen.queryByRole('option')).toBeNull()
  expect(screen.queryByRole('listbox')).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
})
