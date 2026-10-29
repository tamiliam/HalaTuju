/**
 * @jest-environment jsdom
 *
 * Recording what the work ACTUALLY took (2026-10-29).
 *
 * The owner audited all sixteen billed requests and found five wrong — 10, 14, 28, 30, 31 — because
 * billing read `quote_hours`, the PLAN, while the closing report had already published a different
 * number. Request 14's report said *"approximately 5 hours spent … None of it is charged"* and it
 * was billed 2.0.
 *
 * Written from the harms:
 *
 *  * a blank must SAY the invoice will refuse — silence is how the plan got billed unnoticed;
 *  * zero charged hours must be savable, because "none of it is charged" is a real answer;
 *  * a difference between spent and charged must carry a reason, in EITHER direction;
 *  * the boxes take text, not a native number input — a native one follows the browser locale and
 *    a comma decimal would reach the server as something it refuses.
 */
import { fireEvent, render, within } from '@testing-library/react'
import {
  RequestHoursForm, chargedDiffers, hoursFormProblem, hoursProblem,
} from './RequestHoursForm'
import type { OrgRequestAnalysis } from '@/lib/admin-api'

const t = (k: string, vars?: Record<string, string>) => (vars ? `${k}:${Object.values(vars).join('|')}` : k)

function analysis(over: Partial<OrgRequestAnalysis> = {}): OrgRequestAnalysis {
  return {
    id: 5, body: 'Planned 7 hours; it took about 4.', estimated_hours: '7.0',
    actual_hours: null, charged_hours: null, charge_note: '',
    cited_files: ['apps/scholarship/request_hours.py'], authored_by: 'claude-opus-5',
    repo_sha: 'a'.repeat(40), proposed_kind: '', proposed_lane: '',
    created_at: '2026-10-03T02:00:00Z', approved_at: '2026-10-03T03:00:00Z',
    approved_by_name: 'Super', superseded_at: null, is_current: true,
    ...over,
  }
}

describe('what the boxes accept', () => {
  it('takes zero, because "none of it is charged" is a real answer', () => {
    // ⚠ `org_requests._clean_hours` REFUSES zero, correctly — a quote of nothing is meaningless.
    // This is a REPORT, and a report of nothing is request 14, exactly.
    expect(hoursProblem('0', { required: true })).toBe('')
    expect(hoursProblem('0.0', { required: true })).toBe('')
  })

  it('refuses what the server would refuse', () => {
    expect(hoursProblem('abc', { required: true })).toBe('badHours')
    expect(hoursProblem('-1', { required: true })).toBe('badHours')
    expect(hoursProblem('4.25', { required: true })).toBe('badHours')   // one decimal place
    expect(hoursProblem('100001', { required: true })).toBe('badHours')
  })

  it('says the actual is required and the charged figure is not', () => {
    expect(hoursProblem('', { required: true })).toBe('hoursRequired')
    expect(hoursProblem('', { required: false })).toBe('')
  })

  it('asks for a reason whenever the two differ, in EITHER direction', () => {
    // Absorbed: request 14. Accepted extra: request 38. Both are real, both need saying.
    expect(hoursFormProblem('5.0', '0', '')).toBe('chargeNoteRequired')
    expect(hoursFormProblem('2.5', '4.0', '')).toBe('chargeNoteRequired')
    expect(hoursFormProblem('5.0', '0', 'Our overrun.')).toBe('')
  })

  it('does not demand a reason for a typing difference', () => {
    // '4' and '4.0' are the same figure. Compared as numbers, so nobody is asked to explain a
    // trailing zero.
    expect(hoursFormProblem('4.0', '4', '')).toBe('')
  })

  it('reports the empty actual before anything else', () => {
    expect(hoursFormProblem('', '4.0', '')).toBe('hoursRequired')
  })
})

