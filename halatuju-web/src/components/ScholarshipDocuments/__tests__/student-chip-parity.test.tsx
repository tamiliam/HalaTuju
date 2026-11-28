/**
 * @jest-environment jsdom
 *
 * Document chip standard S1: TODAY's student checklists against the SHARED parity fixture.
 *
 * The api's `doc_chips_student.chips_for` (halatuju_api/apps/scholarship/doc_chips_student.py) is
 * checked against the same `student_cases` by `test_doc_chips_student.py`. This half renders today's
 * student components (checklists.tsx, checklistsPathway.tsx) with a stub `t` that returns the i18n
 * key, and reads every badge off the DOM: its colour, its word, and the row it sits on. No component
 * change in the cases. So the server can only serve what the student sees today, or one side goes red.
 *
 * `checks` below renders the real `DocChecks` dispatch exported from `cards.tsx`; the identity card that
 * has been read takes `ICChecklist`. The lazy
 * higher-results components are not drawn here (the server does not port them either).
 */
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import type { ApplicantDocument } from '@/lib/api'
import { readApi } from '@/test/apiSource'
import { ICChecklist } from '../checklists'
import { DocChecks } from '../cards'

type Chip = { key: string; status: string; state: string; student_action: string; kind: string; label: string }
type Case = { name: string; doc: Record<string, unknown>; chips: Chip[] }

const t = (key: string) => key

/** The REAL dispatch from `cards.tsx` (not a copy): a read IC card gets `ICChecklist`; the lazy higher
 *  results are left out (`lazyHigher={false}`), as the server does not port them either. */
function checks(d: ApplicantDocument): ReactNode {
  if (d.doc_type === 'ic' && d.vision_run_at) return <ICChecklist doc={d} t={t} />
  return <DocChecks doc={d} t={t} token={null} lazyHigher={false} />
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

/** The action line a bill chip's row draws (`data-chip-action`), 'none' when the row has none. */
function actionOf(badge: Element): string {
  return badge.closest('div[class*="py-1.5"]')?.parentElement?.querySelector('[data-chip-action]')?.getAttribute('data-chip-action') ?? 'none'
}

/** Every badge, in screen order, as the server's chip shape. */
function drawn(container: HTMLElement): Chip[] {
  const out: Chip[] = []
  container.querySelectorAll('span[data-chip], span.inline-flex.ring-1, p.text-caution-800').forEach((el) => {
    const state = el.getAttribute('data-chip') ?? stateOf(el)
    if (el.tagName === 'P') {
      out.push({ key: 'genuineness', status: STATUS[state], state, student_action: 'none', kind: 'note', label: el.textContent ?? '' })
    } else if (!el.hasAttribute('data-chip')) {            // SupportingDocChip: icon, then words
      const label = el.lastElementChild?.textContent ?? ''
      const key = label.startsWith('scholarship.docs.assist.') ? 'assist' : 'match'
      out.push({ key, status: STATUS[state], state, student_action: 'none', kind: 'fact', label })
    } else {
      out.push({ key: rowKey(el), status: STATUS[state], state, student_action: actionOf(el), kind: 'fact', label: (el.textContent ?? '').replace(/^[✓!✕]/, '') })
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
    // The approved look draws a plain copied value as the value only (no "from the document" tag), so the
    // plain chips are not drawn: every OTHER served chip is, in the same order, state and word.
    expect(drawn(container)).toEqual(c.chips.filter((x) => x.kind !== 'plain'))
  })
})
