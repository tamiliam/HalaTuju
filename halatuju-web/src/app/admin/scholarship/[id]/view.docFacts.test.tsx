/**
 * @jest-environment jsdom
 *
 * THE DOCUMENT DRAWER SAYS WHAT A CHIP MEANS — Next-tier batch 2 (2026-10-01), rendered.
 *
 *   · TD-157 — a Singapore payslip shows "Converted from S$X at R = RM Y", from the SERVED
 *     `sgd_conversion` (the api reads the income engine's own conversion; see
 *     `halatuju_api/apps/scholarship/sgd_conversion.py`). No note for any other document.
 *   · TD-220 — the payslip's IC chip names which red it is: the number read and DIFFERS, or the
 *     slip could not be read at all.
 *   · TD-158 — a birth certificate scored as the wrong kind of document shows no green row.
 *
 * `t` echoes its key (the cockpit harness), so the drawer is read by key; the S$ note's wording is
 * checked against the real en.json template with the real interpolation, below.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildDocument } from '@/test/adminApplicationDetail'
import { interpolateMessage } from '@/lib/branding'
import type { IncomeProofCheck } from '@/lib/api'
import enMessages from '@/messages/en.json'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const FACT = (k: string) => `admin.scholarship.docsDrawer.fact.${k}`
const SG = { sgd: '3,114.00', rate: '3.15', myr: '9,809.10' }
const proof = (nric: string, nric_status: IncomeProofCheck['nric_status']): IncomeProofCheck => ({
  name: 'RAVI', nric, name_status: 'match', nric_status, member: 'father', ic_present: true, points: [],
})

describe('TD-157 — the Singapore payslip says what it was counted at', () => {
  it('a converted slip carries the note; an ordinary one does not', async () => {
    renderCockpit({ role: 'super', stage: 'interviewing', build: { documents: [
      buildDocument('salary_slip', { id: 401, household_member: 'father', sgd_conversion: SG,
        income_proof_check: proof('', 'no_ref') }),
      buildDocument('salary_slip', { id: 402, household_member: 'mother', sgd_conversion: null,
        income_proof_check: proof('', 'no_ref') }),
    ] } })
    await loaded()
    const notes = screen.getAllByTestId('sgd-conversion')
    expect(notes).toHaveLength(1)
    expect(notes[0].textContent).toBe('admin.scholarship.docsDrawer.sgdConverted')
  })

  it('the English template reads as the entry asks, with every figure in it', () => {
    const template = enMessages.admin.scholarship.docsDrawer.sgdConverted
    expect(interpolateMessage(template, SG)).toBe('Converted from S$3,114.00 at 3.15 = RM 9,809.10')
  })
})

describe('TD-220 — the payslip IC chip names its failure', () => {
  it('a number read that differs says "does not match"', async () => {
    renderCockpit({ role: 'super', stage: 'interviewing', build: { documents: [
      buildDocument('salary_slip', { id: 403, household_member: 'father',
        income_proof_check: proof('751206-06-5041', 'mismatch') }),
    ] } })
    await loaded()
    expect(screen.getByText(FACT('ic_no_mismatch'))).toBeTruthy()
    expect(screen.queryByText(FACT('ic_no_unreadable'))).toBeNull()
  })

  it('a slip that could not be read says so', async () => {
    renderCockpit({ role: 'super', stage: 'interviewing', build: { documents: [
      buildDocument('salary_slip', { id: 404, household_member: 'father',
        vision_fields: { student_verdict: 'unreadable' },
        income_proof_check: proof('', 'no_ref') }),
    ] } })
    await loaded()
    expect(screen.getByText(FACT('ic_no_unreadable'))).toBeTruthy()
    expect(screen.queryByText(FACT('ic_no_mismatch'))).toBeNull()
  })
})

describe('TD-158 — a wrong-type birth certificate shows no green row', () => {
  it('its Child / Mother / Father chips are red, beside a Wrong type chip', async () => {
    renderCockpit({ role: 'super', stage: 'interviewing', build: { documents: [
      buildDocument('birth_certificate', { id: 405,
        authenticity: { status: 'not_birth_certificate', reason: 'x' },
        bc_check: { child_name: '', child_status: 'match', mother_name: '', mother_nric: '',
          mother_status: 'match', father_name: '', father_status: 'match', bc_number: '' } }),
    ] } })
    await loaded()
    for (const k of ['child', 'mother', 'father', 'wrongType']) {
      expect(screen.getByText(FACT(k)).className).not.toMatch(/positive/)
    }
    expect(screen.getByText(FACT('child')).className).toBe(screen.getByText(FACT('wrongType')).className)
  })
})
