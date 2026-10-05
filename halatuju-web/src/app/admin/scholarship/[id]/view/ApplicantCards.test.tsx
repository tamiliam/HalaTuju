/**
 * @jest-environment jsdom
 *
 * Owner 2026-10-05 (#134, #119): "Pathways considered" and the "Still deciding" reasons are
 * APPLY-stage context. They used to stay on the cockpit after the student had been awarded; from
 * "Awaiting review" (`profile_complete`) onward — and in every ended state — they are hidden.
 * Rendered, not a source-shape guard: the claim is about what the officer sees for a status.
 */
import { render, screen } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { ApplicantCards } from './ApplicantCards'
import type { T } from './shared'

const t = ((k: string) => k) as unknown as T

function renderAt(status: string, extra: Partial<AdminScholarshipDetail> = {}) {
  const app = {
    status, qualification: 'spm', grades: {}, documents: [], guardians: [], consents: [],
    top_choices: [], chosen_pathway: '', chosen_programme: {},
    pathway_certainty: 'uncertain',
    pathways_considered: ['STPM', 'Matrikulasi'],
    uncertainty_reasons: ['Waiting for results'],
    ...extra,
  } as unknown as AdminScholarshipDetail
  return render(
    <ApplicantCards
      app={app} t={t} vtip={() => undefined}
      incomeValue={null} incomeTip={undefined} incomeNote={undefined}
      sizeValue={null} sizeTip={undefined} sizeNote={undefined} sizeNoteTone="muted"
      perCapita={null}
    />,
  )
}

const CONSIDERED = 'admin.scholarship.pathwaysConsidered'
const REASONS = 'admin.scholarship.uncertaintyReasons'

describe('ApplicantCards — apply-stage pathway context', () => {
  it.each(['submitted', 'shortlisted'])('shows both fields at the apply stage (%s)', (status) => {
    renderAt(status)
    expect(screen.getByText(CONSIDERED)).toBeTruthy()
    expect(screen.getByText(REASONS)).toBeTruthy()
  })

  it.each(['profile_complete', 'interviewing', 'interviewed', 'recommended', 'awarded', 'active',
    'maintenance', 'closed', 'rejected', 'withdrawn', 'expired'])(
    'hides both fields once the application has left the apply stage (%s)', (status) => {
      renderAt(status)
      expect(screen.queryByText(CONSIDERED)).toBeNull()
      expect(screen.queryByText(REASONS)).toBeNull()
    })

  it('still hides the reasons at the apply stage once the student is sure', () => {
    renderAt('shortlisted', { pathway_certainty: 'sure' })
    expect(screen.getByText(CONSIDERED)).toBeTruthy()
    expect(screen.queryByText(REASONS)).toBeNull()
  })
})
