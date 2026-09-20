/**
 * Billing and usage v1: what a tenant used, what the platform paid for it, and the rate card
 * the two are reconciled through.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Billing & usage v1 (Sprint 13a) ──────────────────────────────────────────
export interface BillingServiceRow {
  service: string
  events: number
  quantity: number
  input_tokens: number
  output_tokens: number
  /** Which AI versions did this service's work. Empty for a non-AI service. */
  models: BillingModelRow[]
}

/** One AI version's share of a service. ⚠ Present ONLY on an AI service (gemini, openai); email,
 *  WhatsApp and Cloud Vision OCR record no model because they have none, so their `models` is an
 *  EMPTY LIST — never render that as "unknown". */
export interface BillingModelRow {
  model: string
  events: number
  input_tokens: number
  output_tokens: number
  /** Malaysian dates ('YYYY-MM-DD'), matching how the month itself is grouped. */
  first_seen: string | null
  last_seen: string | null
}

/** One AI job and the model it is SET TO — the upgrade checklist. ⚠ SUPER-ONLY: which model a job
 *  uses is a platform fact a tenant cannot change (owner, 2026-09-11). Resolved live on the
 *  server, never stored, so it cannot disagree with the engine. */
export interface AiJobRow {
  key: string
  label: string
  module: string
  /** Which shared door it goes through; two of them carry most of the platform. */
  seam: string
  provider: string
  /** 'setting' | 'cascade' | 'literal' — WHY the model is what it is. */
  source: string
  /** The setting name, cascade name, or the literal model itself. */
  source_name: string
  /** Written into the source: changing it needs a deploy, not a setting. */
  fixed: boolean
  model: string
  /** The rest of the cascade, in order. Never repeats `model`. */
  fallbacks: string[]
  /** The counsellor report alone falls through to a SECOND PROVIDER. Blank everywhere else. */
  fallback_provider: string
  fallback_model: string
}

export interface BillingOrgBlock {
  organisation_id: number | null
  organisation: string
  is_platform: boolean
  services: BillingServiceRow[]
  totals: { events: number; quantity: number; input_tokens: number; output_tokens: number }
  storage_bytes: number
}

export interface BillingUsagePayload {
  month: string
  months: string[]
  can_see_platform: boolean
  organisations: BillingOrgBlock[]
  /** SUPER-ONLY, absent for an org_admin: every AI job and the model it is set to. */
  ai_jobs?: AiJobRow[]
  /** SUPER-ONLY: every distinct model any job could reach today — the set an upgrade covers. */
  ai_models_in_use?: string[]
  /** BOTH audiences (2026-09-15): the shared services behind the numbers, with their plan only. */
  platform_services?: Array<{ key: string; plan: 'paid' | 'free' }>
}

/** The super/org_admin usage readout. 404s while BILLING_USAGE_ENABLED is off (dark ship) →
 * callers show a "coming soon" placeholder rather than the live card. `month` = 'YYYY-MM'. */
export async function getBillingUsage(
  options?: ApiOptions & { month?: string }
): Promise<BillingUsagePayload> {
  const q = options?.month ? `?month=${encodeURIComponent(options.month)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/billing/usage/${q}`, options)
}

// ── The COST side + the bill (2026-09-11) ───────────────────────────────────────
// SUPER-ONLY, every one of these. What the platform pays and what margin sits on top is a
// commercial disclosure; a 403 (not a 404) says so, because there is nothing to hide about the
// routes existing — only about their contents.
//
// ⚠ Every money figure crosses as a STRING. These are Decimals on the server and a JavaScript
// number cannot hold them without drifting — `0.1 + 0.2` is the reason invoices are not floats.
// Format for display; never do arithmetic on them here.

/** An invoice line we could not price, and why. Rendered, never swallowed: a category the reader
 *  can see is missing gets fixed, whereas a RM0.00 gets believed. */
export interface BillingBlockedLine {
  category: string
  reason: string
}

/** An invoice we hold but cannot yet state in ringgit — an unconverted foreign bill. It is
 *  COUNTED and named, never dropped, which is what makes the month's total honest about being a
 *  floor rather than a total. */
export interface BillingUnconverted {
  source: string
  invoice_ref: string
  currency: string
  amount_original: string | null
}

