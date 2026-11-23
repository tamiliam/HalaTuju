/**
 * Officer cockpit — verdict items, the served fact band, document grouping and reliability.
 *
 * One of five modules `officerCockpit.ts` was split into (audit A3.3, structure only — every line
 * below is the line it was; F2 moved the band to the server). `officerCockpit.ts` re-exports all five, so `@/lib/officerCockpit`
 * still serves every importer.
 */

import { docTypeToFact } from '@/lib/docCategory'
import type { AdminVerdictFact, AdminVerdictItem, AdminApplicantDocument, OverrideSummary } from '@/lib/admin-api'

// ── Verdict item i18n key ─────────────────────────────────────────────────────

// STR-not-current copy is per-status (decisive, no word-salad). The backend keeps a
// single item code `str_not_current` (resolution/help engines key off that literal),
// and tags the reason in params.status. The custom i18n `t` has NO ICU MessageFormat —
// only flat `{var}` interpolation — so an ICU `select` would render raw. Resolve to a
// flat per-status key here instead: str_not_current_{wrong_type,rejected,stale,
// unreadable,unconfirmed}. Default to 'unconfirmed' (the approved-but-dateless case).
export function verdictItemKey(it: AdminVerdictItem): string {
  if (it.code === 'str_not_current') {
    return `str_not_current_${String(it.params?.status || 'unconfirmed')}`
  }
  // Request #62 review 2: the flat singular form ("All 1 grades match" read wrong).
  if (it.code === 'grades_verified' && Number(it.params?.count) === 1) return 'grades_verified_one'
  return it.code
}

// ── Fact band (served by the API) ────────────────────────────────────────────

/**
 * The AI Prediction band of a fact, in five words (i18n `admin.scholarship.verdict.band.<band>`).
 * F2 (fix plan): computed ONCE, on the server (`apps/scholarship/fact_bands.py`), and served on the
 * case detail as `ai_fact_bands` ({fact: band}). The tiles and the grey "AI Prediction" line both
 * render it; the browser no longer derives a band from the engine status (that copy drifted from
 * the grey line, and the QC floor read neither).
 */
export type FactBand = 'certain' | 'probable' | 'unsure' | 'unverifiable' | 'ruleNotMet'

export type FactTileTone = 'green' | 'amber' | 'blue' | 'red'

/** The colour each band is drawn in (Kent scale; both red bands share the red). */
export const BAND_TONE: Record<FactBand, FactTileTone> = {
  certain: 'green',
  probable: 'blue',
  unsure: 'amber',
  unverifiable: 'red',
  ruleNotMet: 'red',
}

/** The legend order, green to red. */
export const BAND_ORDER: readonly FactBand[] = ['certain', 'probable', 'unsure', 'unverifiable', 'ruleNotMet']

/**
 * The served band of one fact. A band the page does not know (an older API during a deploy, or a
 * fact the server did not band) falls back on the raw status: a 'gap' fact reads 'unverifiable'
 * (red, as it always was), anything else 'unsure': never green, never a claimed broken rule.
 */
export function factBandOf(
  bands: Partial<Record<string, string>> | null | undefined, fact: string, rawStatus?: string | null,
): FactBand {
  const band = bands?.[fact]
  if (band && Object.prototype.hasOwnProperty.call(BAND_TONE, band)) return band as FactBand
  return rawStatus === 'gap' ? 'unverifiable' : 'unsure'
}

// The "genuineness NOT checked yet" note (an evidence code the subtitle promotes on a tile that
// is not green).
const HIGHER_RESULTS_NOT_CHECKED = 'higher_results_not_checked'

// The confident "outside this gift's criteria" codes: usually the reason a tile is red (a fake
// offer with a validated reporting date can sit at 'review' and still carries
// `offer_not_official`; it leads there too, as the flag stands). PINNED to the
// backend `award.CONFIDENT_DISQUALIFIERS` by `__tests__/disqualifier-drift.test.ts`.
export const CONFIDENT_DISQUALIFIERS = new Set<string>([
  'offer_not_official',
  'income_above_b40_line',
  'pathway_funded_or_abroad',
  'pathway_start_year_outside',
  'pathway_offer_private',
])

/**
 * The tile's one-line subtitle item. A confident disqualifier leads, so the tile names the
 * reason it is red (#804, owner 2026-11-18: a red Pathway tile read "No pathway chosen yet"
 * while the start year was the reason). Next, the first unresolved problem. Otherwise, on a tile
 * that is not green, the "genuineness NOT checked yet" note leads the positive lines, so a
 * blue tile never reads as though the results were proved. Null = fall back to the status.
 */
export function factSubtitleItem(fact: AdminVerdictFact, band: FactBand): AdminVerdictItem | null {
  const decisive = fact.unresolved.find((it) => CONFIDENT_DISQUALIFIERS.has(it.code))
  if (decisive) return decisive
  if (fact.unresolved.length > 0) return fact.unresolved[0]
  if (band !== 'certain') {
    const nc = fact.evidence.find((e) => e.code === HIGHER_RESULTS_NOT_CHECKED)
    if (nc) return nc
  }
  return fact.evidence[0] ?? null
}

