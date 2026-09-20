/**
 * The Programme Overview — "how is this gift doing?" — and the per-role panel layout that
 * decides which of its blocks a given admin sees, and in what order.
 */
import { adminFetch, adminMutate, giftQuery } from './client'
import type { ApiOptions } from './client'

// ── Programme Overview — "how is this gift doing?", shaped by role ───────────
//
// ⚠⚠ **EVERY SECTION IS OPTIONAL BECAUSE THE SERVER DECIDES WHICH ONES EXIST.**
// `programme_overview.SECTIONS_BY_ROLE` chooses the key set BEFORE anything is serialised, so a
// reviewer's payload has no `money` key to hide and a finance admin's has no `funnel`. The page
// renders by PRESENCE (`programmeOverview.has`) and never by role — a page that fetched
// everything and drew a subset would be a side door into pages the menu already withholds.
//
// ⚠ **MONEY IS A STRING IN EVERY KEY AND MUST STAY ONE.** It is parsed only for chart geometry
// (`programmeOverview.ts`), never for display: a `Decimal` rendered as a float is how `30.00`
// reached a sponsor's screen as `30.0` in S5.
//
// ⚠ `due_soon` / `overdue` are SUBSETS of `with_reviewer` (and of `mine.open`), not a partition.
// The strip reads "2 with a reviewer, 1 due soon"; making them exclusive would mean a case stopped
// being with its reviewer the moment it got late.
export interface OverviewFunnel {
  total: number
  /** All thirteen `STATUS_CHOICES`, zero-filled. An absent stage cannot be told from an empty one. */
  by_status: Record<string, number>
}
export interface OverviewMoney {
  students: number
  committed: string
  paid: string
  remaining: string
  spent: string
}
export interface OverviewAttention {
  unassigned: number
  with_reviewer: number
  due_soon: number
  overdue: number
  awaiting_qc: number
}
export interface OverviewWeekCount { week: string; count: number }
export interface OverviewMonthCount { month: string; count: number }
export interface OverviewMoneyMonth {
  month: string
  released: string
  spent: string
  released_cum: string
  spent_cum: string
  /** ⚠ MAY BE NEGATIVE, and is deliberately not floored: the wallet is the student's own and a
   *  parent may top it up, so students can spend more than we released. */
  gap: string
}
export interface OverviewStudentWeek {
  week: string
  /** Students with a LIVE WALLET that week — the denominator the page names in words. */
  students: number
  spent: string
  /** ⚠ A ROW COUNT, not an item count: a Vircle row is one card transaction. */
  transactions: number
  /** What a card payment cost that week on average — ringgit over rows. */
  spent_per_transaction: string
  transactions_per_student: string
}
/** The whole period in two figures — what the page prints beneath the weekly charts instead of
 *  every week's value. `null` when nothing has been spent. `students` are those whose wallet was
 *  live by `data_to`; `weeks` is the length of the weekly series. */
export interface OverviewStudentOverall {
  students: number
  weeks: number
  spent: string
  transactions: number
  /** Ringgit over rows. */
  spent_per_transaction: string
  /** Rows over students over weeks — how often a student pays in an average week. */
  weekly_transactions_per_student: string
}
export interface OverviewCategory { code: string; total: string; transactions: number }
export type OverviewBand = 'open' | 'due_soon' | 'overdue'
export interface OverviewMyCase {
  id: number
  ref: string
  applicant_name: string
  status: string
  assigned_at: string
  due_at: string
  band: OverviewBand
}
/** ⚠ The QC row is NOT the reviewer row: it carries `since` / `waiting_days`, never a band. */
export interface OverviewQcCase {
  id: number
  ref: string
  applicant_name: string
  status: string
  since: string | null
  waiting_days: number | null
}
/** ⚠ NO SCORE AND NO PERCENTILE (`reviewerDetail.ts`). `turnaround_days` is phrased on the page
 *  as how long a STUDENT waited, never as how fast this volunteer is. */
export interface OverviewPace { completed: number; turnaround_days: number | null }

/**
 * One intake round of the chosen gift, for the picker.
 *
 * ⚠ EVERY ROLE GETS THIS LIST. A round's name, year and state is a DATE — not a person and not a
 * sum — so a reviewer reading "2026 intake, closed" learns nothing the fence was withholding. The
 * org_admin-only intake-years endpoint is a different question and is not involved here.
 */
export interface OverviewIntake {
  id: number
  code: string
  name: string
  year: number
  state: 'draft' | 'open' | 'closed' | 'finished'
}

/** One row of the organisation's Overview layout: a widget and whether it is drawn. */
export interface OverviewLayoutRow {
  key: string
  on: boolean
}

