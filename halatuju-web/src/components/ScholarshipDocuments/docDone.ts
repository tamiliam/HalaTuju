/** Whether a student's document card may fold away: it is genuinely finished (a verified doc reads
 *  all-green) or has nothing to verify. Moved out of `cards.tsx` to keep that file under the line cap. */
import type { ApplicantDocument } from '@/lib/api'

function docIsGenuine(doc: ApplicantDocument): boolean {
  const s = doc.authenticity?.status
  return !s || s === 'genuine'   // canonical: '' / 'genuine' vs suspect / not_<type>
}

export function docDone(docType: string, doc: ApplicantDocument | undefined): boolean {
  if (!doc) return false
  switch (docType) {
    case 'ic':
      return !!doc.vision_run_at
        && doc.vision_name_verdict === 'match'
        && doc.vision_nric_verdict === 'match'
        && docIsGenuine(doc)
    case 'results_slip': {
      const c = doc.academic_check
      return !!c && c.name === 'match' && c.subjects === 'match' && c.results === 'match'
        && docIsGenuine(doc)
    }
    // (`higher_results` never folds: the approved mock keeps its card open with the one-line read.)
    // Nothing to verify — uploaded IS finished.
    case 'photo':
    case 'statement_of_intent':
      return true
    default:
      return false   // everything else keeps today's always-open card
  }
}
