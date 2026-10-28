/**
 * Tenant invoices and receipts: issuing, sending, voiding, recording payment, the issuer's
 * own settings, the rate card, and build hours.
 */
import { API_BASE, adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Tenant invoices and receipts (2026-09-14) ───────────────────────────────────────────────
// ⚠ Every money field is a STRING (the server never sends a float), and a string is truthy at
// '0.00' — compare through Number(), never `if (row.total_myr)`.

/** issued → sent → part_paid → paid, or void. Derived server-side from the receipts, never stored. */
export type InvoiceStatus = 'issued' | 'sent' | 'part_paid' | 'paid' | 'void'

export interface InvoiceLineRow {
  position: number
  /** 'infrastructure' | 'metered' | 'development' */
  category: string
  description: string
  /** Hours, development lines only. */
  quantity: string | null
  /** The BILLED hourly rate, so quantity x unit = amount. */
  unit_amount_myr: string | null
  amount_myr: string
}

export interface InvoiceReceiptRow {
  id: number
  number: string
  received_on: string
  amount_myr: string
  /** 'bank_transfer' | 'cheque' | 'other' */
  method: string
  reference: string
}

export interface InvoiceRow {
  id: number
  number: string
  organisation_id: number
  organisation: string
  period_month: string
  issued_on: string
  due_on: string
  status: InvoiceStatus
  currency: string
  subtotal_myr: string
  discount_pct: string
  discount_myr: string
  discount_reason: string
  total_myr: string
  amount_paid_myr: string
  balance_myr: string
  sent_at: string | null
  voided_at: string | null
  void_reason: string
  bill_to_name: string
  lines: InvoiceLineRow[]
  receipts: InvoiceReceiptRow[]
  // ── SUPER ONLY — absent from an org_admin payload, not blanked ──
  issued_by_email?: string
  override_reason?: string
  sent_by_email?: string
  sent_to?: string[]
  /** Where Send will deliver: the inboxes frozen on the invoice when it was issued. */
  bill_to_emails?: string[]
  voided_by_email?: string
  replaces_number?: string
}

export interface InvoiceProblem {
  code: string
  message: string
  /** True when a super may issue past it with a written reason. The monthly job never does. */
  overridable: boolean
}

export interface InvoiceReadiness {
  organisation_id: number
  organisation: string
  /** Lets the "fix this" link open THAT organisation's settings instead of a picker. */
  organisation_code: string
  problems: InvoiceProblem[]
}

export interface InvoicesPayload {
  invoices: InvoiceRow[]
  // ── SUPER ONLY ──
  month?: string
  issue_day?: number
  readiness?: InvoiceReadiness[]
}

export async function getInvoices(
  options?: ApiOptions & { month?: string }
): Promise<InvoicesPayload> {
  const q = options?.month ? `?month=${encodeURIComponent(options.month)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/billing/invoices/${q}`, options)
}

/** Issue ONE invoice. A refusal is a 409 whose `body.problems` lists every reason.
 *
 * `issued_on` BACK-DATES the printed issue date, and the due date with it (owner, 2026-10-28: July
 * must say 15 August). Left out, the server uses today — the ordinary case and what the monthly
 * job does. A bad date is a plain 400 with its own code, not a readiness refusal. */
export async function issueInvoice(
  data: {
    organisation_id: number; period_month: string; override_reason?: string; issued_on?: string
  },
  options?: ApiOptions
): Promise<InvoiceRow> {
  return adminMutate('/api/v1/admin/scholarship/billing/invoices/', 'POST', data, options)
}

export async function sendInvoice(id: number, options?: ApiOptions): Promise<InvoiceRow> {
  return adminMutate(`/api/v1/admin/scholarship/billing/invoices/${id}/send/`, 'POST', {}, options)
}

export async function voidInvoice(id: number, reason: string, options?: ApiOptions): Promise<InvoiceRow> {
  return adminMutate(`/api/v1/admin/scholarship/billing/invoices/${id}/void/`, 'POST', { reason }, options)
}

export async function recordInvoiceReceipt(
  id: number,
  data: { received_on: string; amount_myr: string; reference: string; method: string; note?: string },
  options?: ApiOptions
): Promise<InvoiceRow> {
  return adminMutate(`/api/v1/admin/scholarship/billing/invoices/${id}/receipt/`, 'POST', data, options)
}

