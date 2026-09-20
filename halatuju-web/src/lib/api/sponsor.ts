/**
 * The sponsor's own portal (Phase E): self-registration, terms, referrals, the pool, their
 * students, the wallet, impact, activity, the community, statements, trust and standing gift.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'

// ── Phase E: sponsor account (self-registration + own status) ──
export interface SponsorAccount {
  registered?: false                 // present + false when the user hasn't registered
  id?: number
  name?: string
  email?: string
  phone?: string
  source?: string
  organisation?: string
  status?: 'pending' | 'approved' | 'rejected' | 'suspended'
  is_approved?: boolean
  profile_complete?: boolean         // false until phone + source + PDPA consent are set
  notify_frequency?: 'realtime' | 'weekly' | 'off'   // F3: email-update cadence
  created_at?: string
  /** Where this sponsor stands with the current terms. The RULE lives on the server — the screen
   *  only reads `needs_terms`, and never computes it. */
  terms?: {
    terms_version: string
    terms_accepted: boolean
    /** True only when a version is active, this sponsor has no row for it, AND the platform flag
     *  is on. Grandfathering is a pre-written row, not a special case here. */
    needs_terms: boolean
    terms_basis: '' | 'accepted' | 'grandfathered'
  }
}

export interface SponsorTermsDocument {
  version: string
  locale_used: string
  title: string
  intro: string
  sections: Array<{ order: number; heading: string; body: string; has_quiz: boolean }>
}

export interface SponsorTermsCheckpoint {
  order: number
  tag: string
  plain: string
  question: string
  options: string[]
  correct: number
  why: string
}

/** The active terms plus where this sponsor stands. Readable at ANY time — being able to re-read
 *  what you agreed to is half of what this feature is for. */
export async function getSponsorTerms(locale = 'en', options?: ApiOptions): Promise<{
  terms: SponsorTermsDocument | null
  state: NonNullable<SponsorAccount['terms']>
  signed_name: string
  accepted_at: string | null
}> {
  return apiRequest(`/api/v1/sponsor/terms/?locale=${encodeURIComponent(locale)}`, options)
}

export async function getSponsorTermsQuiz(locale = 'en', options?: ApiOptions): Promise<{
  version: string
  checkpoints: SponsorTermsCheckpoint[]
}> {
  return apiRequest(`/api/v1/sponsor/terms/quiz/?locale=${encodeURIComponent(locale)}`, options)
}

/** Typing a name IS the signature. A 409 means the version changed while they were reading — the
 *  caller must re-fetch and re-take rather than record an acceptance of unseen wording. */
export async function acceptSponsorTerms(
  body: { version: string; signed_name: string; locale?: string },
  options?: ApiOptions,
): Promise<SponsorAccount> {
  return apiRequest('/api/v1/sponsor/terms/accept/', {
    method: 'POST',
    body: JSON.stringify(body),
    ...options,
  })
}

export async function getSponsorMe(options?: ApiOptions): Promise<SponsorAccount> {
  return apiRequest('/api/v1/sponsor/me/', options)
}

/** F3: set how often the sponsor is emailed about newly-published students. */
export async function patchSponsorNotifications(
  notify_frequency: 'realtime' | 'weekly' | 'off',
  options?: ApiOptions
): Promise<SponsorAccount> {
  return apiRequest('/api/v1/sponsor/notifications/', {
    method: 'PATCH',
    body: JSON.stringify({ notify_frequency }),
    ...options,
  })
}

export async function registerSponsor(
  payload: { name: string; phone: string; source: string; consent: boolean; organisation?: string; note?: string; ref?: string },
  options?: ApiOptions
): Promise<SponsorAccount> {
  return apiRequest('/api/v1/sponsor/register/', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...options,
  })
}

// F4 — sponsor referral / invitation (the inviter's own invites).
export interface SponsorReferral {
  id: number
  invitee_email: string
  invitee_name: string
  note: string
  code: string
  status: 'invited' | 'joined' | 'expired'
  created_at: string
  joined_at: string | null
}

/** F4 — the sponsor's own invitations (latest first). Approved sponsors only. */
export async function getSponsorReferrals(options?: ApiOptions): Promise<{ referrals: SponsorReferral[] }> {
  return apiRequest('/api/v1/sponsor/referrals/', options)
}

/** Invite a prospective sponsor. 400 `bad_email`; a duplicate pending invite to the
 *  same email is idempotent (no second email). */
export async function createSponsorReferral(
  body: { invitee_email: string; invitee_name?: string; note?: string },
  options?: ApiOptions,
): Promise<SponsorReferral> {
  return apiRequest('/api/v1/sponsor/referrals/', {
    ...options, method: 'POST', body: JSON.stringify(body),
  })
}

