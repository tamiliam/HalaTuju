/**
 * @jest-environment jsdom
 *
 * The apply form's Form 6 school picker loads its centre list on demand (TD-309 follow-up,
 * 2026-09-30). Three facts a later tidy-up could quietly undo:
 *   1. the picker still ARRIVES with the same options the static call drew — the centres for the
 *      chosen stream, name and state — and the chosen value (this file);
 *   2. a chunk that cannot be fetched says so IN PLACE — `LazyStpmSchoolPicker.failure.test.tsx`;
 *   3. the apply page does not go back to a STATIC import of `@/data/stpm-schools`, which is the
 *      whole saving on `/scholarship/apply` (jest cannot weigh it; `npm run bundle-budget` does).
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { readWeb } from '@/test/sourceGuard'
import { stpmSchoolsForStream } from '@/data/stpm-schools'
import LazyStpmSchoolPicker from './LazyStpmSchoolPicker'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

describe('the Form 6 school picker arrives on demand', () => {
  it('draws nothing mid-flight, then the picker with the stream\'s centres', async () => {
    const onChange = jest.fn()
    const { container } = render(
      <LazyStpmSchoolPicker stream="sains" value="" onChange={onChange} placeholder="pick" />)
    expect(container.innerHTML).toBe('')
    const box = await screen.findByPlaceholderText('pick')
    // The same list the page drew statically before: the Sains centres, by name.
    const first = stpmSchoolsForStream('sains')[0]
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: first.name } })
    expect(screen.getAllByText(first.name).length).toBeGreaterThan(0)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('a centre that offers only the OTHER stream is not offered', async () => {
    const onlySosial = stpmSchoolsForStream('sains_sosial')
      .find((s) => !s.streams.includes('Sains'))
    if (!onlySosial) throw new Error('the data holds no Sains-Sosial-only centre — rewrite this test')
    render(<LazyStpmSchoolPicker stream="sains" value="" onChange={() => {}} placeholder="pick" />)
    const box = await screen.findByPlaceholderText('pick')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: onlySosial.name } })
    expect(screen.queryByText(onlySosial.name)).toBeNull()
  })
})

describe('the saving is the import line', () => {
  it('the apply page reaches the centre list only through the LAZY boundary', () => {
    const page = readWeb('src/app/scholarship/apply/page.tsx',
      'the apply form — first-load JS of /scholarship/apply, which this boundary pays for')
    expect(page).toContain("from '@/components/scholarship/LazyStpmSchoolPicker'")
    expect(page).not.toMatch(/from\s+'@\/data\/stpm-schools'/)
  })

  it('the lazy module owns a LITERAL import() of the data — a variable specifier emits no chunk', () => {
    const lazy = readWeb('src/components/scholarship/LazyStpmSchoolPicker.tsx', 'the lazy boundary')
    expect(lazy).toContain("import('@/data/stpm-schools')")
    expect(lazy).not.toMatch(/from\s+'next\/dynamic'/)
    expect(lazy).not.toMatch(/from\s+'@\/data\/stpm-schools'/)
  })
})
