/**
 * @jest-environment jsdom
 *
 * Document chip standard S1: TODAY's student checklists against the SHARED parity fixture.
 *
 * The api's `doc_chips_student.chips_for` (halatuju_api/apps/scholarship/doc_chips_student.py) is
 * checked against the same `student_cases` by `test_doc_chips_student.py`. This half renders today's
 * student components (checklists.tsx, checklistsPathway.tsx) with a stub `t` that returns the i18n
 * key, and reads every badge off the DOM: its colour, its word, and the row it sits on. No component
 * changes. So the server can only serve what the student sees today, or one side goes red.
 *
 * `checks` below is the per-document branch of `cards.tsx` (the `checks` block), copied because it
 * sits inside the card component; the identity card that has been read takes `ICChecklist`. The lazy
 * higher-results components are not drawn here (the server does not port them either).
 */
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import type { ApplicantDocument } from '@/lib/api'
import { readApi } from '@/test/apiSource'
import {
  BcChecklist, GenuinenessNote, GuardianshipChecklist, ICChecklist, IncomeIcChecklist,
  IncomeProofChecklist, ResultsSlipChecklist, StrChecklist, UtilityChecklist,
} from '../checklists'
import { OfferLetterChecklist, SupportingDocChip } from '../checklistsPathway'

type Chip = { key: string; status: string; state: string; kind: string; label: string }
type Case = { name: string; doc: Record<string, unknown>; chips: Chip[] }

const t = (key: string) => key

function checks(d: ApplicantDocument): ReactNode {
  if (d.doc_type === 'ic' && d.vision_run_at) return <ICChecklist doc={d} t={t} />
  const body =
    d.doc_type === 'results_slip' && d.academic_check?.higher_kind ? null
      : d.doc_type === 'results_slip' && d.academic_check ? <ResultsSlipChecklist doc={d} t={t} />
        : d.doc_type === 'higher_results' && d.higher_check ? null
          : d.doc_type === 'offer_letter' && d.pathway_check ? <OfferLetterChecklist doc={d} t={t} />
            : d.doc_type === 'parent_ic' && d.income_ic_check ? <IncomeIcChecklist doc={d} t={t} />
              : (d.doc_type === 'salary_slip' || d.doc_type === 'epf') && d.income_proof_check ? <IncomeProofChecklist doc={d} t={t} />
                : d.doc_type === 'str' && d.str_check ? <StrChecklist doc={d} t={t} />
                  : (d.doc_type === 'water_bill' || d.doc_type === 'electricity_bill') && d.utility_check ? <UtilityChecklist doc={d} t={t} />
                    : d.doc_type === 'birth_certificate' && d.bc_check ? <BcChecklist doc={d} t={t} />
                      : d.doc_type === 'guardianship_letter' && d.guardianship_check ? <GuardianshipChecklist doc={d} t={t} />
                        : <SupportingDocChip doc={d} t={t} />
  return (
    <>
      {body}
      <GenuinenessNote doc={d} t={t} />
    </>
  )
}

const STATUS: Record<string, string> = { green: 'verified', amber: 'partial', red: 'not', grey: 'unknown' }

function stateOf(el: Element): string {
  const c = el.className
  if (/text-positive-(700|800)/.test(c)) return 'green'
  if (/text-caution-(700|800)/.test(c)) return 'amber'
  if (/text-critical-700/.test(c)) return 'red'
  if (/text-ground-(500|600|700)/.test(c)) return 'grey'
  throw new Error(`student chip parity: unknown badge colour ${c}`)
}

function rowKey(badge: Element): string {
  const label = badge.parentElement?.querySelector('span.font-medium')?.textContent ?? ''
  return label.replace(/:\s*$/, '').replace(/\s*\(.*$/, '').split('.').pop() ?? ''
}

/** Every badge, in screen order, as the server's chip shape. */
function drawn(container: HTMLElement): Chip[] {
  const out: Chip[] = []
  container.querySelectorAll('span.rounded-full.ring-1, p.text-caution-800').forEach((el) => {
    const state = stateOf(el)
    if (el.tagName === 'P') {
      out.push({ key: 'genuineness', status: STATUS[state], state, kind: 'note', label: el.textContent ?? '' })
    } else if (el.className.includes('inline-flex')) {            // SupportingDocChip: icon, then words
      const label = el.lastElementChild?.textContent ?? ''
      const key = label.startsWith('scholarship.docs.assist.') ? 'assist' : 'match'
      out.push({ key, status: STATUS[state], state, kind: 'fact', label })
    } else {
      const kind = el.className.includes('font-semibold') ? 'fact' : 'plain'
      out.push({ key: rowKey(el), status: STATUS[state], state, kind, label: el.textContent ?? '' })
    }
  })
  return out
}

const cases: Case[] = JSON.parse(readApi('apps/scholarship/tests/fixtures/doc_chip_parity.json')).student_cases

describe("student chip parity (today's student checklists vs the shared fixture)", () => {
  test('the fixture is big enough to mean something', () => {
    expect(cases.length).toBeGreaterThanOrEqual(50)
  })

  test.each(cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const { container } = render(<>{checks(c.doc as unknown as ApplicantDocument)}</>)
    expect(drawn(container)).toEqual(c.chips)
  })
})
