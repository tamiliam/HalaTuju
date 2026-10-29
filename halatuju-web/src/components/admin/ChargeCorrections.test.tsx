/**
 * @jest-environment jsdom
 *
 * Correcting an earlier month on this month's bill (2026-10-29).
 *
 * The owner's rule: *"When we have overcharged or undercharged, this should be deducted or added
 * (or written off) in the following month."* August over-charged BrightPath by 5.5 hours — request
 * 10 billed 15.0 against 11.5 spent, request 14 billed 2.0 after we wrote *"none of it is
 * charged"* — RM126.50 at the billed hour. The sent invoice is never edited.
 *
 * Written from the harms:
 *
 *  * each correction keeps its OWN words, because the reason is printed on the customer's invoice
 *    and a netted figure is a number nobody can explain;
 *  * a credit shows a minus and an UNSIGNED amount — never "−RM-126.50";
 *  * a correction of nothing is refused on this side too: it would print a line saying we got
 *    something wrong by RM0.00;
 *  * the amount is a TEXT box, because a native number input follows the browser locale and a
 *    comma decimal would reach the server as something it refuses.
 */
import { fireEvent, render, within } from '@testing-library/react'
import { ChargeCorrections, correctionProblem } from './ChargeCorrections'
import type { BillingCharge, BillingCorrection } from '@/lib/admin-api'

const t = (k: string, vars?: Record<string, string>) => (vars ? `${k}:${Object.values(vars).join('|')}` : k)

function correction(over: Partial<BillingCorrection> = {}): BillingCorrection {
  return {
    id: 1, amount_myr: '-126.50', corrects_invoice: 'INV-2026-0001',
    reason: 'August: requests 10 and 14 billed the plan', set_by: 'super@x.com',
    ...over,
  }
}

function charge(corrections: BillingCorrection[] = []): BillingCharge {
  return {
    organisation_id: 1, organisation: 'BrightPath', lines: [],
    subtotal_myr: '856.75', discount_pct: '0.00', discount_myr: '0.00',
    discount_reason: '', discount_set_by: '',
    corrections,
    corrections_myr: corrections.length ? '-126.50' : null,
    charged_myr: '730.25', blocked: [],
  }
}

describe('what the form accepts', () => {
  it('refuses a correction of nothing', () => {
    expect(correctionProblem('0', 'x')).toBe('badAmount')
    expect(correctionProblem('0.00', 'x')).toBe('badAmount')
    expect(correctionProblem('-0.00', 'x')).toBe('badAmount')
  })

  it('refuses what is not an amount in ringgit and sen', () => {
    expect(correctionProblem('abc', 'x')).toBe('badAmount')
    expect(correctionProblem('1,50', 'x')).toBe('badAmount')
    expect(correctionProblem('12.345', 'x')).toBe('badAmount')
  })

  it('takes a credit and a charge', () => {
    expect(correctionProblem('-126.50', 'August over-charge')).toBe('')
    expect(correctionProblem('40.00', 'July under-charge')).toBe('')
  })

  it('insists on a reason, because the customer reads it', () => {
    expect(correctionProblem('-126.50', '   ')).toBe('reasonRequired')
  })

  it('names the empty box before the empty reason', () => {
    expect(correctionProblem('', '')).toBe('amountRequired')
  })
})

