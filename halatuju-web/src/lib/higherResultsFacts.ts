/**
 * The cockpit Documents drawer's fact line for a higher-results upload (third results route S3b,
 * 2026-10-26): Name · Type (what the document IS against the results page — an SPM slip or another
 * kind reads red) · CGPA (the slip against the CGPA entered) · Results (STPM subject grades). No
 * genuineness fact: higher results have no signature family yet, so the Academic card says "not
 * checked". Its own leaf because `officerCockpit.ts` is at its size allowance.
 */
import type { AcademicCheck, HigherCheck } from '@/lib/api'

// The cockpit's own two shapes, restated structurally so this leaf imports nothing back from
// `officerCockpit.ts` (no import loop); tsc checks they still fit where they are returned.
type FactStatus = 'verified' | 'partial' | 'not' | 'unknown'
type DocumentFactLabel = { key: string; status: FactStatus }

export function higherResultsFacts(
  c: HigherCheck | null | undefined,
  factStatus: (s: string | undefined | null) => FactStatus,
  genuine: DocumentFactLabel | null = null,   // STPM exact-read S3: the Genuine / Wrong-type chip of a scored page
): DocumentFactLabel[] {
  if (!c) return []
  const facts: DocumentFactLabel[] = [
    { key: 'name', status: factStatus(c.name) },
    { key: 'type', status: c.kind_status === 'match' ? 'verified' : c.kind_status ? 'not' : 'unknown' },
    { key: 'cgpa', status: factStatus(c.cgpa_status) },
  ]
  if (c.grades_status) facts.push({ key: 'results', status: factStatus(c.grades_status) })
  if (genuine) facts.push(genuine)
  return facts
}

/**
 * S4 (#43): the SPM card holds a HIGHER result (`academic_check.higher_kind`). Name, and Type in red
 * — it is not an SPM slip — and no Subjects / Results: nothing was compared with the SPM grades.
 */
export function slipHigherFacts(
  c: AcademicCheck,
  st: (s: string | undefined | null) => FactStatus,
): DocumentFactLabel[] {
  return [{ key: 'name', status: st(c.name) }, { key: 'type', status: 'not' }]
}
