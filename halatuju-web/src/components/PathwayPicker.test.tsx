/**
 * @jest-environment jsdom
 *
 * THE SCHOLARSHIP "MY PLANS" PICKER, mounted (owner rulings 2026-10-30). Shared by /scholarship/apply
 * and /profile. What it must do:
 *   - ask "Have you received an offer…?" and, with an offer, let her NAME the place: every pathway,
 *     then institution FIRST (State → Polytechnic / campus for the campus pathways, University
 *     straight away for the university ones), then the course;
 *   - list the whole catalogue — her results are NOT asked for — until she switches "Eligible
 *     only" on, which then narrows every step;
 *   - store the institution's catalogue name and id on the pick, and read it back to her;
 *   - offer the switch only where entry rules exist for her results (not the third route).
 *
 * Until 2026-10-30 this file pinned the opposite: that the picker ran the eligibility check on
 * mount and offered only eligible pathways (TD-325's results-held rule chose WHICH check). The
 * results-held rule still decides the branch (degree vs pathway), asserted below.
 *
 * `t` echoes its key, so assertions read against i18n keys.
 */
import { useState } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import PathwayPicker, { type PathwayForm } from './PathwayPicker'
import type { PathwayOfferings } from '@/lib/api'
import { calculatePathways, checkEligibility, checkStpmEligibility, getPathwayOfferings } from '@/lib/api'
import { PATHWAY_ORDER } from '@/lib/scholarship'
import { sandboxProfileFormSix, sandboxProfileStpm } from '@/sandbox/fixtures/scholarship'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))

const CATALOGUE: Record<string, PathwayOfferings> = {
  poly: {
    pathway: 'poly',
    institutions: [
      { id: 'PUO', institution_id: 'PUO', name: 'Politeknik Ungku Omar', state: 'Perak', course_ids: ['ELEK', 'MEK'] },
      { id: 'PKB', institution_id: 'PKB', name: 'Politeknik Kota Bharu', state: 'Kelantan', course_ids: ['MEK'] },
    ],
    courses: [
      { course_id: 'ELEK', course_name: 'Diploma Kejuruteraan Elektrik', field_key: 'elek', aliran: null },
      { course_id: 'MEK', course_name: 'Diploma Kejuruteraan Mekanikal', field_key: 'mek', aliran: null },
    ],
  },
  university: {
    pathway: 'university',
    institutions: [{ id: 'UITM', institution_id: 'UITM', name: 'Universiti Teknologi MARA', state: 'Selangor', course_ids: ['DSAINS'] }],
    courses: [{ course_id: 'DSAINS', course_name: 'Diploma Sains', field_key: 'sains', aliran: null }],
  },
  degree: {
    pathway: 'degree',
    institutions: [{ id: 'UM', institution_id: 'UM', name: 'Universiti Malaya', state: 'Kuala Lumpur', course_ids: ['LAW', 'MED'] }],
    courses: [
      { course_id: 'LAW', course_name: 'Ijazah Undang-Undang', field_key: 'law', aliran: null },
      { course_id: 'MED', course_name: 'Ijazah Perubatan', field_key: 'med', aliran: null },
    ],
  },
}

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getPathwayOfferings: jest.fn((p: string) => Promise.resolve(CATALOGUE[p] ?? { pathway: p, institutions: [], courses: [] })),
  // "Eligible only": she qualifies for the electrical diploma only, on the poly pathway only.
  checkEligibility: jest.fn(() => Promise.resolve({
    pathway_stats: { poly: 1 }, eligible_courses: [{ course_id: 'ELEK', course_name: 'Diploma Kejuruteraan Elektrik' }] })),
  calculatePathways: jest.fn(() => Promise.resolve({ pathways: [{ pathway: 'matric', trackId: 'sains', eligible: true }] })),
  checkStpmEligibility: jest.fn(() => Promise.resolve({ eligible_courses: [{ course_id: 'LAW' }] })),
}))

const FORM: PathwayForm = {
  pathwayCertainty: '', chosenPathway: '', chosenProgramme: null, preUTrack: '',
  preUInstitution: '', pathwaysConsidered: [], uncertaintyReasons: [], uncertaintyNote: '',
}
const SPM = { ...sandboxProfileFormSix, results_held: 'spm' }
const STPM = { ...sandboxProfileStpm, results_held: 'stpm' }

