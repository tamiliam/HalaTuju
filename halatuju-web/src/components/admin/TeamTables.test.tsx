/**
 * @jest-environment jsdom
 *
 * Sprint M1b (owner O4, O17): a group table's Remove. Live, or GREYED with the reason and the count in
 * its tip — never inline text. Their last group is accepted and asks for `to_no_group`.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import { RemoveControl } from './TeamTables'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))

const tip = (testId: string) => {
  const b = screen.getByTestId(testId).querySelector('button') as HTMLButtonElement
  return document.getElementById(b.getAttribute('aria-describedby')!)!.textContent
}

describe('RemoveControl', () => {
  it('a free Remove sends to_no_group false', () => {
    const onRemove = jest.fn()
    render(<RemoveControl remove={{ admins: null }} table="admins" onRemove={onRemove} />)
    fireEvent.click(screen.getByTestId('remove-from-admins'))
    expect(onRemove).toHaveBeenCalledWith(false)
  })

  it('their last group is accepted, and asks for to_no_group', () => {
    const onRemove = jest.fn()
    render(<RemoveControl remove={{ admins: 'last_table' }} table="admins" onRemove={onRemove} />)
    fireEvent.click(screen.getByTestId('remove-from-admins'))
    expect(onRemove).toHaveBeenCalledWith(true)
  })

  it('a served has_open_cases is greyed, the count in the tip', () => {
    const onRemove = jest.fn()
    render(<RemoveControl remove={{ reviewers: 'has_open_cases' }} table="reviewers" onRemove={onRemove}
      counts={{ open_cases: 4 }} />)
    expect(screen.queryByTestId('remove-from-reviewers')).toBeNull()
    expect(tip('remove-greyed-reviewers')).toBe('admin.refusal.has_open_cases.many {"n":"4"}')
    fireEvent.click(screen.getByTestId('remove-greyed-reviewers').querySelector('button')!)
    expect(onRemove).not.toHaveBeenCalled()
  })

  it('a refusal the server names is greyed in words; no inline hint is drawn', () => {
    const { container } = render(<RemoveControl remove={{ reviewers: 'mentors_only' }} table="reviewers" onRemove={jest.fn()} />)
    expect(tip('remove-greyed-reviewers')).toBe('admin.refusal.mentors_only')
    // The only visible text is the button's label; the reason sits in the sr-only tip.
    expect(container.textContent).toBe('admin.team.removeFrom.reviewersadmin.refusal.mentors_only')
    expect(container.querySelectorAll('.sr-only')).toHaveLength(1)
  })

  // M1b (O17, TD-606): the served code is the server's whole answer. A last group they may not leave reads
  // the refusal itself; `last_table` means No group is accepted.
  it('a served `not_arrived` or `has_open_cases` is greyed; `last_table` stays live', () => {
    const onRemove = jest.fn()
    const { rerender } = render(<RemoveControl remove={{ reviewers: 'not_arrived' }} table="reviewers"
      onRemove={onRemove} counts={{ open_cases: 2 }} />)
    expect(screen.queryByTestId('remove-from-reviewers')).toBeNull()
    expect(tip('remove-greyed-reviewers')).toBe('admin.refusal.not_arrived')
    fireEvent.click(screen.getByTestId('remove-greyed-reviewers').querySelector('button')!)
    expect(onRemove).not.toHaveBeenCalled()
    rerender(<RemoveControl remove={{ reviewers: 'last_table' }} table="reviewers" onRemove={onRemove}
      counts={{ open_cases: 2 }} />)
    fireEvent.click(screen.getByTestId('remove-from-reviewers'))
    expect(onRemove).toHaveBeenCalledWith(true)
  })

  it('an Admins Remove served `run_in_progress` is greyed with the run count in its tip', () => {
    render(<RemoveControl remove={{ admins: 'run_in_progress' }} table="admins" onRemove={jest.fn()}
      counts={{ runs_in_progress: 2 }} />)
    expect(screen.queryByTestId('remove-from-admins')).toBeNull()
    expect(tip('remove-greyed-admins')).toMatch(/^admin\.refusal\.run_in_progress/)
  })

  it('draws nothing for the lead\'s fixed Admins seat, or with no entry for the table', () => {
    const { container, rerender } = render(<RemoveControl remove={{ admins: 'lead_fixed' }} table="admins" onRemove={jest.fn()} />)
    expect(container.textContent).toBe('')
    rerender(<RemoveControl remove={{ admins: null }} table="reviewers" onRemove={jest.fn()} />)
    expect(container.textContent).toBe('')
  })
})
