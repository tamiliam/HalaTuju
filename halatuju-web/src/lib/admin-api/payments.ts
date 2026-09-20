/**
 * Monthly Vircle payment runs (P2): creating one, the per-student items, signing it off,
 * cancelling it, the CSV, and the funding summary the run is reconciled against.
 *
 * ⚠ `FundingSummaryRow` is the FINANCE ALLOWLIST — it may claim no field the api does not
 * send. drift-test: halatuju-web/src/lib/__tests__/financeAllowlistDrift.test.ts
 *
 * ⚠ THREE SPANS of the old `admin-api.ts` (2908-3001, 3013-3017, 3329-3391). The Overview and
 * spending screens were written between the payment TYPES and the payment ACTIONS; this is
 * the second domain the roadmap promised would come back together for free.
 */
import { API_BASE, adminFetch, adminMutate, giftQuery } from './client'
import type { ApiOptions } from './client'

// ── Payments module (P2): monthly Vircle payment runs ─────────────────────────
export interface PaymentRunSummary {
  id: number
  reference: string
  payment_date: string
  /** The month this run pays for (1st of month, ISO); dedup key — a student is paid once per month. */
  period_month: string | null
  status: 'draft' | 'admin_signed' | 'finance_checked' | 'completed' | 'cancelled'
  students: number
  total: string
  created_at: string
}
export interface PaymentRunItem {
  id: number
  application_id: number
  name: string
  nric: string
  vircle_id: string
  /** Advisory: has Vircle activated this eWallet? The fact is HARVESTED from the relay sheet into
   *  a stored column and served from there — an external data source, not a rule written twice.
   *  A false value shows a "not yet activated" chip; it never blocks, and the student stays
   *  payable regardless. */
  activated: boolean
  award_amount: string
  paid_to_date: string
  amount: string
  credit_applied: string
  included: boolean
  exclude_reason: string
}
export interface PaymentRunSkipped {
  application_id: number
  name: string
  nric: string
  reasons: string[]
}
export interface PaymentSignature { name: string; email: string; at: string }
export interface PaymentRunDetail {
  /** Where the payment instruction is emailed on countersignature (shown in the declaration). */
  vircle_email?: string
  id: number
  reference: string
  payment_date: string
  /** The month this run pays for (1st of month, ISO); dedup key — a student is paid once per month. */
  period_month: string | null
  status: 'draft' | 'admin_signed' | 'finance_checked' | 'completed' | 'cancelled'
  note: string
  drive_file_url: string
  created_by: string
  created_at: string
  admin_signed: PaymentSignature | null
  /** The middle CHECKER signature. Null on every run made before the finance role existed and
   *  on every run in an org with no active finance admin — render those as the 2-card layout. */
  finance_signed: PaymentSignature | null
  /** Whether THIS org's chain includes the finance check. Computed by the server
   *  (payments.finance_check_required) and read verbatim — NEVER re-derive it here from the
   *  staff list, or the activation rule becomes a keep-in-sync pair that drifts. */
  finance_check_required: boolean
  org_admin_signed: PaymentSignature | null
  items: PaymentRunItem[]
  skipped: PaymentRunSkipped[]
  students: number
  total: string
}

/** One student's line in the Payments funding summary. Mirrors the backend's
 *  FundingSummaryRowSerializer, which is an explicit allowlist — the only student data a
 *  `finance` admin can reach. Nothing identifying beyond the name, and no documents, income
 *  or verdicts.
 *  ⚠ ONE FIELD BEHIND: the api also sends `programme` (P2b — which gift funds this student) and
 *  this interface never gained it, so nothing renders it. Pinned, not fixed — adding a column to
 *  a live finance table is a visible change (TD-265).
 *  drift-test: halatuju-web/src/lib/__tests__/financeAllowlistDrift.test.ts */
