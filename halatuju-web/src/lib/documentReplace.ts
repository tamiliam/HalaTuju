/**
 * H6 "Replace a document": who may replace what, and how many replaces are left. Pure, so the
 * Action Centre and the Documents tab read the same rule. The cap itself is the server's
 * (`document_replace.REPLACE_LIMIT`, served as `replace_limit` on each document; 3 is only the
 * fallback for a payload from an older build). The server also refuses a replace once documents are
 * locked, except the types the case still asks for (`open_doc_types`).
 */
import type { ApplicantDocument, ResolutionItem } from '@/lib/api'

const FALLBACK_LIMIT = 3

/** Replaces this document has left (never below 0). */
export function replacesLeft(doc: Pick<ApplicantDocument, 'replace_count' | 'replace_limit'>): number {
  return Math.max(0, (doc.replace_limit ?? FALLBACK_LIMIT) - (doc.replace_count ?? 0))
}

/** True once the stage lock hides Replace for this type (an exempt type stays open). */
export function replaceLocked(docType: string, locked: boolean, openTypes: string[]): boolean {
  return locked && !openTypes.includes(docType)
}

/** A document the student has sent and that reads fine: it is with the reviewer, or already cleared.
 *  Replace on these counts toward the cap. A copy the student is SHOWN as needing a fix (a problem
 *  verdict, or an authenticity note that is not "genuine", suspect included) is the normal "send it
 *  again": never capped, never counted. This follows the server's `must_fix` (see documentReplace.test.ts): the serializer returns
 *  `authenticity` for suspect only on the types where it is shown and null where it is hidden, so a
 *  hidden suspect reads as settled here exactly as the server counts it. The server decides; this only
 *  chooses which cards show the counter and Replace. (An open request for the type is the server's
 *  other exemption; the Action Centre card for it carries no counter.) */
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