export interface PlatformCostBlock {
  lines: number
  total_myr: string | null
  /** The slice that moves with TENANT activity. June measured this at 23% of the GCP bill. */
  attributable_myr: string | null
  /** Ours: crons, CI, deploys. A platform fee, not a metered charge. */
  platform_myr: string | null
  /** What it costs to DELIVER HOURS (Claude). Held apart from `platform_myr` so it is never
   *  marked up as infrastructure — it is recovered through the hourly rate instead. */
  development_myr: string | null
  tax_myr: string | null
  by_source: Record<string, string | null>
  /** Which sources this month rest on a human reading a PDF. A WARNING. The owner's standing
   *  instruction (2026-09-11) is that nothing is typed by hand, so this should be empty. */
  entered_sources: string[]
  /** Sources parsed from the provider's own invoice by a parser that refuses unless its lines
   *  reconcile to the printed total. A NOTE, not a warning — reproducible by anyone holding
   *  the file, which is exactly what `entered` is not. */
  extracted_sources: string[]
  /** False = the total below is a FLOOR. See `unconverted`. */
  is_complete: boolean
  unconverted: BillingUnconverted[]
  /** Providers whose billing window is not the calendar month (Supabase bills the 8th–7th). */
  period_caveats: string[]
  metered_events: number
  metered_org_null: number
  metered_org_null_pct: number
}

export interface BillingChargeLine {
  category: string
  hours: string | null
  rate_myr: string | null
  margin_pct: string | null
  /** What WE paid for this slice, before the margin. Shown beside the charge so the markup is
   *  visible rather than baked into one unexplained figure. */
  cost_myr: string | null
  /** This tenant's share of a platform-wide cost. Null on the development line, which is
   *  already tenant-specific. */
  share_pct: string | null
  /** How that share was decided, in words — usage-weighted or split equally. */
  share_rule: string
  /** Development line only: what the TOOLS for these hours cost us (Claude). ⚠ Shown, never
   *  added — it is already recovered by the hourly rate, and adding it would take the same
   *  ringgit twice. It exists so "is the rate enough?" is a figure rather than a feeling. */
  tool_cost_myr?: string | null
  amount_myr: string | null
  detail: { module: string; hours: string | null; basis: string }[]
}

/** One tenant's bill for one month: shown in full, then discounted. The owner's July rule —
 *  *"we do not bill anything for July. 100% discount. But show the values."* */
export interface BillingCharge {
  organisation_id: number
  organisation: string
  lines: BillingChargeLine[]
  subtotal_myr: string | null
  discount_pct: string | null
  discount_myr: string | null
  discount_reason: string
  discount_set_by: string
  charged_myr: string | null
  blocked: BillingBlockedLine[]
}

/** Finished request work carrying quoted hours that has never reached an invoice. Reported, not
 *  auto-billed: a request has no completion date, so which MONTH it belongs to is a human call. */
export interface UnbilledRequest {
  request_id: number
  organisation_id: number
  organisation: string
  title: string
  hours: string | null
  /** Prefilled for the "record these hours" action, tag included. */
  module: string
  /** ⚠ WHEN WE WORKED, never when the request was raised (owner, 2026-09-11). On production the
   *  two differ: by raised date July carries 4 hours, by worked date it carries none. */
  worked_on: string
  worked_month: string
  /** 'scheduled' (the day the work was slotted in) or 'last touched' (weaker — any later edit
   *  moves it). Shown, so the reader knows how firm the month is. */
  worked_basis: string
}

export interface BillingCostsPayload {
  month: string
  /** Months the LEDGER holds rows for — never a generated range. A month with no rows is one
   *  nobody has entered, and offering it would read as "we paid nothing". */
  months: string[]
  costs: PlatformCostBlock
  charges: BillingCharge[]
  unbilled_requests: UnbilledRequest[]
}

export async function getBillingCosts(
  options?: ApiOptions & { month?: string }
): Promise<BillingCostsPayload> {
  const q = options?.month ? `?month=${encodeURIComponent(options.month)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/billing/costs/${q}`, options)
}

/** Record a discount against ONE organisation and ONE month. `reason` is required server-side. */
export async function setBillingAdjustment(
  data: { organisation_id: number; period_month: string; discount_pct: string; reason: string },
  options?: ApiOptions
): Promise<{ id: number }> {
  return adminMutate('/api/v1/admin/scholarship/billing/costs/', 'POST', data, options)
}

