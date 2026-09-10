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

/** True when the document's own distilled facts (drawer chips) mark `factKey` as a clean match. */
function factVerified(doc: AdminApplicantDocument, factKey: string): boolean {
  return documentFacts(doc).some((f) => f.key === factKey && f.status === 'verified')
}

/**
 * Map each requested profile field → its verification (or undefined). A field is present in the map
 * ONLY when a live document of the right type reports its relevant fact as a clean match.
 */
export function fieldVerifications(
  app: Pick<AdminScholarshipDetail, 'documents'>,
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
  if (docs.some((d) => usableOffer(d) && d.pathway_check?.chosen_institution_status === 'match')) {
    out.institution = { source: 'offerLetter' }
  }
  // Reporting date: the date READ off the offer (the shown value IS the offer's date).
  if (docs.some((d) => usableOffer(d) && d.pathway_check?.reporting_date)) {
    out.reportingDate = { source: 'offerLetter' }
  }

  // Address — a utility bill whose address matches the home address.
  set('address', 'water_bill', 'address', 'utilityBill') ||
    set('address', 'electricity_bill', 'address', 'utilityBill')

  //  · Parent name: the parent's IC is on file and legibly read.
  set('parentName', 'parent_ic', 'name', 'parentIc')
  //  · STR: only when the proof is BOTH approved (Lulus) AND current (dated).
  if (docs.some((d) => d.doc_type === 'str' && factVerified(d, 'status') && factVerified(d, 'current'))) {
    out.str = { source: 'strDoc' }
  }

  return out
}
