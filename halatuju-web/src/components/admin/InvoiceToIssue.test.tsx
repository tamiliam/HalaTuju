/**
 * @jest-environment jsdom
 *
 * The "To issue" panel (2026-10-28). Written from the two things that were impossible before it:
 *
 *  * July and August were UNREACHABLE. The screen only ever asked the server for its default month,
 *    so a month that had already slipped past could not be picked at all.
 *  * the issue date was always the day the button was pressed, so July's bill would have carried
 *    November's due date. The owner asked for the 15th of the following month.
 *
 * And from the harm each one can do: a stale date left over from the previous month, and a date the
 * server would refuse being sent anyway.
 */
import { fireEvent, render, within } from '@testing-library/react'
import InvoiceToIssue from './InvoiceToIssue'
import type { InvoicesPayload } from '@/lib/admin-api'

const t = (k: string, vars?: Record<string, string>) => (vars ? `${k}:${Object.values(vars).join('|')}` : k)

function payload(over: Partial<InvoicesPayload> = {}): InvoicesPayload {
  return {
    invoices: [],
    month: '2026-07',
    issue_day: 15,
    readiness: [{
      organisation_id: 1, organisation: 'BrightPath', organisation_code: 'brightpath', problems: [],
    }],
    ...over,
  }
}

// The real clock would make "is this date in the future?" depend on the day the suite runs.
beforeEach(() => {
  jest.useFakeTimers().setSystemTime(new Date(2026, 9, 28, 9, 0))
})
afterEach(() => {
  jest.useRealTimers()
})

function setup(over: Partial<InvoicesPayload> = {}, onIssue = jest.fn(), onMonth = jest.fn()) {
  const data = payload(over)
  const r = render(<InvoiceToIssue data={data} busy={false} t={t} onMonth={onMonth} onIssue={onIssue} />)
  return { ...r, onIssue, onMonth }
}

describe('picking the month', () => {
  it('offers every closed month and never the one still running', () => {
    const { container } = setup()
    const select = within(container).getByLabelText('admin.billing.invoice.monthLabel') as HTMLSelectElement
    const values = Array.from(select.options).map((o) => o.value)
    expect(values).toContain('2026-07')
    expect(values).toContain('2026-09')
    expect(values).not.toContain('2026-10')
    expect(select.value).toBe('2026-07')
  })

  it('asks the PARENT to reload, because the readiness list is the server\'s answer', () => {
    const { container, onMonth } = setup()
    fireEvent.change(within(container).getByLabelText('admin.billing.invoice.monthLabel'),
      { target: { value: '2026-08' } })
    // Not held locally: readiness for August is a different list of problems, and only the server
    // can compute it. A local month would show July's problems under August's heading.
    expect(onMonth).toHaveBeenCalledWith('2026-08')
  })

  it('keeps the server\'s month selectable even when it falls outside the offered window', () => {
    // A month older than the twelve offered must still be the shown value, or the select would
    // display one month while the cards below it describe another.
    const { container } = setup({ month: '2024-03' })
    const select = within(container).getByLabelText('admin.billing.invoice.monthLabel') as HTMLSelectElement
    expect(select.value).toBe('2024-03')
  })
})

describe('the issue date', () => {
  it('prefills the 15th of the month after the one being billed', () => {
    const { container } = setup()
    expect((within(container).getByTestId('issue-date') as HTMLInputElement).value).toBe('2026-08-15')
  })

  it('sends the typed date with the issue, not the day the button was pressed', () => {
    const { container, onIssue } = setup()
    fireEvent.click(within(container).getByText('admin.billing.invoice.issue'))
    expect(onIssue).toHaveBeenCalledWith(1, '2026-07', '', '2026-08-15')
  })

  it('an edited date is the one that travels, trimmed', () => {
    const { container, onIssue } = setup()
    fireEvent.change(within(container).getByTestId('issue-date'), { target: { value: ' 2026-08-20 ' } })
    fireEvent.click(within(container).getByText('admin.billing.invoice.issue'))
    expect(onIssue).toHaveBeenCalledWith(1, '2026-07', '', '2026-08-20')
  })

  it('refuses to offer Issue at all while the date is one the server would reject', () => {
    const { container, onIssue } = setup()
    // Inside the billed month: a bill cannot predate the thing it bills.
    fireEvent.change(within(container).getByTestId('issue-date'), { target: { value: '2026-07-31' } })
    expect(within(container).getByRole('alert').textContent)
      .toBe('admin.billing.invoice.issueDateBeforeMonthEnd')
    const button = within(container).getByText('admin.billing.invoice.issue') as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(button)
    expect(onIssue).not.toHaveBeenCalled()
  })

  it('CLEARING the box disables Issue instead of quietly meaning today', () => {
    // ⚠ The failure adversarial review found on 2026-10-28: blank reaches the service as
    // "today", so a July invoice would have been dated 28 October with a November due date —
    // frozen, and remediable only by a void. The panel exists to set a date on purpose.
    const { container, onIssue } = setup()
    fireEvent.change(within(container).getByTestId('issue-date'), { target: { value: '' } })
    expect(within(container).getByRole('alert').textContent)
      .toBe('admin.billing.invoice.issueDateRequired')
    const button = within(container).getByText('admin.billing.invoice.issue') as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(button)
    expect(onIssue).not.toHaveBeenCalled()
  })

  it('never offers a month whose natural date falls in a closed year', () => {
    const { container } = setup()
    const select = within(container).getByLabelText('admin.billing.invoice.monthLabel') as HTMLSelectElement
    const values = Array.from(select.options).map((o) => o.value)
    expect(values).toContain('2025-12')
    expect(values).not.toContain('2025-11')
  })

  it('shows the help sentence, naming the cut-off day, while the date is sound', () => {
    const { container } = setup()
    expect(within(container).queryByRole('alert')).toBeNull()
    expect(within(container).getByText('admin.billing.invoice.issueDateHelp:15')).toBeTruthy()
  })
})
