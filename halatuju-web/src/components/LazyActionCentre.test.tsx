/**
 * @jest-environment jsdom
 *
 * The Action Centre is its own chunk (student-help bundle trim, 2026-11-17): the wrapper draws
 * nothing while the chunk is in the air, then the real Action Centre with the same props; and the
 * two student surfaces that show it reach it ONLY through the wrapper, or its code and the
 * Documents slice of words go back into `/scholarship/application`'s first-load JS.
 */
import { readFileSync } from 'fs'
import { join } from 'path'
import { render, screen } from '@testing-library/react'
import LazyActionCentre from './LazyActionCentre'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/ActionCentre', () => ({
  __esModule: true,
  default: (p: { token: string | null; studentName?: string }) => <p>centre {p.token} {p.studentName}</p>,
}))

it('draws nothing at first, then the Action Centre with the props it was given', async () => {
  const { container } = render(<LazyActionCentre token="tok" studentName="Student" onConfirm={() => {}} />)
  expect(container.innerHTML).toBe('')
  expect(await screen.findByText('centre tok Student')).toBeTruthy()
  expect(screen.queryByRole('alert')).toBeNull()
})

it.each([
  'src/app/scholarship/application/page.tsx',
  'src/components/ScholarshipNextSteps.tsx',
])('%s reaches the Action Centre only through the wrapper', (file) => {
  const src = readFileSync(join(__dirname, '..', '..', file), 'utf8')
  expect(src).toContain("from '@/components/LazyActionCentre'")
  expect(src).not.toMatch(/from '@\/components\/ActionCentre'/)
})

it('the wrapper owns a literal import() of the Action Centre', () => {
  const src = readFileSync(join(__dirname, 'LazyActionCentre.tsx'), 'utf8')
  expect(src).toMatch(/import\((\/\* webpackChunkName: '[a-z]{2}' \*\/ )?'@\/components\/ActionCentre'\)/)
})
