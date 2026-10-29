/**
 * Tenant invoices and receipts: issuing, sending, voiding, recording payment, the issuer's
 * own settings, the rate card, and build hours.
 */
import { API_BASE, adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Tenant invoices and receipts (2026-09-14) ───────────────────────────────────────────────
// ⚠ Every money field is a STRING (the server never sends a float), and a string is truthy at
// '0.00' — compare through Number(), never `if (row.total_myr)`.

/** issued → sent → payment_declared → part_paid → paid, or void. Derived server-side, never stored.
 *
 * ⚠ `payment_declared` is the TENANT'S WORD, not money. Nothing has been verified: the customer has
 * said it paid and nobody has looked at the bank yet. It sits nowhere near `paid` on purpose, and a
 * receipt always outranks it — see `has_open_payment_declaration` on the server. */
export type InvoiceStatus =
  'issued' | 'sent' | 'payment_declared' | 'part_paid' | 'paid' | 'void'

export interface InvoiceLineRow {
  position: number
  /** 'infrastructure' | 'metered' | 'development' */
  category: string
  description: string
  /**
   * One request listed UNDER a "Feature requests" group line. A sub-item carries its own hours
   * and no money — the group above it holds the whole group's amount — so the screen indents it
   * and leaves the rate and amount cells empty. Older invoices have no sub-items at all.
   */
  is_sub_item?: boolean
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
  /** When the receipt was emailed to the bill-to inboxes. ⚠ NULL means it was NOT sent — stated,
   *  never assumed. Receipts raised before 2026-10-29 are all null. */
  emailed_at?: string | null
  /** SUPER ONLY, like the invoice's `sent_to`: the tenant knows its own inboxes. */
  emailed_to?: string[]
}

/** The tenant's claim that it has paid — carried to BOTH audiences, and carrying no money.
 *
 * ⚠ There is no amount, by the owner's choice: the invoice already states it, and a tenant-typed
 * figure would only invite an argument about which number is right. No slip either. */
export interface InvoicePaymentDeclarationRow {
  id: number
  /** The date the tenant says the money left their account. */
  paid_on: string
  reference: string
  declared_at: string | null
  declared_by_email: string
  /** 'open' — nobody has looked yet; 'confirmed' — a receipt was raised; 'rejected' — not found. */
  state: 'open' | 'confirmed' | 'rejected'
  /** Why the owner could not match it. Shown to the tenant; empty unless rejected. */
  reject_reason: string
  /** The receipt raised on confirming, by number. Empty until then. */
  receipt_number: string
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
  /** Newest first. Older invoices, and any issued before 2026-10-29, have none. */
  payment_declarations: InvoicePaymentDeclarationRow[]
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

// ── Payment declarations (2026-10-29) ───────────────────────────────────────────────────────
// ⚠ A SEPARATE ROUTE from the invoice actions, because `declare` is the TENANT'S act and the
// action route is super-only. See the server's `AdminInvoiceDeclarationView` docstring.

/** THE TENANT says it has paid. Date and bank reference only — no amount, no slip. Creates no
 *  receipt and moves no money: the owner still has to look at the bank. */
export async function declarePayment(
  id: number, data: { paid_on: string; reference: string }, options?: ApiOptions
): Promise<InvoiceRow> {
  return adminMutate(
    `/api/v1/admin/scholarship/billing/invoices/${id}/declaration/declare/`, 'POST', data, options)
}

/** THE OWNER found the money: raises the receipt and closes the claim. `amount_myr` is required
 *  and comes from the bank statement; `received_on` and `reference` default to what the tenant
 *  declared, and either may be corrected here. */
export async function confirmPaymentDeclaration(
  id: number,
  data: { declaration_id: number; amount_myr: string; received_on?: string; reference?: string;
          method?: string; note?: string },
  options?: ApiOptions
): Promise<InvoiceRow> {
  return adminMutate(
    `/api/v1/admin/scholarship/billing/invoices/${id}/declaration/confirm/`, 'POST', data, options)
}

/** THE OWNER could not match it. The reason is required and is shown to the tenant. */
export async function rejectPaymentDeclaration(
  id: number, data: { declaration_id: number; reason: string }, options?: ApiOptions
): Promise<InvoiceRow> {
  return adminMutate(
    `/api/v1/admin/scholarship/billing/invoices/${id}/declaration/reject/`, 'POST', data, options)
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