export interface FundingSummaryRow {
  application_id: number
  name: string
  ref: string
  status: string
  pathway: string
  award_amount: string
  paid_to_date: string
  remaining: string
  vircle_id: string
  last_run: { reference: string; payment_date: string } | null
}
export interface FundingSummary {
  rows: FundingSummaryRow[]
  totals: { students: number; award_total: string; paid_total: string; remaining_total: string }
}
export async function getFundingSummary(programme?: string, options?: ApiOptions) {
  return adminFetch<FundingSummary>(
    `/api/v1/admin/scholarship/payments/funding-summary/${giftQuery(programme)}`, options)
}

export async function getPaymentRuns(programme?: string, options?: ApiOptions) {
  return adminFetch<{ runs: PaymentRunSummary[] }>(
    `/api/v1/admin/scholarship/payment-runs/${giftQuery(programme)}`, options)
}

/**
 * Create a DRAFT run. `programme_id` is **which gift the money comes from** (P2b).
 *
 * ⚠ REQUIRED POSITIONALLY, NULLABLE IN VALUE, and both halves are deliberate.
 *
 * Required, because P2a's lesson is that a new scoping dimension must not be sneakable — a
 * defaulted programme is the exact shape of the PF-1 routing bug. Every call site has to answer.
 *
 * Nullable, because absence here cannot produce a wrong answer. The server uses the org's only
 * active programme when there is exactly one, and **400 `programme_required` when there is more
 * than one — never a silent pick**. That is PF-1's own precedent for `programme_code`: the guard
 * is the server's refusal, not the signature. So `null` means "I am not choosing", which is
 * honest and safe, and is what the screen sends while BrightPath runs one gift.
 */
/**
 * Create a DRAFT run.
 *
 * ⚠ **THE GIFT IS A CODE FROM THE BREADCRUMB SINCE TD-241** (2026-09-11). It was
 * `programme_id`, taken from a picker ON the Payments page — and that picker was removed with
 * this change, because two controls answering "which gift" is two chances to create a run
 * against a gift you are not looking at, and the money moves either way.
 *
 * ⚠ STILL REQUIRED POSITIONALLY, STILL NULLABLE IN VALUE — P2a's rule, unchanged: a defaulted
 * programme is the shape of the PF-1 routing bug, so every call site has to answer. `undefined`
 * means the caller could not say, and the server then resolves the org's only gift or refuses
 * with `programme_required`.
 */
export async function createPaymentRun(
  payment_date: string, payment_month: string, programme: string | undefined,
  options?: ApiOptions,
) {
  return adminMutate<PaymentRunDetail>(
    `/api/v1/admin/scholarship/payment-runs/${giftQuery(programme)}`, 'POST',
    { payment_date, payment_month }, options)
}
export async function getPaymentRun(id: number, options?: ApiOptions) {
  return adminFetch<PaymentRunDetail>(`/api/v1/admin/scholarship/payment-runs/${id}/`, options)
}
export async function updatePaymentRunItem(
  runId: number, itemId: number,
  patch: { included?: boolean; exclude_reason?: string; amount?: string },
  options?: ApiOptions,
) {
  return adminMutate<PaymentRunDetail>(
    `/api/v1/admin/scholarship/payment-runs/${runId}/items/${itemId}/`, 'PATCH', patch, options)
}
export async function signPaymentRun(id: number, typed_name: string, options?: ApiOptions) {
  return adminMutate<PaymentRunDetail>(
    `/api/v1/admin/scholarship/payment-runs/${id}/sign/`, 'POST', { typed_name }, options)
}
export async function cancelPaymentRun(id: number, options?: ApiOptions) {
  return adminMutate<PaymentRunDetail>(
    `/api/v1/admin/scholarship/payment-runs/${id}/cancel/`, 'POST', {}, options)
}
/** Fetch the run CSV (auth header required) and return its text for a client-side download. */
export async function fetchPaymentRunCsv(id: number, options?: ApiOptions): Promise<string> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/scholarship/payment-runs/${id}/csv/`, { headers })
  if (!res.ok) throw new Error(`CSV download failed: ${res.status}`)
  return res.text()
}

