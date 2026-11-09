/**
 * Officer cockpit — verdict items, fact tones, document grouping, AI suggestion and reliability.
 *
 * One of five modules `officerCockpit.ts` was split into (audit A3.3, structure only — every line
 * below is the line it was). `officerCockpit.ts` re-exports all five, so `@/lib/officerCockpit`
 * still serves every importer.
 */

import { docTypeToFact } from '@/lib/docCategory'
import type { AdminVerdictFact, AdminVerdictItem, AdminApplicantDocument, VerdictMetrics } from '@/lib/admin-api'

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

// ── Fact tile tone ───────────────────────────────────────────────────────────

export type FactTileTone = 'green' | 'amber' | 'blue' | 'red'

// Evidence codes that are NOT a verified value — a self-declaration or a soft signal.
// "Probable" (blue) must rest on at least one real verified value, so a fact backed
// only by these (or by nothing) is "Unsure", not "Probable".
//
// PINNED to the backend: every code the verdict engine emits with a `# SOFT` marker
// MUST appear here (and nothing here should be un-marked there). The jest guard
// `__tests__/soft-evidence-drift.test.ts` reads verdict_engine.py and fails on any
// drift — the denylist had rotted (Phase-2B/2C soft codes leaked a tile to blue,
// audit #11) precisely because nothing enforced the mirror.
// drift-test: halatuju-web/src/lib/__tests__/soft-evidence-drift.test.ts
export const SOFT_EVIDENCE = new Set<string>([
  'pathway_declared',              // the student's own declared pathway (unverified)
  'utility_percapita_b40',         // soft income proxy from the utility bills
  'utility_percapita_high',
  'utility_hardship',
  'unemployment_epf_corroborated', // Phase 2B: EPF (all-zeros/lapsed) hinting unemployment — soft
  'household_size_confirm',        // Phase 2C: described people > stated household size — soft
])

/**
 * Map a verdict fact to a colour tone on a collapsed Kent confidence scale —
 * how sure the engine is that the fact is sound:
 *   verified  → green  (Certain  — checks passed)
 *   review    → blue   (Probable — ≥1 verified value backs it; confirm the rest)
 *             → amber  (Unsure   — review with NO verified value: declared-only /
 *                        soft-signal-only / incomplete. Blue requires a green.)
 *   recommend → amber  (Unsure   — even odds; the coordinator places the verdict)
 *   gap       → red    (Can't verify — missing/unreadable evidence)
 */
export function factTileTone(fact: AdminVerdictFact): FactTileTone {
  switch (fact.status) {
    case 'verified':
      return 'green'
    case 'recommend':
      return 'amber'
    case 'review': {
      // Probable needs a green: at least one genuinely-verified value, not just a
      // declaration or a soft signal. Otherwise it's Unsure.
      const hasVerified = fact.evidence.some((e) => !SOFT_EVIDENCE.has(e.code))
      return hasVerified ? 'blue' : 'amber'
    }
    case 'gap':
    default:
      return 'red'
  }
}

// The estimative-probability band each tone names (Kent scale, collapsed to four).
// Used for the tile labels + legend; the i18n key is admin.scholarship.verdict.band.<key>.
export const TONE_BAND_KEY: Record<FactTileTone, string> = {
  green: 'certain',
  blue: 'probable',
  amber: 'unsure',
  red: 'unverifiable',
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

// ── AI suggestion summary ────────────────────────────────────────────────────

export type AiSuggest = 'yes' | 'no' | 'unsure'

export interface AiSuggestions {
  identity: AiSuggest
  academic: AiSuggest
  pathway: AiSuggest
  income: AiSuggest
}

/** Derive a plain yes / no / unsure suggestion from each fact's AI status. */
function statusToSuggest(status: AdminVerdictFact['status']): AiSuggest {
  if (status === 'verified') return 'yes'
  if (status === 'gap') return 'no'
  return 'unsure'
}

/**
 * Summarise the AI's verdict for each fact as a simple yes/no/unsure so the
 * record-verdict panel can render "AI suggested: Identity yes, Academic unsure…"
 * The coordinator then decides for themselves.
 */
export function aiSuggestionFor(verdictFacts: AdminVerdictFact[]): AiSuggestions {
  const defaults: AiSuggestions = {
    identity: 'unsure',
    academic: 'unsure',
    pathway: 'unsure',
    income: 'unsure',
  }
  for (const f of verdictFacts) {
    const key = f.fact as keyof AiSuggestions
    if (key in defaults) {
      defaults[key] = statusToSuggest(f.status)
    }
  }
  return defaults
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
export function verdictReliability(m: VerdictMetrics): Reliability {
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
