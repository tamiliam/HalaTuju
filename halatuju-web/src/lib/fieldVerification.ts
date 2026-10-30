import { documentFacts } from './officerCockpit'
import type { AdminApplicantDocument, AdminScholarshipDetail } from './admin-api'

/**
 * Field-level "verified" ticks for the officer cockpit (owner 2026-07-15). Purely a DISPLAY
 * projection of the document-matching the engines already do: a field is "verified" only when its
 * typed value MATCHES an uploaded, machine-read document — the same green truth the Documents
 * drawer chips show (`documentFacts`). We deliberately reuse that helper so the tick can never
 * disagree with the chip. No backend / no MODEL_VERSION involvement — read-only, additive.
 *
 * Rules are CONSERVATIVE: a tick shows only on the engine's strongest "clean match" (`verified`)
 * state. Partial / mismatch / no-document → no tick (absence = "not corroborated"; the drawer's red
 * chips own the mismatches, so we never paint a competing failure here).
 */
// NB household income + size ticks are NOT here — they come from the backend `household_check`
// reconciliation (document total vs stated), handled directly in the cockpit page.
export type VerifiableField =
  | 'name'
  | 'nric'
  | 'school'
  | 'grades'
  | 'chosenProgramme'
  | 'preUInstitution'
  | 'institution'
  | 'reportingDate'
  | 'address'
  | 'parentName'
  | 'str'

export interface FieldVerification {
  /** i18n suffix under admin.scholarship.verified.source.* — names the document it matched. */
  source: string
}

/** A document is "live" (not a superseded re-upload). The admin drawer keeps old copies visible. */
function isLive(doc: AdminApplicantDocument): boolean {
  return !doc.superseded_at
}

/** Upper-case, single-spaced, punctuation-free, so two printings of one value compare equal. */
const norm = (s?: string | null): string => (s || '').toUpperCase().replace(/[^A-Z0-9]+/g, ' ').trim()

/** An offer whose fields may stand behind a shown value: not a fake (`not_*`), addressed to THIS
 * student (her name matches, and the IC does not DISAGREE — many letters print no IC, and app 179's
 * reads `unreadable`), and not for a different course (`pathway` not `mismatch`). */
function backingOffer(d: AdminApplicantDocument): boolean {
  const pc = d.pathway_check
  const auth = d.authenticity?.status
  return d.doc_type === 'offer_letter' && isLive(d) && !!pc && !(auth && auth.startsWith('not_'))
    && pc.name === 'match' && pc.ic !== 'mismatch' && pc.pathway !== 'mismatch'
}

/**
 * The institution the Academic card shows. The student's own (`chosen_programme.institution`,
 * else `pre_u_institution`); when she named none, the institution on her own offer letter.
 * ⚠ It used to render "—" in that case WITH a tick (owner, 2026-10-30, four Sabah students): the
 * server checked the catalogue course's institution against the letter and found a match, so the
 * tick was true about a value the screen never showed. One reader, used by the card and by the
 * tick below, so the two cannot drift.
 */
export function shownInstitution(
  app: Pick<AdminScholarshipDetail, 'documents'>
    & Partial<Pick<AdminScholarshipDetail, 'chosen_programme' | 'pre_u_institution'>>,
): string {
  const own = ((app.chosen_programme?.institution as string) || app.pre_u_institution || '').trim()
  if (own) return own
  const offer = (app.documents || []).find((d) => backingOffer(d) && (d.pathway_check?.institution || '').trim())
  return (offer?.pathway_check?.institution || '').trim()
}

/** True when the document's own distilled facts (drawer chips) mark `factKey` as a clean match. */
function factVerified(doc: AdminApplicantDocument, factKey: string): boolean {
  return documentFacts(doc).some((f) => f.key === factKey && f.status === 'verified')
}

/**
 * Map each requested profile field → its verification (or undefined). A field is present in the map
 * ONLY when a live document of the right type reports its relevant fact as a clean match.
 */
