// Payment-run status → pill classes (shared by the Payments landing + detail pages).
// `finance_checked` shares the amber "part-signed, still in flight" tone with `admin_signed` —
// both mean signatures are being collected and no money has moved.
export const statusPill = (s: string) =>
  s === 'completed' ? 'bg-positive-100 text-positive-700'
  : s === 'admin_signed' || s === 'finance_checked' ? 'bg-caution-100 text-caution-700'
  : s === 'cancelled' ? 'bg-ground-100 text-ground-500'
  : 'bg-info-100 text-info-700'   // draft

// The month a run pays for, e.g. '2026-07-01' → 'Jul 2026'. Hand-formatted (deterministic,
// hydration-safe — never toLocaleDateString, whose locale differs on the server).
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTHS_FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                     'September', 'October', 'November', 'December']
export const monthLabel = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const [y, m] = iso.split('-')
  const i = Number(m) - 1
  return MONTHS[i] ? `${MONTHS[i]} ${y}` : iso
}
// Full form for prose (the sign-off declaration): '2026-07-01' → 'July 2026'.
export const monthLabelFull = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const [y, m] = iso.split('-')
  const i = Number(m) - 1
  return MONTHS_FULL[i] ? `${MONTHS_FULL[i]} ${y}` : iso
}


// ── Sign-off view model (Sprint 14; request #39 Sprint 2) ────────────────────
// The run-detail page's conditional sign-off chain, as ONE pure decision so it can be tested
// without mounting the page (and so the in-progress block and the completed block can't drift).
//
// IMPORTANT: every input is the SERVER's verdict, read verbatim off the run payload — whether the
// check step is armed (`check_step_required`, with the old `finance_check_required` key as the
// fallback for one release), the step THIS viewer may take now (`your_step`, from the same
// `payments.next_step_for` that `payments.sign` asks), whether the organisation admin approves
// under the fallback, and whether this viewer may edit or cancel (`can_prepare`). Nothing here
// re-derives a rule from a role or a staff list (docs/lessons.md: carry the computed value across
// the language boundary, never mirror the rule). Since #39 Sprint 2 Finance APPROVES runs.

export type PaymentStep = 'sign' | 'check' | 'approve'

export interface SignOffRun {
  status: string
  finance_check_required: boolean
  check_step_required?: boolean
  finance_signed: unknown | null
  admin_signed: unknown | null
  your_step?: PaymentStep | null
  approver_fallback?: boolean
  can_prepare?: boolean
}

export interface SignOffView {
  /** Is the check step armed for this run? Drives the 3- vs 2-column layout. */
  needsFinance: boolean
  /** Render the check column at all. False when unarmed — no empty placeholder. */
  showFinanceColumn: boolean
  /** The approver must wait: prepared, the check is armed, nobody has checked yet. */
  awaitingFinance: boolean
  /** Step number shown against the approver column (2 when unarmed, 3 when armed). */
  approverStepNumber: 2 | 3
  /** Item editing + Cancel: Prepare holders and the organisation admin (served `can_prepare`). */
  canEditItems: boolean
  canCancel: boolean
  /** The COMPLETED block shows a third seal only when a check signature was collected. */
  completedColumns: 2 | 3
  /** The step this viewer may take now, if any — the ONLY thing that draws a name box. */
  yourStep: PaymentStep | null
  /** Approving under the fallback: nobody else can, so the page says why the button is there. */
  fallback: boolean
}

export function signOffView(run: SignOffRun): SignOffView {
  const needsFinance = !!(run.check_step_required ?? run.finance_check_required)
  const yourStep = run.your_step ?? null
  return {
    needsFinance,
    showFinanceColumn: needsFinance,
    awaitingFinance: needsFinance && run.status === 'admin_signed' && !run.finance_signed,
    approverStepNumber: needsFinance ? 3 : 2,
    canEditItems: run.status === 'draft' && !!run.can_prepare,
    canCancel: !!run.can_prepare,
    // Keyed on the SIGNATURE, never on the check flag: a historical run completed before the
    // step existed must render the original 2-card layout and imply no skipped step.
    completedColumns: run.finance_signed ? 3 : 2,
    yourStep,
    fallback: yourStep === 'approve' && !!run.approver_fallback,
  }
}