describe('the rows', () => {
  const noop = jest.fn()

  it('prints a credit with a minus, an unsigned amount and its reason', () => {
    const { container } = render(
      <ChargeCorrections charge={charge([correction()])} month="2026-09" t={t} busy={false}
        onRecord={noop} onRemove={noop} />)
    const row = within(container).getByTestId('correction-1')
    expect(within(row).getByText('admin.billing.charge.correctionCredit')).not.toBeNull()
    expect(row.textContent).toContain('INV-2026-0001')
    expect(row.textContent).toContain('requests 10 and 14')
    expect(row.textContent).toContain('−RM126.50')
    expect(row.textContent).not.toContain('-RM126.50')
  })

  it('prints an under-charge as a charge, with no minus', () => {
    const { container } = render(
      <ChargeCorrections month="2026-09" t={t} busy={false} onRecord={noop} onRemove={noop}
        charge={charge([correction({ amount_myr: '40.00', corrects_invoice: '',
          reason: 'July: two hours missed' })])} />)
    const row = within(container).getByTestId('correction-1')
    expect(within(row).getByText('admin.billing.charge.correctionCharge')).not.toBeNull()
    expect(row.textContent).toContain('RM40.00')
    expect(row.textContent).not.toContain('−')
  })

  it('keeps two corrections on two rows rather than netting them', () => {
    const { container } = render(
      <ChargeCorrections month="2026-09" t={t} busy={false} onRecord={noop} onRemove={noop}
        charge={charge([correction(), correction({ id: 2, amount_myr: '-23.00',
          reason: 'August: request 14 charged 2.0, we said none' })])} />)
    expect(within(container).getByTestId('correction-1')).not.toBeNull()
    expect(within(container).getByTestId('correction-2')).not.toBeNull()
  })

  it('a month with no correction shows no row', () => {
    const { container } = render(
      <ChargeCorrections charge={charge()} month="2026-09" t={t} busy={false}
        onRecord={noop} onRemove={noop} />)
    expect(within(container).queryByTestId('correction-1')).toBeNull()
  })
})

describe('recording and removing', () => {
  it('sends the amount and the reason for THIS month', () => {
    // ⚠ The month on screen is the month that CARRIES it, never the month that was wrong.
    const record = jest.fn()
    const { container } = render(
      <ChargeCorrections charge={charge()} month="2026-09" t={t} busy={false}
        onRecord={record} onRemove={jest.fn()} />)
    fireEvent.click(within(container).getByText('admin.billing.charge.addCorrection'))
    fireEvent.change(within(container).getByLabelText('admin.billing.charge.correctionAmount'),
      { target: { value: '-126.50' } })
    fireEvent.change(within(container).getByLabelText('admin.billing.charge.correctionReason'),
      { target: { value: 'August over-charge' } })
    fireEvent.click(within(container).getByText('admin.billing.charge.apply'))
    expect(record).toHaveBeenCalledWith(1, '-126.50', 'August over-charge')
  })

  it('will not send a correction with no reason, and says so', () => {
    const record = jest.fn()
    const { container } = render(
      <ChargeCorrections charge={charge()} month="2026-09" t={t} busy={false}
        onRecord={record} onRemove={jest.fn()} />)
    fireEvent.click(within(container).getByText('admin.billing.charge.addCorrection'))
    fireEvent.change(within(container).getByLabelText('admin.billing.charge.correctionAmount'),
      { target: { value: '-126.50' } })
    expect(within(container)
      .getByText('admin.billing.charge.correctionError.reasonRequired')).not.toBeNull()
    fireEvent.click(within(container).getByText('admin.billing.charge.apply'))
    expect(record).not.toHaveBeenCalled()
  })

  it('uses a text box, so a comma decimal cannot be typed by the browser', () => {
    const { container } = render(
      <ChargeCorrections charge={charge()} month="2026-09" t={t} busy={false}
        onRecord={jest.fn()} onRemove={jest.fn()} />)
    fireEvent.click(within(container).getByText('admin.billing.charge.addCorrection'))
    const box = within(container).getByLabelText('admin.billing.charge.correctionAmount')
    expect(box.getAttribute('type')).toBe('text')
  })

  it('removal passes the row id, and is offered on an existing row', () => {
    const remove = jest.fn()
    const { container } = render(
      <ChargeCorrections charge={charge([correction({ id: 7 })])} month="2026-09" t={t}
        busy={false} onRecord={jest.fn()} onRemove={remove} />)
    fireEvent.click(within(container).getByText('admin.billing.charge.correctionRemove'))
    expect(remove).toHaveBeenCalledWith(7)
  })

  it('offers nothing to press while the page is busy', () => {
    const { container } = render(
      <ChargeCorrections charge={charge([correction({ id: 7 })])} month="2026-09" t={t} busy
        onRecord={jest.fn()} onRemove={jest.fn()} />)
    const button = within(container).getByText('admin.billing.charge.correctionRemove')
    expect((button as HTMLButtonElement).disabled).toBe(true)
  })
})