// Phase E2 — anonymised sponsor pool. The card holds ONLY non-identifying fields
// (the backend allowlist serializer guarantees no name/NRIC/address/phone/email).
export interface SponsorPoolCard {
  id: number          // opaque key to fetch the detail; not identifying
  ref: string         // human alias, e.g. "S-A3F9C1"
  state: string
  school: string      // the SECONDARY school attended (owner 2026-07-18) — '' when unknown
  field: string
  course: string      // confirmed programme name (e.g. "Diploma Kejuruteraan Mekanikal")
  // Path to that programme's public HalaTuju page ('/course/<id>' | '/stpm/<id>' | '/pathway/…'),
  // or '' when it has none — then the name renders as plain text. Server-computed
  // (card_display.course_href) so the FE never re-derives the rule. Non-identifying: a course page
  // is shared by every student on that programme.
  course_href: string
  academic: string
  institution: string // TARGET university — '' when unknown (card shows course only)
  blurb: string       // ≤20-word card-strict one-liner — '' when none
  funding_categories: string[]
  programme_months: number | null
  award_amount: string | null   // E3: admin-set; non-identifying
  funded_amount: string | null  // raised so far (sum of holding sponsorships); '0' until partial funding ships → drives the funding bar
  funded: boolean               // just-funded grace-window card: bar full, no fund button (read-only)
  // My-students single lifecycle badge (post-acceptance); null on a discovery card. 'Awaiting
  // acceptance' is derived separately from the sponsorship 'offered' status.
  portfolio_status: 'discontinued' | 'graduated' | 'paused' | 'semester_completed' | 'needs_attention' | 'on_track' | null
  supported_semesters: number | null   // how many semesters the bursary funds (owner-set or heuristic)
  // F2: coarse, non-identifying progress band — null until the student is sponsored.
  progress_state: 'on_track' | 'semester_completed' | 'needs_attention' | 'graduated' | null
  // S5: coarse operational signal, distinct from the academic band — 'paused' (on hold)
  // or 'completing' (wrapping up). null in good standing; probation is never surfaced.
  support_status: 'paused' | 'completing' | null
  // R5: a bare boolean — an independent party confirmed enrolment with the institution.
  enrolment_verified: boolean
  // Redesign: catalogue field artwork slug ('' → frontend uses the generic image).
  field_image_slug: string
  // Redesign: course-start date (ISO, date-only) → the "starts in N days" countdown; null when unset.
  reporting_date: string | null
}

export interface SponsorPoolDetail extends SponsorPoolCard {
  anon_profile: string  // generated anonymous blurb (markdown)
}

/** Browse the anonymised student pool (approved sponsor only). When the pool flag
 *  is off the API 404s — callers treat that as "not available yet". */
export async function getSponsorPool(options?: ApiOptions): Promise<{ students: SponsorPoolCard[] }> {
  return apiRequest('/api/v1/sponsor/pool/', options)
}

export async function getSponsorPoolDetail(id: number, options?: ApiOptions): Promise<SponsorPoolDetail> {
  return apiRequest(`/api/v1/sponsor/pool/${id}/`, options)
}

// F2 — a sponsor's own allocation: the ANONYMISED student card + money/status only.
export interface SponsorSponsorship {
  id: number
  status: 'offered' | 'active' | 'lapsed' | 'cancelled'
  amount: string
  offered_at: string
  accept_deadline: string | null
  decided_at: string | null
  student: SponsorPoolCard
  onboarded: boolean   // R2: journey signal — student completed onboarding
  semesters: number    // R2: count of recorded semester results
}

// A student the sponsor OWNS — the portfolio detail page (any lifecycle status), with the full
// generated anon profile. Reached by clicking a My-students card; read-only, no funding controls.
/** What a sponsor may see about their student's spending: CATEGORIES AND TOTALS ONLY.
 *
 * ⚠⚠ There is deliberately no merchant, no transaction id, no wallet and no purchase date in
 * this shape, and the server builds it one aggregate at a time so none can arrive by
 * accident (`spend_sponsor.py`). If you are adding a field here, the question to answer
 * first is whether a SPONSOR may see it.
 *
 * ⚠ Money is a STRING and stays one — it is only parsed for chart geometry, never for
 * display. A bare Decimal once reached this wire as a float; see `spend_sponsor`.
 *
 * ⚠ `as_at` is the date of the last IMPORT, not the day the student last bought something. */
export interface SponsorSpending {
  promised: string
  released: string
  spent: string
  left: string
  as_at: string
  /** Ranked by value. `other` is last when it exists; `transfer` and `unsorted` are NEVER
   *  folded into it, however small (owner, 2026-09-10). */
  categories: Array<{ code: string; label: string; total: string }>
}

export interface SponsorMyStudentDetail extends SponsorSponsorship {
  anon_profile: string  // the reviewed anonymous profile (markdown)
  /** null — not an empty card — when nothing has been imported for this student yet. Four
   *  zeroes would claim they have spent nothing; the likelier truth is no report has arrived. */
  spending: SponsorSpending | null
}

/** A student the caller sponsors (by application id). 404 if the caller doesn't sponsor them. */
export async function getMyStudentDetail(id: number, options?: ApiOptions): Promise<SponsorMyStudentDetail> {
  return apiRequest(`/api/v1/sponsor/my-students/${id}/`, options)
}

export interface SponsorWallet {
  balance: string
  donations: Array<{ amount: string; reference: string; created_at: string }>
  sponsorships: SponsorSponsorship[]
}

