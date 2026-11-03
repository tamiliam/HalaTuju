/**
 * The cockpit Documents drawer's fact line for an OFFER LETTER — moved verbatim out of
 * `officerCockpit.documentFacts` (offer exact-read S6, 2026-11-03, a moves-only split:
 * `officerCockpit.ts` sat at its size allowance). The chip colour rules live here (S6: the owner's
 * chip table, below).
 */
import type { AdminApplicantDocument } from '@/lib/admin-api'

// The cockpit's own two shapes, restated structurally so this leaf imports nothing back from
// `officerCockpit.ts` (no import loop); tsc checks they still fit where they are returned.
type FactStatus = 'verified' | 'partial' | 'not' | 'unknown'
type DocumentFactLabel = { key: string; status: FactStatus }

export function offerFacts(
  doc: AdminApplicantDocument,
  factStatus: (s: string | undefined | null) => FactStatus,
): DocumentFactLabel[] {
  const c = doc.pathway_check
  if (!c) return []
  // THE OWNER'S CHIP TABLE (2026-11-02, offer exact-read S6): green = fine, nothing to do; yellow =
  // the reviewer should look; red = something is WRONG with the letter.
  //   Name / IC  — green match · yellow partial / unreadable (a blank or unread field is "look": many
  //                universities print no IC at all) · red mismatch (another person).
  //   Pathway    — green when the letter matches the student's choice, or she declared nothing and a
  //                GENUINE offer set it (`pathway_set_by_offer`); yellow otherwise — it differs (the
  //                Check 2 `pathway_confirm` query asks her), there is nothing to compare, or the letter
  //                is not a genuine offer. NEVER red: a different pathway is not a fault in the letter.
  //   Official   — green genuine · yellow suspect (a person decides) · red not_offer_letter (a fail).
  //   Reporting date — green read · yellow not printed (shown once the letter was read).
  // The verdict ladder counts only the red ones (`verdict_ladder._OFFER_CHIP_RED`), so the tile and
  // the chips agree.
  const auth = doc.authenticity?.status
  const fake = !!auth && auth.startsWith('not_')
  const identity = (s: string | undefined | null): FactStatus => (s === 'unreadable' ? 'partial' : factStatus(s))
  const facts: DocumentFactLabel[] = [
    { key: 'name', status: identity(c.name) },
    { key: 'ic_no', status: identity(c.ic) },
  ]
  if (c.pathway) {
    const green = !fake && (c.pathway === 'match' || !!c.pathway_set_by_offer)
    facts.push({ key: 'pathway', status: green ? 'verified' : 'partial' })
  }
  if (auth) facts.push({ key: 'official', status: auth === 'genuine' ? 'verified' : fake ? 'not' : 'partial' })
  const read = !(c.name === 'pending' && c.ic === 'pending')
  if (read) facts.push({ key: 'reportingDate', status: (c.reporting_date || '').trim() ? 'verified' : 'partial' })
  // Course-switch note (owner 2026-07-10): amber chip on the LIVE offer when it replaced a
  // genuinely different prior offer (any→any). Always shown, even after the student confirms —
  // so a swap never rides through as a silent green (the verdict tile carries the same note).
  if (c.switched_from) facts.push({ key: 'switched', status: 'partial' })
  return facts
}