/** The layout as stored, with who last touched it. */
export interface OverviewLayout {
  organisation: { code: string; name: string }
  sections: OverviewLayoutRow[]
  updated_by_email: string
  updated_at: string | null
}

export interface ProgrammeOverview {
  programme: { code: string; name: string } | null
  generated_at: string
  /** The newest day any spending file reaches, or null. Shown at the top of the page. */
  data_to: string | null
  /**
   * The sections this payload carries, IN THE ORDER THE PAGE MUST DRAW THEM.
   *
   * ⚠⚠ **IT IS AN ORDER NOW, NOT A SET.** The server narrows the role's sections by the
   * organisation's stored layout and emits them in the layout's own order; a page that kept its
   * own fixed JSX order would silently ignore every arrangement an org admin ever saved. It may
   * be EMPTY — an organisation that switched off everything a finance admin can see gets a 200
   * and a notice, because that is what they asked for.
   */
  sections: string[]
  funnel?: OverviewFunnel
  money?: OverviewMoney
  attention?: OverviewAttention
  applications_series?: {
    applications_per_week: OverviewWeekCount[]
    awards_per_month: OverviewMonthCount[]
  }
  money_series?: {
    money_per_month: OverviewMoneyMonth[]
    per_student_per_week: OverviewStudentWeek[]
    per_student_overall: OverviewStudentOverall | null
    by_category: OverviewCategory[]
  }
  mine?: { open: number; due_soon: number; overdue: number
           cases: OverviewMyCase[]; pace: OverviewPace }
  qc?: { awaiting: number; oldest_waiting_days: number | null
         cases: OverviewQcCase[]; pace: OverviewPace }
  /** The round the figures were narrowed to, echoed back — `null` when the whole history is shown. */
  intake: OverviewIntake | null
  /** The chosen gift's rounds, newest year first. `[]` when no gift is chosen (the picker hides). */
  intakes: OverviewIntake[]
  /**
   * The five customisable widgets with their flags, in order — **org_admin and super only.**
   *
   * ⚠⚠ **ITS PRESENCE IS THE PERMISSION.** The page shows Customise when this key arrived and on
   * nothing else: there is no `if (role === 'org_admin')` anywhere on the client, for the same
   * reason `has()` exists — a client-side role check is one edit away from being wrong, and the
   * server has already answered the question.
   */
  layout?: OverviewLayoutRow[]
}

/**
 * The Overview, narrowed to a gift and optionally to one of its rounds.
 *
 * ⚠ `intake` IS A COHORT ID, not a year. A wrong tenant's round, another gift's round, an unknown
 * id or a non-integer are all **404 `not_found`** (the `_gift_narrowing` reasoning: a fence's own
 * answer is "there is no such thing", never "you may not"), and the page clears a stale id and
 * reads again rather than showing an error a person cannot act on.
 */
export async function getProgrammeOverview(
  params: { programme?: string; intake?: number } = {}, options?: ApiOptions,
) {
  const gift = giftQuery(params.programme)
  const intake = params.intake === undefined
    ? ''
    : `${gift ? '&' : '?'}intake=${encodeURIComponent(String(params.intake))}`
  return adminFetch<ProgrammeOverview>(
    `/api/v1/admin/scholarship/programme-overview/${gift}${intake}`, options)
}

/** GET the organisation's Overview layout. `org` is a super's `?org=` override; an org_admin
 *  sends nothing and gets their own organisation. An organisation with no stored row gets the
 *  platform default, so this never 404s on "you have not customised yet". */
export async function getOverviewLayout(
  org?: string, options?: ApiOptions,
): Promise<OverviewLayout> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminFetch(`/api/v1/admin/scholarship/organisation/overview-layout/${q}`, options)
}

/**
 * Save the layout.
 *
 * ⚠⚠ **SEND THE FULL ORDERED LIST, ALWAYS.** The server validates `sections` as a PERMUTATION of
 * the five customisable widgets and refuses all-or-nothing (`bad_layout` / `bad_section` /
 * `duplicate_section` / `missing_section` / `bad_flag`, each with the offending `key`). A diff
 * would carry no order at all, which is the one thing this list exists to record.
 */
export async function saveOverviewLayout(
  sections: OverviewLayoutRow[], org?: string, options?: ApiOptions,
): Promise<OverviewLayout> {
  const q = org ? `?org=${encodeURIComponent(org)}` : ''
  return adminMutate(
    `/api/v1/admin/scholarship/organisation/overview-layout/${q}`, 'PUT', { sections }, options)
}