describe('the panel', () => {
  const save = jest.fn()
  beforeEach(() => jest.clearAllMocks())

  it('says plainly that the invoice will refuse while nothing is recorded', () => {
    const { container } = render(
      <RequestHoursForm analysis={analysis()} t={t} busy={false} onSave={save} />)
    expect(within(container).getByText('admin.requests.owner.hoursMissing')).not.toBeNull()
  })

  it('shows both figures once they are recorded, with the reason', () => {
    const { container } = render(
      <RequestHoursForm t={t} busy={false} onSave={save}
        analysis={analysis({ actual_hours: '5.0', charged_hours: '0.0',
          charge_note: 'Our overrun, not theirs.' })} />)
    expect(within(container).getByText('admin.requests.owner.hoursRecorded:5.0|0.0')).not.toBeNull()
    expect(within(container).getByText('Our overrun, not theirs.')).not.toBeNull()
    expect(within(container).queryByText('admin.requests.owner.hoursMissing')).toBeNull()
  })

  it('sends the typed figures, and nothing it was not given', () => {
    const { container } = render(
      <RequestHoursForm analysis={analysis()} t={t} busy={false} onSave={save} />)
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursRecord'))
    fireEvent.change(within(container).getByLabelText('actual_hours'), { target: { value: '4.0' } })
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursSave'))
    // ⚠ `charged_hours` is left OUT, not sent as ''. The server defaults it to the actual, which
    // is the ordinary case; sending a blank would make it guess what the blank meant.
    expect(save).toHaveBeenCalledWith({ actual_hours: '4.0', charged_hours: undefined,
      charge_note: undefined })
  })

  it('will not save a difference with no reason, and says which rule it broke', () => {
    const { container } = render(
      <RequestHoursForm analysis={analysis()} t={t} busy={false} onSave={save} />)
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursRecord'))
    fireEvent.change(within(container).getByLabelText('actual_hours'), { target: { value: '5.0' } })
    fireEvent.change(within(container).getByLabelText('charged_hours'), { target: { value: '0' } })
    expect(within(container)
      .getByText('admin.requests.owner.hoursError.chargeNoteRequired')).not.toBeNull()
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursSave'))
    expect(save).not.toHaveBeenCalled()
  })

  it('saves a deliberate write-off once it is explained', () => {
    const { container } = render(
      <RequestHoursForm analysis={analysis()} t={t} busy={false} onSave={save} />)
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursRecord'))
    fireEvent.change(within(container).getByLabelText('actual_hours'), { target: { value: '5.0' } })
    fireEvent.change(within(container).getByLabelText('charged_hours'), { target: { value: '0' } })
    fireEvent.change(within(container).getByLabelText('charge_note'),
      { target: { value: 'Our overrun, not theirs.' } })
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursSave'))
    expect(save).toHaveBeenCalledWith({ actual_hours: '5.0', charged_hours: '0',
      charge_note: 'Our overrun, not theirs.' })
  })

  it('uses text boxes, so a comma decimal cannot be typed by the browser', () => {
    const { container } = render(
      <RequestHoursForm analysis={analysis()} t={t} busy={false} onSave={save} />)
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursRecord'))
    expect(within(container).getByLabelText('actual_hours').getAttribute('type')).toBe('text')
    expect(within(container).getByLabelText('charged_hours').getAttribute('type')).toBe('text')
  })

  it('offers nothing to press while the page is busy', () => {
    const { container } = render(
      <RequestHoursForm analysis={analysis()} t={t} busy onSave={save} />)
    const button = within(container).getByText('admin.requests.owner.hoursRecord')
    expect((button as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('a stale write-off note cannot survive the figures matching', () => {
  // ⚠ FOUND BY REVIEW, not by a failing test. The note box stayed on screen after the two
  // figures were made equal, so a write-off could be reversed with its explanation still
  // attached: "our overrun, absorbed in full" sitting on a request that was charged in full.
  it('a blank charged box means "the same as actual", not a difference', () => {
    expect(chargedDiffers('4.0', '')).toBe(false)
    expect(chargedDiffers('4.0', '4')).toBe(false)
    expect(chargedDiffers('4.0', '0')).toBe(true)
  })

  it('hides the note box while the figures match', () => {
    const { container } = render(
      <RequestHoursForm t={t} busy={false} onSave={jest.fn()}
        analysis={analysis({ actual_hours: '5.0', charged_hours: '0.0',
          charge_note: 'Our overrun, absorbed in full.' })} />)
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursEdit'))
    expect(within(container).getByLabelText('charge_note')).not.toBeNull()
    fireEvent.change(within(container).getByLabelText('charged_hours'), { target: { value: '5.0' } })
    expect(within(container).queryByLabelText('charge_note')).toBeNull()
  })

  it('does not send the old note once the figures match', () => {
    const save = jest.fn()
    const { container } = render(
      <RequestHoursForm t={t} busy={false} onSave={save}
        analysis={analysis({ actual_hours: '5.0', charged_hours: '0.0',
          charge_note: 'Our overrun, absorbed in full.' })} />)
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursEdit'))
    fireEvent.change(within(container).getByLabelText('charged_hours'), { target: { value: '5.0' } })
    fireEvent.click(within(container).getByText('admin.requests.owner.hoursSave'))
    expect(save).toHaveBeenCalledWith({ actual_hours: '5.0', charged_hours: '5.0',
      charge_note: undefined })
  })
})
