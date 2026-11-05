/**
 * @jest-environment jsdom
 *
 * REQUEST #62 — a subject the student ENTERED that the results slip does not show, in the cockpit.
 *
 * The server decides (`academic_engine.student_slip_check`: `subjects` = 'mismatch' when a slip
 * subject was not entered OR an entered one is not on a fully read slip, with the `extra` list) and
 * the verdict carries `academic_extra_subjects`. The browser never derives the rule; this file
 * asserts the officer SEES it: the drawer's Subjects chip goes red on an extra-only check (the
 * control: green on a clean one) and the Academic card names the new item.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildDocument, buildVerdict } from '@/test/adminApplicationDetail'
import type { AcademicCheck } from '@/lib/api'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const SUBJECTS_CHIP = 'admin.scholarship.docsDrawer.fact.subjects'

const check = (over: Partial<AcademicCheck>): AcademicCheck => ({
  name: 'match', subjects: 'match', results: 'match', candidate_name: 'TEST STUDENT 07',
  exam: '', exam_year: '', missing: [], extra: [], mismatched: [], uncertain: [], slip_count: 2,
  ...over,
})

const mount = async (academic: AcademicCheck, verdict = buildVerdict()) => {
  renderCockpit({ role: 'super', stage: 'interviewing', build: {
    documents: [buildDocument('results_slip', { id: 320, academic_check: academic })], verdict } })
  await loaded()
}

describe('an entered subject the slip does not show', () => {
  it('⚠ REDS THE SUBJECTS CHIP when the server serves an extra-only mismatch', async () => {
    await mount(check({ subjects: 'mismatch', extra: ['Fizik'] }))
    expect(screen.getByText(SUBJECTS_CHIP).className).toContain('text-critical-600')
  })

  it('and the control: a clean slip check keeps the chip green', async () => {
    await mount(check({}))
    expect(screen.getByText(SUBJECTS_CHIP).className).toContain('text-positive-700')
  })

  it('the Academic card names the new item', async () => {
    const verdict = buildVerdict({ academic: 'review' }).map((f) => f.fact === 'academic'
      ? { ...f, unresolved: [{ code: 'academic_extra_subjects', params: { subjects: 'Fizik' } }] } : f)
    await mount(check({ subjects: 'mismatch', extra: ['Fizik'] }), verdict)
    expect(screen.getAllByText('admin.scholarship.verdict.item.academic_extra_subjects').length)
      .toBeGreaterThan(0)
  })
})
