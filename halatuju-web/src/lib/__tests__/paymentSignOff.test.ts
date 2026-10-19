// The conditional finance CHECK step, as seen by the run-detail page (Sprint 14).
//
// `signOffView` is the single decision behind the sign-off block, the completed seal cards and
// the finance viewer's read-only controls, so the three can never disagree about whether the
// chain has two steps or three. The rule it encodes is NOT re-derived here: the server sends
// `finance_check_required` and this reads it verbatim (docs/lessons.md — don't mirror a rule
// across the language boundary, carry the computed value).
import { signOffView, statusPill, type SignOffRun } from '../paymentStatus'

const SIG = { name: 'X', email: 'x@y.com', at: '2026-08-01T00:00:00Z' }

const run = (over: Partial<SignOffRun> = {}): SignOffRun => ({
  status: 'draft',
  finance_check_required: false,
  finance_signed: null,
  admin_signed: null,
  ...over,
})

describe('signOffView — dormant organisation (no finance admin)', () => {
  it('keeps the original two-column layout with no finance placeholder', () => {
    const v = signOffView(run({ status: 'admin_signed', admin_signed: SIG }))
    expect(v.needsFinance).toBe(false)
    expect(v.showFinanceColumn).toBe(false)
    expect(v.approverStepNumber).toBe(2)
  })

  it('never makes the approver wait', () => {
    expect(signOffView(run({ status: 'admin_signed', admin_signed: SIG })).awaitingFinance).toBe(false)
  })
})

describe('signOffView — armed organisation (active finance admin)', () => {
  const armed = (over: Partial<SignOffRun> = {}) => run({ finance_check_required: true, ...over })

  it('shows a third column and renumbers the approver step', () => {
    const v = signOffView(armed({ status: 'admin_signed', admin_signed: SIG }))
    expect(v.showFinanceColumn).toBe(true)
    expect(v.approverStepNumber).toBe(3)
  })

  it('makes the approver wait once the maker has signed and finance has not', () => {
    expect(signOffView(armed({ status: 'admin_signed', admin_signed: SIG })).awaitingFinance).toBe(true)
  })

  it('stops making the approver wait once finance has checked', () => {
    const v = signOffView(armed({ status: 'finance_checked', admin_signed: SIG, finance_signed: SIG }))
    expect(v.awaitingFinance).toBe(false)
  })

  it('does not make the approver wait while the run is still a draft', () => {
    expect(signOffView(armed({ status: 'draft' })).awaitingFinance).toBe(false)
  })
})

describe('signOffView — the completed seal cards', () => {
  it('renders three cards when a finance signature was collected', () => {
    const v = signOffView(run({ status: 'completed', finance_check_required: true,
                                admin_signed: SIG, finance_signed: SIG }))
    expect(v.completedColumns).toBe(3)
  })

  it('renders the historical two-card layout when the finance triple is empty', () => {
    // The load-bearing case: a run completed BEFORE the role existed, in an org that has since
    // appointed a finance admin. It must not imply a step was skipped, so this keys on the
    // signature rather than on finance_check_required.
    const v = signOffView(run({ status: 'completed', finance_check_required: true,
                                admin_signed: SIG, finance_signed: null }))
    expect(v.completedColumns).toBe(2)
  })
})

describe('signOffView — what the served fields allow (#39 Sprint 2)', () => {
  it('edits a draft and cancels only when the server says can_prepare', () => {
    const yes = signOffView(run({ status: 'draft', can_prepare: true }))
    expect([yes.canEditItems, yes.canCancel]).toEqual([true, true])
    // Finance APPROVES runs and is served can_prepare: false — no edit, no cancel.
    const no = signOffView(run({ status: 'draft', can_prepare: false }))
    expect([no.canEditItems, no.canCancel]).toEqual([false, false])
    // A payload from before the change carries no can_prepare: nothing is offered.
    expect(signOffView(run({ status: 'draft' })).canEditItems).toBe(false)
  })

  it('does not allow editing once signatures exist, for anyone', () => {
    expect(signOffView(run({ status: 'admin_signed', can_prepare: true })).canEditItems).toBe(false)
    expect(signOffView(run({ status: 'finance_checked', can_prepare: true })).canEditItems).toBe(false)
  })

  it('carries your_step verbatim, and null when absent', () => {
    expect(signOffView(run({ status: 'admin_signed', your_step: 'approve' })).yourStep).toBe('approve')
    expect(signOffView(run({ status: 'admin_signed' })).yourStep).toBeNull()
  })

  it('names the fallback only to the person whose step is the approval', () => {
    expect(signOffView(run({ status: 'admin_signed', your_step: 'approve', approver_fallback: true })).fallback)
      .toBe(true)
    expect(signOffView(run({ status: 'admin_signed', your_step: null, approver_fallback: true })).fallback)
      .toBe(false)
  })

  it('reads check_step_required first and the old key only when it is absent', () => {
    expect(signOffView(run({ finance_check_required: true, check_step_required: false })).needsFinance)
      .toBe(false)
    expect(signOffView(run({ finance_check_required: true })).needsFinance).toBe(true)
  })
})

describe('statusPill knows the new status', () => {
  it('gives finance_checked the same in-flight amber as admin_signed', () => {
    expect(statusPill('finance_checked')).toBe(statusPill('admin_signed'))
  })

  it('still distinguishes completed, cancelled and draft', () => {
    // Layer 1 F6 renamed the FAMILIES, not the meanings: green→positive, gray→ground, blue→info.
    // The values are Tailwind's own, so nothing a person sees moved in light mode.
    expect(statusPill('completed')).toContain('positive')
    expect(statusPill('cancelled')).toContain('ground')
    expect(statusPill('draft')).toContain('info')
    // A run mid-chain must never read as finished.
    expect(statusPill('finance_checked')).not.toBe(statusPill('completed'))
  })
})
