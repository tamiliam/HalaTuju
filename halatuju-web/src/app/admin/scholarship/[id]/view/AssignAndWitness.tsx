'use client'

/**
 * ASSIGN A REVIEWER, and below it THE WITNESS ORGANISATION for a sourceless student.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import type { Dispatch, SetStateAction } from 'react'
import { showsReviewerAssignedCard, assignOptions } from '@/lib/officerCockpit'
import type { AdminScholarshipDetail, SourceItem } from '@/lib/admin-api'

import type { T } from './shared'

export function AssignAndWitness({
  app, t, busy, isSuper, canAssign, decisionLocked, admins, doAssign,
  witnessCardVisible, activeSources, witnessSel, setWitnessSel,
  witnessBusy, witnessMsg, setWitnessMsg, witnessEditing, setWitnessEditing, doAssignWitness,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  isSuper: boolean
  canAssign: boolean
  decisionLocked: boolean
  admins: Array<{ id: number; name: string; role: string }>
  doAssign: (adminId: number | null) => void
  witnessCardVisible: boolean
  activeSources: SourceItem[]
  witnessSel: string
  setWitnessSel: Dispatch<SetStateAction<string>>
  witnessBusy: boolean
  witnessMsg: string
  setWitnessMsg: Dispatch<SetStateAction<string>>
  witnessEditing: boolean
  setWitnessEditing: Dispatch<SetStateAction<boolean>>
  doAssignWitness: () => void
}) {
  return (<>

      {/* ── Assign a reviewer (F7) — SUPER or org_admin + audited. First assignment is gated on
            readiness (no open queries OR the SLA lapsed); reassign is allowed any time.
            Stage window (`showsReviewerAssignedCard`): hidden at 'shortlisted', where the Reject
            card above takes this slot and assignment is impossible anyway (services.is_assignable),
            and hidden again from 'recommended' onward, where the Recommendation box already names
            the reviewer and this would only add a locked, greyed duplicate. ─── */}
      {canAssign && showsReviewerAssignedCard(app.status) && (() => {
        const ready = app.query_sla?.ready_for_assignment ?? false
        const firstAssignBlocked = !app.assigned_to_id && !ready
        // Once a decision is recorded the reviewer is fixed (it's a finished case) — the
        // dropdown locks. It unlocks again only if a superadmin REOPENS the decision.
        const assignLocked = decisionLocked
        const assigned = !!app.assigned_to_id
        return (
        <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">
            {assigned ? t('admin.scholarship.assign.assignedTitle') : t('admin.scholarship.assignTitle')}
          </h2>
          <select
            value={app.assigned_to_id ?? ''}
            disabled={!!busy || firstAssignBlocked || assignLocked}
            title={assignLocked ? t('admin.scholarship.assign.lockedHint')
              : firstAssignBlocked ? t('admin.scholarship.assign.error.not_ready') : undefined}
            onChange={(e) => doAssign(e.target.value ? Number(e.target.value) : null)}
            className="border rounded-lg px-3 py-2 text-sm w-full disabled:bg-ground-100 disabled:text-ground-placeholder"
          >
            <option value="">{t('admin.scholarship.unassigned')}</option>
            {/* Assignable options. The backend already returns the org-fenced, review-capable set
                (services.REVIEW_ROLES; AdminAssignableAdminsView). A super may pick any of them; a
                non-super (org_admin) delegates only to their own org's reviewers (the assign endpoint
                rejects anything else as bad_assignee). The CURRENT assignee always renders so a later
                role change never hides them (#66: assigned as qc → promoted to org_admin → was
                showing "Unassigned"). Role suffixed so a senior assignee is distinguishable.
                ⚠ A PAUSED reviewer is DISABLED here, not removed — for the same #66 reason, and
                because a name that simply vanishes leaves the reader guessing. The label says why.
                The person already holding the case is never disabled: pause stops NEW work, and
                disabling the current value would make the select unable to show its own state.
                ⚠ A reviewer scoped to ANOTHER GIFT is greyed the same way, with the gift named
                (S-ASSIGN). Same two reasons, and a blank gift on either side greys nobody — it
                means "every gift", which is what all 17 live staff still carry.
                All the rules live in the pure `assignOptions`, where they are tested. */}
            {assignOptions(admins, {
              isSuper,
              currentAssigneeId: app.assigned_to_id,
              applicationProgrammeId: app.programme_id ?? null,
            })
              .map((a) => (
                <option key={a.id} value={a.id} disabled={a.disabled}>
                  {a.name}{a.role !== 'reviewer' ? ` (${a.role})` : ''}
                  {a.reason === 'paused' ? ` — ${t('admin.reviewers.status.paused')}` : ''}
                  {a.reason === 'otherGift'
                    ? ` — ${t('admin.scholarship.assign.coversOtherGift', { gift: a.programmeName })}`
                    : ''}
                </option>
              ))}
          </select>
          {assignLocked ? (
            <p className="text-xs text-ground-400">{t('admin.scholarship.assign.lockedHint')}</p>
          ) : firstAssignBlocked && (
            <p className="text-xs text-caution-700">{t('admin.scholarship.assign.notReadyHint')}</p>
          )}
        </div>
        )
      })()}

      {/* ── Witness organisation — directly below Reviewer assigned (owner 2026-07-22; it used
            to sit full-width BELOW the whole cockpit grid, far from the related controls).
            Three gates, all required:
              • role      — super/admin/org_admin (`canManageSources`; the Admin role manages
                            sources + witnesses, unlike reviewer assignment)
              • sourceless — a student WITH a referring org is witnessed by that org, so the
                            control would be meaningless for them
              • stage     — `showsWitnessCard`: from AWAITING QC onward. Only an AWARDED student
                            signs, but it appears a stage early so the org admin can assign ahead
                            of the award. Never on the off-ramps (rejected/withdrawn/expired).
            Restyled from the old wide card: the column is narrow, so the select + button stack
            full-width instead of sitting side by side, and the chrome matches its siblings. ─── */}
      {witnessCardVisible && (
        <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">
            {t('admin.sources.witness.title')}
          </h2>
          {/* Two states. SETTLED (a witness is on file): name the organisation and say what
              happens next — no picker, no "Assign" button asking for a done thing. PICKING
              (nothing on file yet, or the officer pressed Change): the dropdown + Assign.
              Setting it back to None returns the card to the unassigned invitation. */}
          {app.witness_org && !witnessEditing ? (
            <>
              <p className="text-sm text-ground-700">
                {t('admin.sources.witness.assignedNote', { org: app.witness_org.name })}
              </p>
              <p className="text-xs text-ground-500">{t('admin.sources.witness.assignedNext')}</p>
              <button type="button"
                onClick={() => { setWitnessEditing(true); setWitnessMsg('') }}
                className="text-sm font-medium text-primary-600 hover:text-primary-700 hover:underline">
                {t('admin.sources.witness.change')}
              </button>
            </>
          ) : (
            <>
              <p className="text-xs text-ground-500">
                {app.witness_org
                  ? t('admin.sources.witness.changeHelp')
                  : t('admin.sources.witness.help')}
              </p>
              <select
                className="w-full rounded-lg border border-ground-300 px-3 py-2 text-sm focus:border-info-500 focus:ring-2 focus:ring-info-500"
                value={witnessSel} onChange={(e) => setWitnessSel(e.target.value)}>
                <option value="">{t('admin.sources.witness.none')}</option>
                {activeSources.map((s) => <option key={s.id} value={s.code}>{s.name}</option>)}
              </select>
              <button type="button" onClick={doAssignWitness}
                disabled={witnessBusy || witnessSel === (app.witness_org?.code || '')}
                className="w-full rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {witnessBusy
                  ? t('admin.sources.witness.assigning')
                  : app.witness_org ? t('admin.sources.witness.update') : t('admin.sources.witness.assign')}
              </button>
              {app.witness_org && (
                <button type="button"
                  onClick={() => { setWitnessEditing(false); setWitnessSel(app.witness_org?.code || ''); setWitnessMsg('') }}
                  disabled={witnessBusy}
                  className="w-full rounded-lg border border-ground-300 px-4 py-2 text-sm text-ground-600 hover:bg-ground-50 disabled:opacity-50">
                  {t('common.cancel')}
                </button>
              )}
            </>
          )}
          {witnessMsg && (
            <p className={`text-sm ${witnessMsg === t('admin.sources.witness.assigned') ? 'text-positive-700' : 'text-critical-600'}`}>{witnessMsg}</p>
          )}
        </div>
      )}

  </>)
}
