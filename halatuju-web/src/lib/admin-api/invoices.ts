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

/** Issue ONE invoice. A refusal is a 409 whose `body.problems` lists every reason. */
export async function issueInvoice(
  data: { organisation_id: number; period_month: string; override_reason?: string },
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
  bill_to_name: string
  address: string
  emails: string[]
  missing: string[]
}

export interface InvoiceSettingsPayload {
  issuer: InvoiceIssuerSettings
  tenants: TenantBillingDetails[]
}

export async function getInvoiceSettings(options?: ApiOptions): Promise<InvoiceSettingsPayload> {
  return adminFetch('/api/v1/admin/scholarship/billing/invoice-settings/', options)
}

export async function saveInvoiceIssuer(
  issuer: Partial<Omit<InvoiceIssuerSettings, 'missing'>>, options?: ApiOptions
): Promise<InvoiceSettingsPayload> {
  return adminMutate('/api/v1/admin/scholarship/billing/invoice-settings/', 'POST', { issuer }, options)
}

export async function saveTenantBillingDetails(
  data: { organisation_id: number; bill_to_name: string; address: string; emails: string[] },
  options?: ApiOptions
): Promise<InvoiceSettingsPayload> {
  return adminMutate('/api/v1/admin/scholarship/billing/invoice-settings/', 'POST', data, options)
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

