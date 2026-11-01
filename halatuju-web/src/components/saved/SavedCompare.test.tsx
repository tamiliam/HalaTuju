/**
 * @jest-environment jsdom
 *
 * Mobile M3: saved-course compare on a phone (the owner's layout B) and the compare bar.
 */
import { fireEvent, render, screen, within } from '@testing-library/react'
import SavedCompareView, { CompareBar, type CompareData } from './SavedCompare'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k} ${Object.values(p).join(' ')}` : k) }),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href, className }: { children: unknown; href: string; className?: string }) =>
    <a href={href} className={className}>{children as never}</a>,
}))

const c = (id: string, name: string, fees: string, merit: string): CompareData => ({
  course_id: id, name, level: 'Diploma', field: 'Kejuruteraan', institution: `Inst ${id}`, state: 'Perak',
  type: 'Politeknik', fees, allowance: '—', merit, requirements: [`req ${id}`], semesters: '6', courseType: 'spm',
})
const THREE = [c('A', 'Course A', 'RM200', '72.4'), c('B', 'Course B', 'RM300', '80.1'), c('C', 'Course C', 'RM1,200', '92.0')]

const phone = () => screen.getByTestId('compare-phone')

describe('SavedCompareView on a phone (layout B)', () => {
  it('two columns: the first pick and the second; every row label is a heading over both values', () => {
    render(<SavedCompareView data={THREE.slice(0, 2)} loading={false} onBack={() => {}} />)
    const view = within(phone())
    expect(view.getByText('discovery.row.fees')).toBeTruthy()
    const feesRow = view.getByText('discovery.row.fees').closest('div') as HTMLElement
    expect(within(feesRow).getByText('RM200')).toBeTruthy()
    expect(within(feesRow).getByText('RM300')).toBeTruthy()
    // Two picks: no chooser.
    expect(view.queryByText('discovery.compareWith')).toBeNull()
  })

  it('with three picks, "Compare with" chooses the second column', () => {
    render(<SavedCompareView data={THREE} loading={false} onBack={() => {}} />)
    const view = within(phone())
    const feesRow = () => view.getByText('discovery.row.fees').closest('div') as HTMLElement
    expect(within(feesRow()).getByText('RM300')).toBeTruthy()
    expect(within(feesRow()).queryByText('RM1,200')).toBeNull()
    const chooseC = view.getByRole('button', { name: 'Course C' })
    expect(chooseC.getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(chooseC)
    expect(chooseC.getAttribute('aria-pressed')).toBe('true')
    expect(within(feesRow()).getByText('RM1,200')).toBeTruthy()
    expect(within(feesRow()).queryByText('RM300')).toBeNull()
    expect(within(feesRow()).getByText('RM200')).toBeTruthy()   // the first pick stays
  })

  it('marks nothing as "best" — which fee or merit is better is the student\'s call', () => {
    render(<SavedCompareView data={THREE} loading={false} onBack={() => {}} />)
    expect(document.body.textContent).not.toMatch(/best|terbaik|lowest|highest/i)
  })

  it('the back button is 44 px and returns', () => {
    const onBack = jest.fn()
    render(<SavedCompareView data={THREE} loading={false} onBack={onBack} />)
    const back = screen.getByRole('button', { name: /discovery.backToSaved/ })
    expect(back.className).toContain('min-h-11')
    fireEvent.click(back)
    expect(onBack).toHaveBeenCalled()
  })
})

describe('CompareBar', () => {
  it('draws nothing until a course is ticked', () => {
    const { container } = render(<CompareBar count={0} onCancel={() => {}} onCompare={() => {}} />)
    expect(container.innerHTML).toBe('')
  })

  it('one tick: the phone bar shows, Compare is off; two: Compare works', () => {
    const onCompare = jest.fn()
    const { rerender } = render(<CompareBar count={1} onCancel={() => {}} onCompare={onCompare} />)
    const bar = within(screen.getByTestId('compare-bar-phone'))
    expect(bar.getByText('discovery.selectedCount 1')).toBeTruthy()
    expect((bar.getByRole('button', { name: 'discovery.compare' }) as HTMLButtonElement).disabled).toBe(true)
    rerender(<CompareBar count={2} onCancel={() => {}} onCompare={onCompare} />)
    const bar2 = within(screen.getByTestId('compare-bar-phone'))
    fireEvent.click(bar2.getByRole('button', { name: 'discovery.compare' }))
    expect(onCompare).toHaveBeenCalled()
  })
})