/** F2 — the sponsor's "My students" home: directed-giving balance + their holding
 *  (offered/active) allocations, each carrying the anonymised student card. 404s
 *  while the pool flag is off (callers treat that as "not available yet"). */
export async function getSponsorWallet(options?: ApiOptions): Promise<SponsorWallet> {
  return apiRequest('/api/v1/sponsor/wallet/', options)
}

/** E3 — fund a pooled student IN FULL for their admin-set award amount → an 'offered'
 *  award (the student is then notified to accept). On a bad state the thrown Error's
 *  `.code` is 'insufficient_balance' | 'not_fundable' | 'not_found'. */
export async function fundStudent(id: number, options?: ApiOptions): Promise<SponsorSponsorship> {
  return apiRequest(`/api/v1/sponsor/pool/${id}/fund/`, {
    ...options, method: 'POST', body: JSON.stringify({}),
  })
}

/** R2 — the My Giving dashboard aggregate: impact numbers + the giving-donut
 *  breakdown. Counts + money only (allowlist-safe, no student identity). 404s
 *  while the pool flag is off (callers treat that as "not available yet"). */
export interface SponsorImpact {
  total_given: string
  students_supported: number
  students_active: number
  students_graduated: number
  semesters_completed: number
  balance: { committed: string; completed: string; available: string }
}

export async function getSponsorImpact(options?: ApiOptions): Promise<SponsorImpact> {
  return apiRequest('/api/v1/sponsor/impact/', options)
}

/** R3 — the My Giving activity feed: this sponsor's own students' lifecycle events,
 *  anonymous ref only. 404s while the pool flag is off. */
export interface SponsorActivityEvent {
  type: 'funded' | 'accepted' | 'semester' | 'graduated' | 'thank_you'
  ref: string
  at: string
}

export async function getSponsorActivity(options?: ApiOptions): Promise<{ events: SponsorActivityEvent[] }> {
  return apiRequest('/api/v1/sponsor/activity/', options)
}

/** R3 — programme-wide belonging counts for the My Giving community strip. */
export interface SponsorCommunity {
  sponsors: number
  students_supported: number
  students_waiting: number
}

export async function getSponsorCommunity(options?: ApiOptions): Promise<SponsorCommunity> {
  return apiRequest('/api/v1/sponsor/community/', options)
}

/** R4 — the giving statement's two ledgers: donations INTO the trust + gifts OUT to
 *  students (anonymous ref only). 404s while the pool flag is off. */
export interface SponsorStatement {
  donations: Array<{ amount: string; reference: string; at: string }>
  gifts: Array<{ ref: string; amount: string; at: string }>
  total_in: string
  total_out: string
}

export async function getSponsorStatement(options?: ApiOptions): Promise<SponsorStatement> {
  return apiRequest('/api/v1/sponsor/statement/', options)
}

/** R5 — the Trust & Transparency hub: programme-level content (who-we-are /
 *  governance / sources & uses / assurance) + live community counts. The data is
 *  editable in the DB without a deploy; figures are illustrative until real audited
 *  ones are published. 404s while the pool flag is off. */
export interface TrustTrustee { name: string; role?: string; bio?: string }
export interface TrustFigure { label: string; amount: string }
export interface SponsorTrust {
  legal_entity: string
  contact_email: string
  trustees: TrustTrustee[]
  sources: TrustFigure[]
  uses: TrustFigure[]
  assurance: {
    fy?: string
    students_verified?: number
    disbursed?: string
    auditor?: string
    report_url?: string
  }
  figures_are_illustrative: boolean
  community: SponsorCommunity
}

export async function getSponsorTrust(options?: ApiOptions): Promise<SponsorTrust> {
  return apiRequest('/api/v1/sponsor/trust/', options)
}

/** R6 — AutoSponsor: the sponsor's own standing-gift config (auto-direct their
 *  balance to the next matching student; each allocation is still an offered
 *  sponsorship the student accepts). 404s while the pool flag is off. */
export interface SponsorStandingGift {
  configured: boolean
  active: boolean
  field_pref?: string
  state_pref?: string
  max_amount?: string | null
  last_allocated_at?: string | null
}

export async function getSponsorStandingGift(options?: ApiOptions): Promise<SponsorStandingGift> {
  return apiRequest('/api/v1/sponsor/standing-gift/', options)
}

export async function putSponsorStandingGift(
  body: { field_pref?: string; state_pref?: string; max_amount?: string | null; active?: boolean },
  options?: ApiOptions,
): Promise<SponsorStandingGift> {
  return apiRequest('/api/v1/sponsor/standing-gift/', {
    ...options, method: 'PUT', body: JSON.stringify(body),
  })
}

/** F1 — public live counter for the sponsor landing. No auth (a public marketing
 *  page calls it). While SPONSOR_POOL_ENABLED is off it returns {count:0,
 *  enabled:false} so the landing stays dark until go-live. */
export async function getStudentsWaitingCount(options?: ApiOptions): Promise<{ count: number; enabled: boolean }> {
  return apiRequest('/api/v1/sponsor/pool/count/', options)
}

