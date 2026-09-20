/**
 * The officer's verdict and everything that judges it: the anomalies, the ledger, the facts,
 * the funding estimate, the query SLA, the QC gate, reopening, and the metrics.
 *
 * ⚠ FIVE SPANS of the old `admin-api.ts` (1276-1287, 1437-1461, 1466-1479, 1632-1708,
 * 1807-1853). `getScholarshipApplication` sat between the reopen calls and the case summary,
 * and belongs with the rest of the application reads in `./applications`.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { AdminScholarshipDetail } from './applications'

/** Verdict metrics summary returned by GET /verdict-metrics/. */
export interface VerdictMetrics {
  applications: number
  fact_decisions: number
  overrides: number
  override_rate: number
  per_fact: Record<string, { decided: number; overrides: number }>
  /** Which verdict_engine generations this roll-up averaged, {version: applications}.
   *  More than one key means the rate below BLENDS predictors — see the card. */
  engine_versions?: Record<string, number>
}

/** Reverse a recorded decision (super-only): holds the sponsor profile from the pool
 *  and unlocks the decision panel. `reason` is required (a reopen asserts a reviewer error). */
export async function reopenDecision(id: number, reason: string, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/reopen-decision/`, 'POST', { reason }, options)
}

/** Close a reopen with NO change — restore the profile to its prior published state. */
export async function cancelReopen(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/cancel-reopen/`, 'POST', {}, options)
}

/** QC gate on an AWAITING-QC ('interviewed') case: accept → recommended, or reopen → back to
 *  the reviewer at 'interviewing' (comments emailed to the assigned reviewer).
 *  override_reason: super-only pass of the V5 verdict gap floor — recorded server-side. */
export async function recordQcDecision(
  id: number,
  payload: { decision: 'accept' | 'reopen' | 'reject'; comments?: string; override_reason?: string },
  options?: ApiOptions,
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/qc-decision/`, 'POST', payload, options)
}

/** Check-2 case summary — the LLM briefing above the verdict checklist. `enabled:false` when the
 *  feature flag is off (dark); `summary:''` when every fact is Certain (nothing to brief). */
export interface VerdictCaseSummary {
  enabled: boolean
  summary?: string
  cached?: boolean
  model?: string
  error?: string
}
export async function getVerdictCaseSummary(id: number, options?: ApiOptions) {
  return adminFetch<VerdictCaseSummary>(
    `/api/v1/admin/scholarship/applications/${id}/verdict-summary/`, options)
}

/** S16 Phase A: deterministic pre-interview flag (anomaly engine). The `code`
 *  resolves to two i18n keys: `scholarship.admin.anomaly.{code}.fact` (the
 *  observed inconsistency, with `params` interpolated) and `.question` (the
 *  suggested interview question). */
export interface AdminAnomaly {
  code: string
  params: Record<string, string | number>
}

/** V3 (#9): a folded interview-agenda entry. kind: anomaly (pre-interview flag) ·
 *  open_query (a carried-over unanswered query, ask verbally) · needs_interview (a verdict
 *  amber that says "confirm at interview") · motivation (the standing Motivation & grit
 *  section; params.seeded=true when the statement of intent is thin). */
export interface AdminAgendaEntry {
  code: string
  kind: 'anomaly' | 'open_query' | 'needs_interview' | 'motivation'
  params: Record<string, string | number | boolean>
}

/** S1 verification verdict. One of four facts the coordinator AUDITS (does not
 *  assemble). Each evidence/unresolved item's `code` resolves to
 *  `admin.scholarship.verdict.item.{code}` in i18n (params interpolate).
 *  status: verified (green, AI asserts) · review (amber, confirm) ·
 *  recommend (blue, a human places the verdict) · gap (red, action needed). */
export interface AdminVerdictItem {
  // string[] supports the income reason codes' `members` list (e.g. ['father','brother']).
  code: string
  params: Record<string, string | number | string[]>
}
export interface AdminVerdictFact {
  fact: 'identity' | 'academic' | 'income' | 'pathway'
  status: 'verified' | 'review' | 'recommend' | 'gap'
  evidence: AdminVerdictItem[]
  unresolved: AdminVerdictItem[]
}

/** Check 2 STEP 1 — the deterministic submission review. */
export interface AdminLedgerRow {
  claim: string
  value: string
  source: string
  // verified (assert as fact) · reported (self-reported / under review) ·
  // student_words (their voice) · unverified (omit or hedge).
  verification: 'verified' | 'reported' | 'student_words' | 'unverified'
}
export interface AdminSubmissionReview {
  ledger: AdminLedgerRow[]
  completeness: Array<{ code: string }>
  consistency: AdminAnomaly[]
}

/** Check 2 — per-pathway funding-need estimate (RM [low, high]). */
export interface AdminFundingEstimate {
  pathway: string            // 'stpm' | 'matric' | 'asasi' | 'poly' | 'university' | 'pismp' | 'unknown'
  known: boolean             // false for an un-estimated/unknown pathway → fall back to self-report
  monthly: number            // est. RM monthly shortfall after govt allowance + PTPTN
  months: number | null      // typical (or student-stated) programme length
  total: number              // monthly × months, rounded to RM100 — the whole-programme need
  variable: boolean          // cost varies a lot by institution/field → show a caveat
  practical: boolean         // has an internship/practical term that may add travel
}

/** Check 2 STEP 2/3 — the query SLA clock for the cockpit. */
export interface AdminQuerySla {
  deadline: string | null
  lapsed: boolean
  open_count: number
  days_left: number | null
  ready_for_assignment: boolean
  // true when the app is proceeding to assignment WITH clarify queries still open
  // (the SLA lapsed) — the 'ready-with-open-queries' reviewer flag.
  proceeding_with_open_queries: boolean
  // V3 (#7): higher-priority clarify gaps crowded out by the cap right now (0 = none) — the
  // cockpit shows "N more queries waiting" so a capped-out query stays visible to the officer.
  clarify_overflow: number
}

// ── Sprint 5: Officer verdict + caveats ─────────────────────────────────────

export interface RecordVerdictPayload {
  officer_verdict: {
    identity?: string
    academic?: string
    income?: string
    pathway?: string
    overall?: string
  }
  reason?: string
  finalise?: boolean
  language?: string
}

export interface RecordVerdictResult extends AdminScholarshipDetail {
  finalise_result: { ok: boolean; code?: string } | null
}

/** Record the coordinator's verdict. May also trigger a final-profile
 *  generation when `finalise: true` is passed. */
export async function recordVerdict(
  id: number,
  payload: RecordVerdictPayload,
  options?: ApiOptions,
): Promise<RecordVerdictResult> {
  return adminMutate<RecordVerdictResult>(
    `/api/v1/admin/scholarship/applications/${id}/record-verdict/`,
    'POST',
    payload,
    options,
  )
}

/** Aggregate override-rate metrics for the verdict engine.
 *  `cohort` is optional; omit to get the cross-cohort totals. */
export async function getVerdictMetrics(
  options?: ApiOptions,
  cohort?: string,
): Promise<VerdictMetrics> {
  const qs = cohort ? `?cohort=${encodeURIComponent(cohort)}` : ''
  return adminFetch<VerdictMetrics>(
    `/api/v1/admin/scholarship/verdict-metrics/${qs}`,
    options,
  )
}

