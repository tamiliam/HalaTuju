/**
 * Sponsor terms — the pure decisions the panel makes, kept out of the components so they can be
 * unit-tested. The contract module's editors put this kind of logic inline and none of it is
 * covered; that is the mistake this file exists to avoid.
 */
import type { SponsorQuizPayload, SponsorTermsDetail, SponsorTermsSection } from './admin-api'

export const TERMS_LOCALES = ['en', 'ms', 'ta'] as const
export type TermsLocale = (typeof TERMS_LOCALES)[number]

/** Status → the pill's look. Active is the only one that is doing anything. */
export const STATUS_TONE: Record<string, string> = {
  active: 'bg-positive-100 text-positive-700',
  draft: 'bg-caution-100 text-caution-700',
  archived: 'bg-ground-100 text-ground-500',
}

/** Only a draft may be edited — a published version is immutable so a past acceptance can point
 *  at it forever and still mean something. The server enforces this; the UI must agree, or it
 *  offers buttons that can only fail. */
export function isEditable(terms: Pick<SponsorTermsDetail, 'status'> | null): boolean {
  return terms?.status === 'draft'
}

/** A checkpoint is complete when it would survive the server's Q2 rule: three non-blank options
 *  and an answer marked. Mirrors `sponsor_terms.quiz_payload_valid`. */
export function quizComplete(payload: SponsorQuizPayload | undefined | null): boolean {
  if (!payload) return false
  const opts = payload.options
  if (!Array.isArray(opts) || opts.length !== 3) return false
  if (!opts.every((o) => typeof o === 'string' && o.trim())) return false
  return payload.correct === 0 || payload.correct === 1 || payload.correct === 2
}

/**
 * Which sections still need work before this version could publish. Returned as section ORDERS so
 * the editor can mark them, rather than as a boolean the user has to hunt through.
 */
export function sectionsNeedingWork(sections: SponsorTermsSection[]): number[] {
  return sections
    .filter((s) => !s.heading_en.trim() || !s.body_en.trim()
      || (s.is_quiz_candidate && !quizComplete(s.quiz_en)))
    .map((s) => s.order)
}

/** How many checkpoints a sponsor will actually be asked. */
export function checkpointCount(sections: SponsorTermsSection[]): number {
  return sections.filter((s) => s.is_quiz_candidate && quizComplete(s.quiz_en)).length
}

/**
 * Translation progress per locale, for the honesty line above the editor.
 *
 * English is excluded — it is authoritative rather than a translation, so reporting it as "100%
 * translated" would be meaningless. A locale only counts a section when BOTH its heading and body
 * are present, matching `SponsorTermsVersion.languages_available` on the server.
 */
export function translationProgress(
  terms: Pick<SponsorTermsDetail, 'title_ms' | 'title_ta' | 'intro_ms' | 'intro_ta'>,
  sections: SponsorTermsSection[],
): Record<'ms' | 'ta', { done: number; total: number; complete: boolean }> {
  const out = {} as Record<'ms' | 'ta', { done: number; total: number; complete: boolean }>
  for (const loc of ['ms', 'ta'] as const) {
    const done = sections.filter(
      (s) => s[`heading_${loc}`].trim() && s[`body_${loc}`].trim()).length
    const intro = Boolean(terms[`title_${loc}`].trim() && terms[`intro_${loc}`].trim())
    out[loc] = {
      done,
      total: sections.length,
      complete: intro && sections.length > 0 && done === sections.length,
    }
  }
  return out
}

/** A new blank section, ready to append. */
export function blankSection(order: number): SponsorTermsSection {
  return {
    order,
    heading_en: '', heading_ms: '', heading_ta: '',
    body_en: '', body_ms: '', body_ta: '',
    is_quiz_candidate: false,
    quiz_en: {}, quiz_ms: {}, quiz_ta: {},
    quiz_generated_model: '',
  }
}

/**
 * Move a section up or down, returning a NEW array with orders renumbered 1..N.
 *
 * The server assigns orders by position on save, so what the editor shows and what it saves cannot
 * disagree — but renumbering here keeps the displayed numbers honest while editing.
 */
export function moveSection(
  sections: SponsorTermsSection[], index: number, delta: number,
): SponsorTermsSection[] {
  const target = index + delta
  if (index < 0 || index >= sections.length || target < 0 || target >= sections.length) {
    return sections
  }
  const next = sections.slice()
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  return renumber(next)
}

export function renumber(sections: SponsorTermsSection[]): SponsorTermsSection[] {
  return sections.map((s, i) => ({ ...s, order: i + 1 }))
}

/**
 * Clearing the quiz flag WIPES the payloads, mirroring `replace_sections` on the server.
 *
 * Doing it here as well is not belt-and-braces for its own sake: without it the editor would show
 * a section as "no checkpoint" while still holding the answers, and saving would then silently
 * discard work the user could still see on screen.
 */
export function setQuizFlag(section: SponsorTermsSection, on: boolean): SponsorTermsSection {
  if (on) return { ...section, is_quiz_candidate: true }
  return { ...section, is_quiz_candidate: false, quiz_en: {}, quiz_ms: {}, quiz_ta: {}, quiz_generated_model: '' }
}

/** Map a server error code to an i18n leaf. An allowlist, so an unmapped code can never render as
 *  a raw key path in front of an admin. */
const ERRORS = new Set([
  'version_required', 'version_exists', 'not_draft', 'unknown_config_field', 'sections_invalid',
  'quiz_not_candidate', 'quiz_ai_unconfigured', 'quiz_ai_unavailable', 'quiz_bad_json',
  'quiz_invalid', 'publish_forbidden', 'not_publishable', 'signature_required', 'not_found',
])

export function termsErrorKey(code: string | undefined): string {
  return ERRORS.has(code || '') ? `admin.sponsors.terms.error.${code}` : 'admin.sponsors.terms.error.generic'
}