/** An invoice or receipt PDF as a Blob. The route needs the auth header, so a plain link cannot
 *  fetch it — the page turns the Blob into a download. */
export async function fetchBillingPdf(
  kind: 'invoice' | 'receipt', id: number, options?: ApiOptions
): Promise<Blob> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/scholarship/billing/${kind}s/${id}/pdf/`, { headers })
  if (!res.ok) throw new Error(`PDF failed: ${res.status}`)
  return res.blob()
}

export interface InvoiceIssuerSettings {
  legal_name: string
  registration_no: string
  address: string
  email: string
  phone: string
  bank_name: string
  bank_account_name: string
  bank_account_no: string
  payment_terms_days: number
  /** Required fields still blank. Empty = invoices can be issued. */
  missing: string[]
}

export interface TenantBillingDetails {
  organisation_id: number
  organisation: string
  /** The code the server resolved. A save sends it back, so the two calls cannot disagree. */
  organisation_code: string
  bill_to_name: string
  address: string
  emails: string[]
  missing: string[]
}

/** ⚠ TWO CALLS, TWO SCOPES (2026-10-28). They were one endpoint on Billing & usage, grouped by the
 *  task (issuing) rather than by scope. Who is BILLING is one platform-wide row a super owns; who is
 *  BILLED is per-organisation and that organisation may edit its own. Keeping them in one call meant
 *  one fence deciding two different questions. */
export interface InvoiceIssuerPayload {
  issuer: InvoiceIssuerSettings
}

/** SUPER-ONLY. 403 for anyone else — it carries the platform's own bank account. */
export async function getInvoiceIssuer(options?: ApiOptions): Promise<InvoiceIssuerPayload> {
  return adminFetch('/api/v1/admin/scholarship/billing/issuer/', options)
}

export async function saveInvoiceIssuer(
  issuer: Partial<Omit<InvoiceIssuerSettings, 'missing'>>, options?: ApiOptions
): Promise<InvoiceIssuerPayload> {
  return adminMutate('/api/v1/admin/scholarship/billing/issuer/', 'POST', { issuer }, options)
}

/** One organisation's bill-to, named by CODE like the sibling Organisation → Settings tabs.
 *  A super may name any tenant; an org_admin only its own — anything else is a 404, the same
 *  answer as an organisation that does not exist. Omit the code and the server returns the sole
 *  tenant, or refuses with `organisation_required` and the list. */
export async function getOrgBillingDetails(
  code?: string, options?: ApiOptions
): Promise<TenantBillingDetails> {
  const q = code ? `?organisation=${encodeURIComponent(code)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/billing/bill-to/${q}`, options)
}

export async function saveOrgBillingDetails(
  data: { organisation: string; bill_to_name: string; address: string; emails: string[] },
  options?: ApiOptions
): Promise<TenantBillingDetails> {
  return adminMutate('/api/v1/admin/scholarship/billing/bill-to/', 'POST', data, options)
}

export interface BillingRateRow {
  id: number
  /** 'infrastructure' | 'metered' | 'development' */
  category: string
  /** 'margin_pct' | 'hourly_rate' */
  kind: string
  value: string
  effective_from: string
  updated_by_email: string
  note: string
}

export async function getBillingRates(options?: ApiOptions): Promise<{ rates: BillingRateRow[] }> {
  return adminFetch('/api/v1/admin/scholarship/billing/rates/', options)
}

/** ⚠ This never EDITS a rate. It writes a NEW effective-dated row, so setting a rate in
 *  September cannot re-price August. The history is the audit trail. */
export async function setBillingRate(
  data: { category: string; kind: string; value: string; effective_from?: string; note?: string },
  options?: ApiOptions
): Promise<BillingRateRow> {
  return adminMutate('/api/v1/admin/scholarship/billing/rates/', 'POST', data, options)
}

/** Record build hours against a tenant and a month. `basis` is required server-side — an hours
 *  figure with no stated reconstruction is not auditable. */
export async function recordBuildHours(
  orgId: number,
  data: { period_month: string; module: string; hours: string; basis: string },
  options?: ApiOptions
): Promise<{ id: number }> {
  return adminMutate(
    `/api/v1/admin/scholarship/billing/hours/${orgId}/`, 'POST', data, options)
}

