'use client'

/**
 * THE COCKPIT'S POST-AWARD STATE AND HANDLERS (audit A3.3 — moved out of `view.tsx`, code unchanged):
 * the witness organisation, the bursary agreement, the disbursement ledger and manual closure.
 */
import { useEffect, useState } from 'react'
import {
  getSources, assignWitness, adminCountersignBursary, adminWitnessBursary,
  scheduleTranche, actOnDisbursement, setMaintenanceSubstate, closeApplication,
  type SourceItem, type DisbursementAction, type MaintenanceSubstate, type ClosureReason,
} from '@/lib/admin-api'
import { showsWitnessCard } from '@/lib/officerCockpit'
import { closeErrorKey, stageStatus } from '@/lib/closeOffer'
import { nextSequence } from '@/lib/disbursement'
import type { BursaryAgreement } from '@/lib/api'
import type { CockpitCtx } from './cockpitCtx'

export function usePostAward(ctx: CockpitCtx, canManageSources: boolean) {
  const { id, token, t, app, setApp, setBusy } = ctx

  // Conditional Bursary Award Agreement (flag-gated, dark by default). The admin
  // detail GET does not carry the agreement, so the card's state is populated by
  // the countersign/witness action responses (each returns the full agreement).
  const [bursary, setBursary] = useState<BursaryAgreement | null>(null)
  const [bursaryMsg, setBursaryMsg] = useState('')

  // Witness-organisation assignment (go-live transition, T2). Shown for a SOURCELESS application
  // (no source; sources Sprint C) so a super/org_admin can assign a witness org — usable BEFORE the flag
  // flips (runbook step 2 precedes the flip), so it is NOT gated behind bursary_agreement_enabled.
  const [activeSources, setActiveSources] = useState<SourceItem[]>([])
  const [witnessSel, setWitnessSel] = useState<string>('')
  const [witnessBusy, setWitnessBusy] = useState(false)
  const [witnessMsg, setWitnessMsg] = useState('')
  // Once a witness org is on file the card SETTLES (names the org, no dropdown) — the assign
  // copy would otherwise keep asking for something already done (owner 2026-07-25). Reassigning
  // is still one click away: "Change" flips this back to the picker.
  const [witnessEditing, setWitnessEditing] = useState(false)
  const sourceless = !!app && !app.source
  // Only fetch the organisation list when the witness card can actually render — same three
  // gates as the card itself, so a pre-QC or off-ramp case makes no needless request (most
  // sourceless students today are at 'shortlisted', where the card never appears).
  const witnessCardVisible = canManageSources && sourceless && showsWitnessCard(stageStatus(app, 'active_at'))
  useEffect(() => {
    if (!token || !witnessCardVisible) return
    getSources({ token }).then((d) => setActiveSources(d.sources.filter((s) => s.show_in_apply && s.is_active))).catch(() => {})
  }, [token, witnessCardVisible])
  useEffect(() => { setWitnessSel(app?.witness_org?.code || '') }, [app?.witness_org?.code])

  const doAssignWitness = async () => {
    if (!token || !app) return
    setWitnessBusy(true); setWitnessMsg('')
    try {
      const res = await assignWitness(id, witnessSel || null, { token })
      setApp({ ...app, witness_org: res.witness_org ? { id: 0, code: res.witness_org, name: res.witness_org_name || res.witness_org } : null })
      setWitnessMsg(t('admin.sources.witness.assigned'))
      setWitnessEditing(false)   // settle back to the named-org state
    } catch {
      setWitnessMsg(t('admin.actionFailed'))
    } finally { setWitnessBusy(false) }
  }

  const doCountersignBursary = async () => {
    if (!token) return
    setBusy('bursary'); setBursaryMsg('')
    try {
      setBursary(await adminCountersignBursary(id, { token }))
    } catch (e) {
      setBursaryMsg(t('admin.scholarship.bursary.actionError'))
    } finally { setBusy('') }
  }

  const doWitnessBursary = async () => {
    if (!token) return
    setBusy('bursary'); setBursaryMsg('')
    try {
      setBursary(await adminWitnessBursary(id, undefined, { token }))
    } catch (e) {
      const { status, code = '' } = e as Error & { status?: number; code?: string }  // review L6: say which refusal
      setBursaryMsg(t(status === 403 ? 'admin.scholarship.bursary.witnessForbidden'
        : ['witness_changed', 'no_witness_organisation', 'already_witnessed'].includes(code)
          ? `admin.scholarship.bursary.witnessRefused.${code}` : 'admin.scholarship.bursary.actionError'))
    } finally { setBusy('') }
  }

  // Post-award S4: disbursement (tranche) ledger.
  const [disbAmount, setDisbAmount] = useState('')
  const [disbLabel, setDisbLabel] = useState('')
  const [disbMsg, setDisbMsg] = useState('')

  // The backend raises a machine code as the Error message (adminMutate throws new Error(body.error)).
  const DISB_CODES = new Set(['bad_amount', 'not_in_programme', 'bad_state', 'bad_action', 'bad_sequence', 'on_hold', 'not_in_maintenance', 'bad_substate'])
  const disbError = (e: unknown) => {
    const code = (e as Error)?.message
    return t(`admin.disbursement.error.${code && DISB_CODES.has(code) ? code : 'generic'}`)
  }

  const doScheduleTranche = async () => {
    if (!token) return
    const amount = parseFloat(disbAmount)
    if (!amount || amount <= 0) { setDisbMsg(t('admin.disbursement.error.bad_amount')); return }
    setBusy('disbursement'); setDisbMsg('')
    try {
      const seq = nextSequence(app?.disbursements ?? [])
      setApp(await scheduleTranche(id, { amount, sequence: seq, label: disbLabel.trim() }, { token }))
      setDisbAmount(''); setDisbLabel('')
    } catch (e) {
      setDisbMsg(disbError(e))
    } finally { setBusy('') }
  }

  const doDisbursementAction = async (disbursementId: number, action: DisbursementAction) => {
    if (!token) return
    setBusy('disbursement'); setDisbMsg('')
    try {
      setApp(await actOnDisbursement(disbursementId, action, undefined, { token }))
    } catch (e) {
      setDisbMsg(disbError(e))
    } finally { setBusy('') }
  }

  // Post-award S5: maintenance sub-state (on_track / probation / on_hold / ready_to_close).
  const doSetSubstate = async (substate: MaintenanceSubstate) => {
    if (!token) return
    setBusy('disbursement'); setDisbMsg('')
    try {
      setApp(await setMaintenanceSubstate(id, substate, { token }))
    } catch (e) {
      setDisbMsg(disbError(e))
    } finally { setBusy('') }
  }

  // Manual closure (post-award S6; any in-play status since TD-352).
  const [closeReason, setCloseReason] = useState<ClosureReason | ''>('')
  const [closeMsg, setCloseMsg] = useState('')
  const doClose = async () => {
    if (!token || !closeReason) return
    setBusy('close'); setCloseMsg('')
    try {
      setApp(await closeApplication(id, closeReason, { token }))
      setCloseReason('')
    } catch (e) {
      setCloseMsg(t(closeErrorKey((e as Error)?.message)))
    } finally { setBusy('') }
  }

  return {
    bursary, setBursary, bursaryMsg, doCountersignBursary, doWitnessBursary,
    witnessCardVisible, activeSources, witnessSel, setWitnessSel, witnessBusy, witnessMsg,
    setWitnessMsg, witnessEditing, setWitnessEditing, doAssignWitness,
    disbAmount, setDisbAmount, disbLabel, setDisbLabel, disbMsg,
    doScheduleTranche, doDisbursementAction, doSetSubstate,
    closeReason, setCloseReason, closeMsg, doClose,
  }
}
