/**
 * @jest-environment jsdom
 *
 * Two apply-form pickers now arrive on demand (apply gift clarity, 2026-10-05), paying for
 * `/scholarship/apply`'s first-load budget: the PISMP school-type picker and the matriculation
 * college list. The facts a later tidy-up could quietly undo:
 *   1. each still ARRIVES drawing what the static version drew (this file);
 *   2. a chunk that cannot be fetched says so in place (the two `.failure.test.tsx` files);
 *   3. the apply page does not go back to a STATIC import of either — the whole saving (jest
 *      cannot weigh it; `npm run bundle-budget` does).
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { readWeb } from '@/test/sourceGuard'
import { collegesForTrack } from '@/data/matric-colleges'
import LazyAliranPicker from './LazyAliranPicker'
import LazyMatricCollegePicker from './LazyMatricCollegePicker'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

it('the PISMP picker draws nothing mid-flight, then the school types, and reports a pick', async () => {
  const onChange = jest.fn()
  const { container } = render(<LazyAliranPicker alirans={['sk', 'sjkt']} value="" onChange={onChange} />)
  expect(container.innerHTML).toBe('')
  const group = await screen.findByRole('radiogroup')
  expect(group.querySelectorAll('[role="radio"]')).toHaveLength(2)
  fireEvent.click(screen.getByText('scholarship.apply.plan.aliran.sjkt'))
  expect(onChange).toHaveBeenCalledWith('sjkt')
})

it('the matric picker draws nothing mid-flight, then the colleges for the chosen track', async () => {
  const { container } = render(
    <LazyMatricCollegePicker track="kejuruteraan" value="" onChange={() => {}} placeholder="pick" />)
  expect(container.innerHTML).toBe('')
  const box = await screen.findByPlaceholderText('pick')
  const first = collegesForTrack('kejuruteraan')[0]
  fireEvent.focus(box)
  fireEvent.change(box, { target: { value: first.name } })
  expect(screen.getAllByText(first.name).length).toBeGreaterThan(0)
  expect(screen.queryByRole('alert')).toBeNull()
})

describe('the saving is the import line', () => {
  const page = readWeb('src/app/scholarship/apply/page.tsx',
    'the apply form — first-load JS of /scholarship/apply, which these boundaries pay for')

  it('the apply page reaches both only through their lazy boundaries', () => {
    expect(page).toContain("from '@/components/scholarship/LazyAliranPicker'")
    expect(page).toContain("from '@/components/scholarship/LazyMatricCollegePicker'")
    expect(page).not.toMatch(/from\s+'@\/components\/AliranPicker'/)
    expect(page).not.toMatch(/from\s+'@\/data\/matric-colleges'/)
  })

  it('each lazy module owns a LITERAL import() — a variable specifier emits no chunk', () => {
    const aliran = readWeb('src/components/scholarship/LazyAliranPicker.tsx', 'the lazy boundary')
    expect(aliran).toContain("import('@/components/AliranPicker')")
    expect(aliran).not.toMatch(/from\s+'@\/components\/AliranPicker'/)
    const matric = readWeb('src/components/scholarship/LazyMatricCollegePicker.tsx', 'the lazy boundary')
    expect(matric).toContain("import('@/data/matric-colleges')")
    expect(matric).not.toMatch(/from\s+'@\/data\/matric-colleges'/)
  })
})