let latest: PathwayForm = FORM
function Harness({ profile }: { profile: Record<string, unknown> }) {
  const [form, setForm] = useState<PathwayForm>(FORM)
  latest = form
  return <PathwayPicker value={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} profile={profile as never} token="tkn" />
}
const mount = (profile: Record<string, unknown>) => render(<Harness profile={profile} />)
const click = (key: string) => fireEvent.click(screen.getByText(key).closest('button') as HTMLButtonElement)
const choose = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })
const options = (label: string) => Array.from((screen.getByLabelText(label) as HTMLSelectElement).options)
  .map((o) => o.value).filter(Boolean)

beforeEach(() => {
  jest.clearAllMocks()
  latest = FORM
})

it('asks the offer question, with the two stored answers', () => {
  mount(SPM)
  expect(screen.getByText('scholarship.apply.plan.question')).toBeTruthy()
  click('scholarship.apply.plan.uncertain')
  expect(latest.pathwayCertainty).toBe('uncertain')
  expect(screen.getByText('scholarship.apply.plan.uncertainIntro')).toBeTruthy()
  expect(screen.queryByRole('switch')).toBeNull()          // nothing to narrow while waiting
  click('scholarship.apply.plan.sure')
  expect(latest.pathwayCertainty).toBe('sure')
})

it('with an offer: EVERY pathway, and no results asked for', async () => {
  mount(SPM)
  click('scholarship.apply.plan.sure')
  expect(options('scholarship.apply.plan.pathwayLabel')).toEqual([...PATHWAY_ORDER])
  await act(async () => { await Promise.resolve() })
  expect(checkEligibility).not.toHaveBeenCalled()
  expect(calculatePathways).not.toHaveBeenCalled()
  expect(checkStpmEligibility).not.toHaveBeenCalled()
})

it('polytechnic: State → Polytechnic → Course, and the pick names the institution', async () => {
  mount(SPM)
  click('scholarship.apply.plan.sure')
  choose('scholarship.apply.plan.pathwayLabel', 'poly')
  await waitFor(() => expect(screen.getByLabelText('scholarship.apply.plan.stateLabel')).toBeTruthy())
  expect(getPathwayOfferings).toHaveBeenCalledWith('poly')
  expect(screen.queryByLabelText('scholarship.apply.plan.institutionLabel.poly')).toBeNull()   // state first
  expect(options('scholarship.apply.plan.stateLabel')).toEqual(['Kelantan', 'Perak'])
  choose('scholarship.apply.plan.stateLabel', 'Perak')
  expect(options('scholarship.apply.plan.institutionLabel.poly')).toEqual(['PUO'])
  choose('scholarship.apply.plan.institutionLabel.poly', 'PUO')
  const box = screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder')
  fireEvent.focus(box)
  fireEvent.click(screen.getByText('Diploma Kejuruteraan Elektrik'))
  expect(latest.chosenProgramme).toEqual({
    courseId: 'ELEK', courseName: 'Diploma Kejuruteraan Elektrik', fieldKey: 'elek',
    institution: 'Politeknik Ungku Omar', institutionId: 'PUO' })
  expect(screen.getByTestId('plan-named').textContent)
    .toBe('Diploma Kejuruteraan Elektrik · Politeknik Ungku Omar, Perak')
  expect(screen.getByText('scholarship.apply.plan.offerNote')).toBeTruthy()
})

