/**
 * @jest-environment jsdom
 *
 * Request #31 (BrightPath, 2026-10-08) — the reviewer sees where the IC says the student was born.
 *
 * ⚠ THE LINE IS THE SERVER'S. `birth_state.label` is read from the IC's place-of-birth code and
 * worded on the server (English, to keep `en.json` flat — TD-360; served on the ADMIN payload
 * only); the cockpit prints it beside the NRIC and never re-reads the number itself.
 *
 * ⚠ `meets_rule` IS RE-READ ON EVERY LOAD (request #31 review). The gate ran at submit, and an
 * unverified NRIC can be changed afterwards; when the CURRENT IC fails the intake's CURRENT rule
 * the QC panel shows the served warning on its accept floor — so the override box appears on
 * screen instead of the server's 400 arriving unexplained. Owner 2026-11-23: the header line no
 * longer turns into a red banner; it reads "Born: <state>" and the served `state` chip says it.
 */
import { fireEvent, screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
/** Access S1: a QC writer, as the server serves her (`can_qc` is the QC door's own key). */
const QC_WRITER = { can_write: true, can_cancel_decline: true, can_tranche: true, can_qc: true }

describe('the place of birth beside the NRIC (owner 2026-11-23: "Born: <state>", no banner)', () => {
  it('prints the state name alone in the case header', async () => {
    renderCockpit({ role: 'reviewer', stage: 'submitted', build: {
      birth_state: { kind: 'state', state: 'kuala_lumpur', code: '14', name: 'W.P. Kuala Lumpur',
                     label: 'Born in: W.P. Kuala Lumpur (IC code 14)', meets_rule: null, warning: '' },
    } })
    await loaded()
    // t() echoes the key in tests; the {state} value is what the owner reads
    expect(screen.getByTestId('birth-state').textContent).toBe('admin.scholarship.bornState')
  })

  it('prints a fail-closed reading just as plainly', async () => {
    renderCockpit({ role: 'reviewer', stage: 'submitted', build: {
      birth_state: { kind: 'abroad', state: null, code: '71',
                     label: 'Born outside Malaysia (IC code 71)', meets_rule: null, warning: '' },
    } })
    await loaded()
    expect(screen.getByTestId('birth-state').textContent).toBe('Born outside Malaysia (IC code 71)')
  })

  it("a failing IC reads the same plain line — no red banner; the chip says 'state'", async () => {
    renderCockpit({ role: 'reviewer', stage: 'submitted', build: { birth_state: FAILS, rejection_chip: 'state' } })
    await loaded()
    expect(screen.getByTestId('birth-state').textContent).toBe('admin.scholarship.bornState')
    expect(screen.queryByText(FAILS.warning)).toBeNull()
    expect(screen.getByTestId('rejection-chip').textContent).toBe('admin.scholarship.rejectionChip.state')
  })
})

/** A student whose IC was changed after the gate (the review's finding 1). */
const FAILS = {
  kind: 'state' as const, state: 'selangor', code: '10', name: 'Selangor',
  label: 'Born in: Selangor (IC code 10)',
  meets_rule: false,
  warning: "Born in: Selangor (IC code 10) — does not meet this intake's rule (Sabah)",
}

describe('the QC accept floor', () => {
  const FLOOR = 'admin.scholarship.qcDecision.gapFloor'
  const accept = () => screen.getByRole('button', { name: 'admin.scholarship.qcDecision.accept' })

  it('shows the floor and asks for a reason instead of sending the accept', async () => {
    const { api } = renderCockpit({ role: 'qc', writes: QC_WRITER, stage: 'awaiting_qc', build: {
      outcome: 'recommend', birth_state: FAILS } })
    await loaded()
    expect(screen.getByText(FLOOR, { exact: false })).toBeTruthy()
    fireEvent.click(accept())
    expect(screen.getByText('admin.scholarship.qcDecision.overrideTitle')).toBeTruthy()
    expect(api.recordQcDecision).not.toHaveBeenCalled()
  })

  it('stays out of the way when the intake has no rule', async () => {
    renderCockpit({ role: 'qc', writes: QC_WRITER, stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(screen.queryByText(FLOOR, { exact: false })).toBeNull()
  })
})
