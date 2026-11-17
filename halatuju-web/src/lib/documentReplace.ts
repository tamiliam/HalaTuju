/**
 * H6 "Replace a document": who may replace what, and how many replaces are left. Pure, so the
 * Action Centre and the Documents tab read the same rule. The rule is the server's
 * (`document_replace.SlotBook`): a slot takes the first upload and three replaces, counted across
 * Remove, plus one more for each ask a person raised after its last upload. Before consent nobody can
 * ask, so a slot whose copy holds the consent gate takes up to four more (eight in all); any slot shut
 * before consent (at four or at eight) is served `replace_support` and refused with the body code
 * `replace_limit_support`, and the student is sent to support instead of told her reviewer will ask. The server serves the
 * answer as `replaces_left` on each document; `replace_limit - replace_count` (3 the fallback) is only
 * for a payload from an older build. The server also refuses a replace once documents are locked,
 * except the types the case still asks for (`open_doc_types`).
 */
import type { ApplicantDocument, ResolutionItem } from '@/lib/api'

const FALLBACK_LIMIT = 3
const SUPPORT_CODE = 'replace_limit_support'

/** Replaces this document's slot has left (never below 0): the server's own number when served. */
export function replacesLeft(doc: Pick<ApplicantDocument, 'replace_count' | 'replace_limit' | 'replaces_left'>): number {
  if (typeof doc.replaces_left === 'number') return Math.max(0, doc.replaces_left)
  return Math.max(0, (doc.replace_limit ?? FALLBACK_LIMIT) - (doc.replace_count ?? 0))
}

/** The line a shut slot shows: support when shut before consent (no ask is possible), else the reviewer will ask. */
export function replaceLimitKey(doc?: Pick<ApplicantDocument, 'replace_support'> | null): string {
  return doc?.replace_support ? 'scholarship.actionCentre.replaceLimitSupport' : 'scholarship.actionCentre.replaceLimit'
}

/** The text for a `replace_limit_reached` 409: the pre-consent support line in the student's own
 *  language, else the server's message (the reviewer will ask), else the plain line. */
export function replaceRefusalText(e: unknown, t: (key: string) => string): string {
  if ((e as { bodyCode?: string } | null)?.bodyCode === SUPPORT_CODE) return t('scholarship.actionCentre.replaceLimitSupport')
  return (e as Error | null)?.message || t('scholarship.actionCentre.replaceLimit')
}

/** True once the stage lock hides Replace for this type (an exempt type stays open). */
export function replaceLocked(docType: string, locked: boolean, openTypes: string[]): boolean {
  return locked && !openTypes.includes(docType)
}

/** A document the student has sent and that reads fine: it is with the reviewer, or already cleared.
 *  Only a hint for the upload's `replace` flag (the server ignores it): every upload into a slot counts
 *  toward the cap, a copy that needs a fix included, so the counter is NOT gated on this. */
export function isSettledDoc(doc: ApplicantDocument): boolean {
  if (doc.verification_status === 'rejected') return false   // a returned copy is a fix: the server never caps it
  const v = doc.vision_fields?.student_verdict
  const s = doc.authenticity?.status
  return (!v || v === 'ok' || v === 'review_manually') && (!s || s === 'genuine')
}

/** The live document a resolved doc item is about: same type, then the item's member if it names one,
 *  else the only one of that type. Null when there is none (no Replace then). */
export function docForItem(docs: ApplicantDocument[], item: ResolutionItem): ApplicantDocument | null {
  const ofType = docs.filter((d) => d.doc_type === item.doc_type)
  const member = typeof item.params?.household_member === 'string' ? item.params.household_member : ''
  const exact = member ? ofType.filter((d) => d.household_member === member) : ofType
  return exact.length === 1 ? exact[0] : null
}