/** The detail list under the tiles: every line except the one the tile's subtitle already shows. */
export function factDetailItems(
  fact: AdminVerdictFact, band: FactBand,
): { unresolved: AdminVerdictItem[]; evidence: AdminVerdictItem[] } {
  const shown = factSubtitleItem(fact, band)
  return {
    unresolved: fact.unresolved.filter((it) => it !== shown),
    evidence: fact.evidence.filter((it) => it !== shown),
  }
}

// ── Document grouping ────────────────────────────────────────────────────────

// Which fact a doc_type belongs to now has ONE home, `@/lib/docCategory`, because three screens
// answered the question and only this one had been corrected (TD-262 / W5). The type is
// re-exported so the cockpit's own consumers keep importing it from here.
export type { DocFact } from '@/lib/docCategory'

export interface GroupedDocuments {
  identity: AdminApplicantDocument[]
  academic: AdminApplicantDocument[]
  pathway: AdminApplicantDocument[]
  income: AdminApplicantDocument[]
  additional: AdminApplicantDocument[]
  other: AdminApplicantDocument[]
  // Phase 2: replaced (superseded) documents — version history, kept out of every fact
  // group and shown under an "Old / Replaced" list so a superseded doc never reads as live.
  superseded: AdminApplicantDocument[]
}

/**
 * Group a flat list of documents under the verification-fact sections plus the
 * "additional" (supporting) and "other" (reviewer-requested extras) buckets. Any
 * superseded (replaced) document is diverted to the `superseded` bucket regardless of
 * its doc_type, so the fact sections only ever show the live copy.
 */
export function groupDocumentsByFact(
  documents: AdminApplicantDocument[],
): GroupedDocuments {
  const groups: GroupedDocuments = {
    identity: [],
    academic: [],
    pathway: [],
    income: [],
    additional: [],
    other: [],
    superseded: [],
  }
  for (const doc of documents) {
    if (doc.superseded_at) {
      groups.superseded.push(doc)
      continue
    }
    const fact = docTypeToFact(doc.doc_type)
    groups[fact].push(doc)
  }
  // Fixed within-section order. ACADEMIC: the SPM results slip first, the current-CGPA semester
  // slip below. ADDITIONAL: school-leaving cert → statement of intent → photo (anything else last;
  // "any other document/photo" lives in OTHER, not here).
  const orderBy = (list: AdminApplicantDocument[], order: string[]) => {
    const rank = (dt: string) => { const i = order.indexOf(dt); return i < 0 ? 99 : i }
    list.sort((a, b) => rank(a.doc_type) - rank(b.doc_type))
  }
  orderBy(groups.academic, ['higher_results', 'results_slip', 'semester_result'])
  orderBy(groups.additional, ['school_leaving_cert', 'statement_of_intent', 'photo'])
  return groups
}

// ── AI reliability (the scorekeeper — verification-assurance Sprint 3) ─────────

export const RELIABILITY_FACTS = ['identity', 'academic', 'pathway', 'income'] as const
export interface FactReliability { fact: string; decided: number; agree: number; pct: number }
export interface Reliability {
  applications: number
  perFact: FactReliability[]
  overall: { decided: number; agree: number; pct: number }
  /** ⚠ THE HONESTY FIELD. Every version of `verdict_engine` that produced a prediction in
   *  this roll-up. The rate above BLENDS them (owner 2026-09-11: surface the mix now, split
   *  the roll-up per version once there is enough under each to compare). Sorted, so the
   *  card renders the same order every time. */
  engineVersions: string[]
}

/** Turn the raw override metrics (how often the human DISAGREED with the AI) into the
 *  AGREEMENT view the card renders — per fact + overall. Agreement = 1 − override rate.
 *  Pure; `pct` is a 0–1 fraction (the component formats it). */
export function verdictReliability(m: OverrideSummary): Reliability {
  const perFact = RELIABILITY_FACTS.map((fact) => {
    const f = m.per_fact?.[fact] || { decided: 0, overrides: 0 }
    const agree = Math.max(0, f.decided - f.overrides)
    return { fact, decided: f.decided, agree, pct: f.decided ? agree / f.decided : 0 }
  })
  const agree = Math.max(0, m.fact_decisions - m.overrides)
  return {
    applications: m.applications,
    perFact,
    overall: { decided: m.fact_decisions, agree, pct: m.fact_decisions ? agree / m.fact_decisions : 0 },
    // Empty keys ('' = a caller that did not say) are dropped: they are an absence of
    // provenance, not a generation, and listing '' as a version would invent one.
    engineVersions: Object.keys(m.engine_versions || {}).filter(Boolean).sort(),
  }
}
