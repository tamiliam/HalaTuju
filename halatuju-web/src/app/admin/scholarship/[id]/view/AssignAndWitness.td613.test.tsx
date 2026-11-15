/**
 * @jest-environment jsdom
 *
 * TD-613 (2026-11-15): THE COCKPIT'S REVIEWER CARD OFFERS A CHANGE EXACTLY WHEN THE SERVER TAKES ONE.
 *
 * A case whose holder can no longer review it (suspended, archived, out of Reviewers) comes back
 * open at a stage the stage window hides (a reopened funded case at AWAITING QC is shown, a reopened
 * decline is not). The card now reads the served `assignable` / `needs_new_holder`: it shows, it
 * unlocks, it names the departed holder, and it never offers Unassigned. Synthetic names only.
 */
import { render, screen } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'

import { AssignAndWitness } from './AssignAndWitness'

const t = ((k: string) => k) as unknown as Parameters<typeof AssignAndWitness>[0]['t']
const noop = () => undefined

function renderCard(app: Partial<AdminScholarshipDetail>, decisionLocked = true) {
  return render(
    <AssignAndWitness
      app={{ id: 1, query_sla: { ready_for_assignment: true }, programme_id: null, ...app } as unknown as AdminScholarshipDetail}
      t={t} busy="" isSuper={false} canAssign decisionLocked={decisionLocked}
      admins={[{ id: 5, name: 'Reviewer Five', role: 'reviewer' }]} doAssign={noop}
      witnessCardVisible={false} activeSources={[]} witnessSel="" setWitnessSel={noop}
      witnessBusy={false} witnessMsg="" setWitnessMsg={noop} witnessEditing={false}
      setWitnessEditing={noop} doAssignWitness={noop}
    />,
  )
}

const departed = { assigned_to_id: 77, assigned_to_name: 'Former Holder', assignable: true, needs_new_holder: true }

describe('a case whose holder has gone', () => {
  it('shows, unlocked, at a reopened decline the stage window hides', () => {
    const { container } = renderCard({ status: 'rejected', ...departed })
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.disabled).toBe(false)
    expect(container.querySelector('[data-needs-new-holder]')?.textContent)
      .toBe('admin.scholarship.assign.needsNewHolderHint')
  })

  it('names the departed holder and never offers Unassigned', () => {
    renderCard({ status: 'interviewed', ...departed })
    expect((screen.getByRole('option', { name: 'Former Holder' }) as HTMLOptionElement).selected).toBe(true)
    expect((screen.getByRole('option', { name: 'admin.scholarship.unassigned' }) as HTMLOptionElement).disabled)
      .toBe(true)
    expect((screen.getByRole('option', { name: 'Reviewer Five' }) as HTMLOptionElement).disabled).toBe(false)
  })
})

describe('a case whose holder can still work it', () => {
  it('is locked at Awaiting QC when the server says it may not change hands, even unlocked by a reopen', () => {
    const { container } = renderCard(
      { status: 'interviewed', assigned_to_id: 5, assigned_to_name: 'Reviewer Five', assignable: false, needs_new_holder: false },
      false,
    )
    expect((screen.getByRole('combobox') as HTMLSelectElement).disabled).toBe(true)
    expect(container.textContent).toContain('admin.scholarship.assign.error.not_assignable')
  })

  it('stays hidden at a decided decline', () => {
    const { container } = renderCard({ status: 'rejected', assigned_to_id: 5, assignable: false, needs_new_holder: false })
    expect(container.querySelector('select')).toBeNull()
  })
})
