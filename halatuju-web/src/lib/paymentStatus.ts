// Payment-run status → pill classes (shared by the Payments landing + detail pages).
// `finance_checked` shares the amber "part-signed, still in flight" tone with `admin_signed` —
// both mean signatures are being collected and no money has moved.
export const statusPill = (s: string) =>
  s === 'completed' ? 'bg-green-100 text-green-700'
  : s === 'admin_signed' || s === 'finance_checked' ? 'bg-amber-100 text-amber-700'
  : s === 'cancelled' ? 'bg-gray-100 text-gray-500'
  : 'bg-blue-100 text-blue-700'   // draft

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


// ── Sign-off view model (Sprint 14) ───────────────────────────────────────────
// The run-detail page's conditional sign-off chain, as ONE pure decision so it can be tested
// without mounting the page (and so the three-state layout can't drift between the in-progress
// block and the completed block).
//
// IMPORTANT: `financeCheckRequired` is the SERVER's verdict for this organisation
// (payments.finance_check_required), read verbatim off the run payload. Nothing here re-derives
// it from the staff list — that would recreate the keep-in-sync pair docs/lessons.md warns about.

export interface SignOffRun {
  status: string
  finance_check_required: boolean
  finance_signed: unknown | null
  admin_signed: unknown | null
}

export interface SignOffView {
  /** Does this org's chain include the finance check? Drives the 3- vs 2-column layout. */
  needsFinance: boolean
  /** Render the finance column at all. False for a dormant org — no empty placeholder. */
  showFinanceColumn: boolean
  /** The approver must wait: maker signed, chain has a finance step, nobody has checked yet. */
  awaitingFinance: boolean
  /** Step number shown against the approver column (2 when dormant, 3 when armed). */
  approverStepNumber: 2 | 3
  /** Item editing + Cancel are admin/org_admin powers; finance reads and signs only. */
  canEditItems: boolean
  canCancel: boolean
  /** The COMPLETED block shows a third seal only when a finance signature was collected. */
  completedColumns: 2 | 3
}

export function signOffView(run: SignOffRun, viewerRole?: string): SignOffView {
  const isFinanceViewer = viewerRole === 'finance'
  const needsFinance = !!run.finance_check_required
  return {
    needsFinance,
    showFinanceColumn: needsFinance,
    awaitingFinance: needsFinance && run.status === 'admin_signed' && !run.finance_signed,
    approverStepNumber: needsFinance ? 3 : 2,
    canEditItems: run.status === 'draft' && !isFinanceViewer,
    canCancel: !isFinanceViewer,
    // Keyed on the SIGNATURE, never on finance_check_required: a historical run completed
    // before the role existed must render the original 2-card layout and imply no skipped step,
    // even if the org has since appointed a finance admin.
    completedColumns: run.finance_signed ? 3 : 2,
  }
}