it('university: University → Course, with no state step', async () => {
  mount(SPM)
  click('scholarship.apply.plan.sure')
  choose('scholarship.apply.plan.pathwayLabel', 'university')
  await waitFor(() => expect(screen.getByLabelText('scholarship.apply.plan.institutionLabel.university')).toBeTruthy())
  expect(screen.queryByLabelText('scholarship.apply.plan.stateLabel')).toBeNull()
  choose('scholarship.apply.plan.institutionLabel.university', 'UITM')
  fireEvent.focus(screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder'))
  fireEvent.click(screen.getByText('Diploma Sains'))
  expect(latest.chosenProgramme?.institution).toBe('Universiti Teknologi MARA')
})

it('changing the institution clears the course below it', async () => {
  mount(SPM)
  click('scholarship.apply.plan.sure')
  choose('scholarship.apply.plan.pathwayLabel', 'poly')
  await waitFor(() => screen.getByLabelText('scholarship.apply.plan.stateLabel'))
  choose('scholarship.apply.plan.stateLabel', 'Perak')
  choose('scholarship.apply.plan.institutionLabel.poly', 'PUO')
  fireEvent.focus(screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder'))
  fireEvent.click(screen.getByText('Diploma Kejuruteraan Mekanikal'))
  expect(latest.chosenProgramme?.courseId).toBe('MEK')
  choose('scholarship.apply.plan.stateLabel', 'Kelantan')
  expect(latest.chosenProgramme).toBeNull()
})

it('matriculation: all four tracks, unfiltered', () => {
  mount(SPM)
  click('scholarship.apply.plan.sure')
  choose('scholarship.apply.plan.pathwayLabel', 'matric')
  for (const tr of ['sains', 'kejuruteraan', 'sains_komputer', 'perakaunan']) {
    expect(screen.getByText(`scholarship.apply.plan.track.${tr}`)).toBeTruthy()
  }
  expect(calculatePathways).not.toHaveBeenCalled()
})

describe('"Eligible only" — off by default, narrows when switched on', () => {
  it('narrows the pathways, then the campuses and courses, sending bumiputera: true (Option A)', async () => {
    mount(SPM)
    click('scholarship.apply.plan.sure')
    const sw = screen.getByRole('switch', { name: 'search.eligibleOnly' })
    expect(sw.getAttribute('aria-checked')).toBe('false')
    fireEvent.click(sw)
    await waitFor(() => expect(options('scholarship.apply.plan.pathwayLabel')).toEqual(['poly']))
    expect((checkEligibility as jest.Mock).mock.calls[0][0].bumiputera).toBe(true)
    choose('scholarship.apply.plan.pathwayLabel', 'poly')
    await waitFor(() => expect(options('scholarship.apply.plan.stateLabel')).toEqual(['Perak']))   // PKB offers no eligible course
    choose('scholarship.apply.plan.stateLabel', 'Perak')
    choose('scholarship.apply.plan.institutionLabel.poly', 'PUO')
    fireEvent.focus(screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder'))
    expect(screen.getByText('Diploma Kejuruteraan Elektrik')).toBeTruthy()
    expect(screen.queryByText('Diploma Kejuruteraan Mekanikal')).toBeNull()
  })

  it('narrows the matriculation tracks', async () => {
    mount(SPM)
    click('scholarship.apply.plan.sure')
    fireEvent.click(screen.getByRole('switch', { name: 'search.eligibleOnly' }))
    await waitFor(() => expect(checkEligibility).toHaveBeenCalled())
    // matric is not in this student's eligible pathways; she can still reach it by switching off
    fireEvent.click(screen.getByRole('switch', { name: 'search.eligibleOnly' }))
    choose('scholarship.apply.plan.pathwayLabel', 'matric')
    fireEvent.click(screen.getByRole('switch', { name: 'search.eligibleOnly' }))
    await waitFor(() => expect(screen.queryByText('scholarship.apply.plan.track.perakaunan')).toBeNull())
    expect(screen.getByText('scholarship.apply.plan.track.sains')).toBeTruthy()
  })

  it('draws into the page\'s slot when one is given (the apply card header)', () => {
    const slot = document.createElement('div')
    document.body.appendChild(slot)
    render(<PathwayPicker value={{ ...FORM, pathwayCertainty: 'sure' }} onChange={() => {}} profile={SPM as never} token="tkn" switchSlot={slot} />)
    expect(within(slot).getByRole('switch')).toBeTruthy()
    slot.remove()
  })

  it.each(['matric', 'asasi', 'diploma'])('is not offered to a %s holder (no entry rules, D2)', (kind) => {
    mount({ ...sandboxProfileStpm, results_held: kind, higher_cgpa: 3.4 })
    click('scholarship.apply.plan.sure')
    expect(screen.queryByRole('switch')).toBeNull()
  })

  it('is not offered without results', () => {
    mount({ ...sandboxProfileFormSix })     // no served results_held: the "no results" fallback
    click('scholarship.apply.plan.sure')
    expect(screen.queryByRole('switch')).toBeNull()
  })
})

describe('STPM and third-route holders: University → Degree (TD-325 still picks the branch)', () => {
  it('lists every degree of the university, unfiltered, and records the university', async () => {
    mount(STPM)
    click('scholarship.apply.plan.sure')
    expect(screen.queryByLabelText('scholarship.apply.plan.pathwayLabel')).toBeNull()   // no pathway step
    await waitFor(() => expect(getPathwayOfferings).toHaveBeenCalledWith('degree'))
    choose('scholarship.apply.plan.institutionLabel.university', 'UM')
    fireEvent.focus(screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder'))
    expect(screen.getByText('Ijazah Perubatan')).toBeTruthy()
    fireEvent.click(screen.getByText('Ijazah Undang-Undang'))
    expect(latest.chosenProgramme).toMatchObject({ courseId: 'LAW', institution: 'Universiti Malaya', institutionId: 'UM' })
    expect(checkStpmEligibility).not.toHaveBeenCalled()
  })

  it('"Eligible only" asks the STPM check, with bumiputera: true, and narrows the degrees', async () => {
    mount(STPM)
    click('scholarship.apply.plan.sure')
    fireEvent.click(screen.getByRole('switch', { name: 'search.eligibleOnly' }))
    await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
    expect((checkStpmEligibility as jest.Mock).mock.calls[0][0].bumiputera).toBe(true)
    expect(checkEligibility).not.toHaveBeenCalled()
    await waitFor(() => screen.getByLabelText('scholarship.apply.plan.institutionLabel.university'))
    choose('scholarship.apply.plan.institutionLabel.university', 'UM')
    fireEvent.focus(screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder'))
    expect(screen.getByText('Ijazah Undang-Undang')).toBeTruthy()
    expect(screen.queryByText('Ijazah Perubatan')).toBeNull()
  })

  it('a matric holder gets the same unfiltered degree list', async () => {
    mount({ ...sandboxProfileStpm, results_held: 'matric', higher_cgpa: 3.4 })
    click('scholarship.apply.plan.sure')
    await waitFor(() => expect(getPathwayOfferings).toHaveBeenCalledWith('degree'))
    expect(checkStpmEligibility).not.toHaveBeenCalled()
  })
})

it('never reads the stored Bumiputera answer, even with "Eligible only" on', async () => {
  const reads: string[] = []
  // (STPM: its check picks the fields it sends; the SPM check is sent the whole profile spread —
  // which touches every key — with `bumiputera: true` laid over it, asserted above.)
  const profile = new Proxy({ ...STPM, bumiputera: false }, {
    get(target, key, recv) { if (key === 'bumiputera') reads.push('read'); return Reflect.get(target, key, recv) },
  })
  mount(profile)
  click('scholarship.apply.plan.sure')
  fireEvent.click(screen.getByRole('switch', { name: 'search.eligibleOnly' }))
  await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
  expect(reads).toEqual([])
})

// Review 2026-10-30: a failed catalogue fetch must not outlive the pathway it was for, and can be retried.
describe('a failed catalogue fetch', () => {
  const failOnce = () => (getPathwayOfferings as jest.Mock).mockImplementationOnce(() => Promise.reject(new Error('down')))

  it('clears when she switches to a pathway that fetches nothing (matriculation)', async () => {
    failOnce()
    mount(SPM)
    click('scholarship.apply.plan.sure')
    choose('scholarship.apply.plan.pathwayLabel', 'poly')
    expect(await screen.findByRole('alert')).toBeTruthy()
    choose('scholarship.apply.plan.pathwayLabel', 'matric')
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText('scholarship.apply.plan.track.sains')).toBeTruthy()
  })

  it('"Retry" asks again and draws the steps', async () => {
    failOnce()
    mount(SPM)
    click('scholarship.apply.plan.sure')
    choose('scholarship.apply.plan.pathwayLabel', 'poly')
    const alert = await screen.findByRole('alert')
    fireEvent.click(within(alert).getByText('common.retry'))
    expect(await screen.findByLabelText('scholarship.apply.plan.stateLabel')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(getPathwayOfferings).toHaveBeenCalledTimes(2)
  })
})
