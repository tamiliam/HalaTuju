/**
 * The cockpit Documents drawer's fact line for an OFFER LETTER — moved verbatim out of
 * `officerCockpit.documentFacts` (offer exact-read S6, 2026-11-03, a moves-only split:
 * `officerCockpit.ts` sat at its size allowance). The chip colour rules live here.
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
  // Owner policy: an offer can settle identity + pathway ONLY if it is a genuine OFFICIAL
  // public offer. A non-genuine offer (conditional / private-IPTS / a non-official
  // pemakluman/semakan notification) can't confirm the pathway — so the Pathway VARIABLE goes
  // red (it establishes no pathway; the verdict counts this chip, `_pathway_red_chips`) and an
  // 'Official' fact surfaces the genuineness itself. Official is TWO-TONE (owner 2026-07-08):
  // RED for fake (`not_offer_letter` — not recognisably a proper offer), AMBER for suspect
  // (thin/cropped fingerprints — "we aren't sure"), matching the slip/IC chip semantics.
  const auth = doc.authenticity?.status
  const notOfficial = !!auth && auth !== 'genuine'
  // Reporting-date BONUS (owner 2026-07-08): a validated official registration summons lifts a
  // SUSPECT doc's effective officialness — it provably summons the student to register at a
  // public institution, so it DOES establish the pathway. The Pathway chip must key off this
  // EFFECTIVE state (the same predicate `_pathway_red_chips` counts), or the tile (Certain) and
  // the chip (red) contradict each other — #56/#75. A FAKE doc stays not-official even with the
  // bonus. The Official chip below deliberately keeps the RAW genuineness (amber/red) — that
  // dimension is what Check-2 acts on and the bonus never repaints it.
  const fake = !!auth && auth.startsWith('not_')
  const effectiveNotOfficial = fake || (notOfficial && !c.reporting_official)
  const facts: DocumentFactLabel[] = [
    { key: 'name', status: factStatus(c.name) },
    { key: 'ic_no', status: factStatus(c.ic) },
  ]
  if (c.pathway) facts.push({ key: 'pathway', status: effectiveNotOfficial ? 'not' : factStatus(c.pathway) })
  if (notOfficial) facts.push({ key: 'official', status: fake ? 'not' : 'partial' })
  // Course-switch note (owner 2026-07-10): amber chip on the LIVE offer when it replaced a
  // genuinely different prior offer (any→any). Always shown, even after the student confirms —
  // so a swap never rides through as a silent green (the verdict tile carries the same note).
  if (c.switched_from) facts.push({ key: 'switched', status: 'partial' })
  // NB deliberately NO separate reporting-date chip (owner 2026-07-08): the Intake {year} chip
  // already carries the currency signal (green current / amber past), and the reporting-date
  // BONUS is band machinery — its effect shows in the tile + the offer_reporting_official
  // evidence line. A chip keyed on `reporting_official` also mislabels the ≥0.70 genuine offers,
  // whose stored reads predate the label field (they were never re-extracted; bonus is moot for
  // them). Removed same-day after a short-lived 'daftar' chip shipped.
  return facts
}