export function fieldVerifications(
  app: Pick<AdminScholarshipDetail, 'documents' | 'guardian_ic_name_match'>
    & Partial<Pick<AdminScholarshipDetail, 'chosen_programme' | 'pre_u_institution'>>,
): Partial<Record<VerifiableField, FieldVerification>> {
  const docs = (app.documents || []).filter(isLive)
  const out: Partial<Record<VerifiableField, FieldVerification>> = {}

  const set = (field: VerifiableField, docType: string, factKey: string, source: string): boolean => {
    if (docs.some((d) => d.doc_type === docType && factVerified(d, factKey))) {
      out[field] = { source }
      return true
    }
    return false
  }

  // Identity — the MyKad is the authority (deterministic Vision read).
  set('name', 'ic', 'name', 'mykad')
  set('nric', 'ic', 'ic_no', 'mykad')

  // Academic.
  set('school', 'school_leaving_cert', 'school', 'schoolLeavingCert')
  set('grades', 'results_slip', 'results', 'resultsSlip')

  // Pathway (all three offer-based ticks). An offer is USABLE for verification unless it's a
  // genuine FAKE — a `not_offer_letter` / `not_*` read (it isn't an offer at all, so its fields are
  // meaningless). A merely SUSPECT (thin/cropped) offer still ticks: the field it read (programme /
  // institution / reporting date) is legitimately the offer's, and we don't withhold verification on
  // a soft genuineness doubt (owner 2026-07-16). Unscored → also usable (fail-open).
  const usableOffer = (d: AdminApplicantDocument): boolean => {
    if (d.doc_type !== 'offer_letter') return false
    const auth = d.authenticity?.status
    return !auth || !auth.startsWith('not_') // only a genuine fake (not_offer_letter / not_*) fails
  }
  // Chosen Programme (tertiary/programme pathways): the offer confirms the declared programme.
  if (docs.some((d) => usableOffer(d) && d.pathway_check?.pathway === 'match')) {
    out.chosenProgramme = { source: 'offerLetter' }
  }
  // ⚠ A TICK IS A FIELD-LEVEL FACT, NOT A SUMMARY OF THE DOCUMENT (owner, 2026-09-10:
  // *"I wonder if we could only tick the institution, as they do match."*).
  //
  // Both of these used to carry `&& pathway !== 'mismatch'` — a guard whose stated reason was that
  // "a green tick can't contradict a red Pathway chip" (#117: the school matches but the stream
  // clashes). That was an implementation choice copied forward from the pre-U tick, never an owner
  // ruling, and it conflates two different questions. The tick answers *"was THIS field verified
  // against the letter?"*; the chip answers *"does this document establish the declared pathway?"*
  // A student whose school matches exactly and whose STREAM differs has a verified institution and
  // an open pathway question — and the screen should say both, not suppress the true half.
  //
  // ⚠ THE RULE STAYS HONEST BECAUSE IT STILL KEYS ON THE INSTITUTION'S OWN VERDICT. Measured on
  // the four live records reading `mismatch` (2026-09-10): #33, #99 and #120 gain the tick — their
  // institution genuinely matches — and #14 gains nothing, because its institution genuinely
  // differs ("Temeloh" vs "TEMERLOH"). Removing the guard cannot tick a field that disagrees.
  //
  // Pre-U institution (matric/STPM): the offer's institution matches the SHOWN pre-U institution.
  if (docs.some((d) => usableOffer(d) && d.pathway_check?.institution_status === 'match')) {
    out.preUInstitution = { source: 'offerLetter' }
  }
  // Tertiary institution (poly / UA diploma / asasi / PISMP): the offer's institution matches the
  // SHOWN chosen_programme.institution (pre_u_institution is blank for these, so `institution_status`
  // can't tick them). The cockpit uses this for a tertiary student; a pre-U student uses
  // `preUInstitution`. NB `chosen_institution_status` already returns 'unknown' for an institution
  // copied off the letter itself, so this cannot tick a value that was never independently stated.
  // ⚠ Never on a blank: the card shows `shownInstitution`, and a tick beside "—" vouches for nothing.
  if (shownInstitution(app).trim()
      && docs.some((d) => usableOffer(d) && d.pathway_check?.chosen_institution_status === 'match')) {
    out.institution = { source: 'offerLetter' }
  }
  // ⚠ A VALUE THAT IS THE LETTER'S OWN IS BACKED BY THE LETTER (owner, 2026-10-30: *"Tick says the
  // value is backed by documented evidence … It is understood that if we checked the offer letter,
  // it would match."*). Supersedes request #9's "circular" rule for the TICK: when the course or the
  // institution was copied off the student's own offer, the engine still answers `unknown` (it
  // cannot test a letter against itself), but the shown value IS what the letter prints, exactly as
  // the reporting date always was. Thirteen of 52 tertiary students showed a ticked date beside an
  // unticked course from the same letter. Kept honest by `backingOffer`: her name and IC on it, not
  // a fake, not a different course — and by comparing the SHOWN value, so nothing else ticks.
  const backing = docs.filter(backingOffer)
  const course = norm(app.chosen_programme?.course_name as string)
  if (course && backing.some((d) => norm(d.pathway_check?.programme) === course)) {
    out.chosenProgramme = { source: 'offerLetter' }
  }
  const inst = norm(shownInstitution(app))
  if (inst && backing.some((d) => norm(d.pathway_check?.institution) === inst)) {
    out.institution = { source: 'offerLetter' }
  }
  // Reporting date: the date READ off the offer (the shown value IS the offer's date).
  if (docs.some((d) => usableOffer(d) && d.pathway_check?.reporting_date)) {
    out.reportingDate = { source: 'offerLetter' }
  }

  // Address — a utility bill whose address matches the home address.
  set('address', 'water_bill', 'address', 'utilityBill') ||
    set('address', 'electricity_bill', 'address', 'utilityBill')

  //  · Parent name (request #45): the CONTACT name matches the name read off a live parent/guardian
  //    IC. It used to tick whenever ANY parent IC was read — app 171 showed it beside the mother's
  //    name with only the father's IC on file. The name match is the server's (`vision.name_match`,
  //    served as `guardian_ic_name_match`); the drawer's Name chip must ALSO be green, so a card
  //    whose genuineness says it is not an IC cannot lend its read name. No match → no tick.
  const matched = new Set(app.guardian_ic_name_match || [])
  if (docs.some((d) => d.doc_type === 'parent_ic' && matched.has(d.id) && factVerified(d, 'name'))) {
    out.parentName = { source: 'parentIc' }
  }
  //  · STR: only when the proof is BOTH approved (Lulus) AND current (dated).
  if (docs.some((d) => d.doc_type === 'str' && factVerified(d, 'status') && factVerified(d, 'current'))) {
    out.str = { source: 'strDoc' }
  }

  return out
}
