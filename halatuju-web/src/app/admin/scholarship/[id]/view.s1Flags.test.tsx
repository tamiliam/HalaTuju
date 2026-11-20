/**
 * @jest-environment jsdom
 *
 * ACCESS S1 (TD-664 a-c) — SERVE, NEVER DERIVE. The cockpit draws three more controls from flags the server
 * computes with the same function its door asks (`views_admin.base.served_write_flags`), and never from the
 * role:
 *
 *  * the QC panel and the Re-verify IC card follow `can_qc` (the key `_require_qc` reads) — a role that names
 *    QC with the flag false gets neither; a role that does not with the flag true gets both;
 *  * the self-QC note reads only the served `qc_refusal` (`qcRefusalFor` keeps no local copy of the rule);
 *  * the pre-award Close card follows `can_close_pre_award` (the close door's own pre-award answer).
 *
 * The case stage (`case_stage`) and the phone's decision bar are pinned in `view.decisionBar.test.tsx`.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit, ASSIGNED_ADMIN_ID } from '@/test/renderCockpit'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'
import { qcRefusalFor } from './view/QcPanel'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const qcPanel = () => screen.queryByText('admin.scholarship.qcDecision.title')
const closeCard = () => screen.queryByText('admin.closure.title')
const RULED = { kind: 'state' as const, state: 'selangor', code: '10', label: 'Born in: Selangor (IC code 10)',
  meets_rule: true, warning: '' }

describe('the QC panel and the Re-verify IC card follow the served can_qc', () => {
  it.each([
    ['qc', false, false],
    ['org_admin', false, false],
    ['reviewer', true, true],
    ['admin', true, true],
  ] as const)('%s with can_qc=%s: the panel shows=%s', async (role, canQc, shows) => {
    renderCockpit({ role, adminId: 43, writes: { can_qc: canQc }, stage: 'awaiting_qc',
      build: { outcome: 'recommend', nric_verified: false, birth_state: RULED } })
    await loaded()
    expect(!!qcPanel()).toBe(shows)
    expect(!!screen.queryByTestId('reverify-ic')).toBe(shows)
  })
})

describe('the self-QC note reads only the served qc_refusal', () => {
  it('qcRefusalFor answers what the server sent, and nothing else', () => {
    const at = (fields: object) => buildApplicationDetail('awaiting_qc', { outcome: 'recommend', ...fields })
    expect(qcRefusalFor(at({ qc_refusal: 'self_verdict_qc_forbidden' }))).toBe('self_verdict_qc_forbidden')
    expect(qcRefusalFor(at({ qc_refusal: null }))).toBeNull()
    // The case is held by the viewer's own id, yet no answer came: no local guess is made.
    expect(qcRefusalFor(at({ assigned_to_id: ASSIGNED_ADMIN_ID }))).toBeNull()
  })

  it('a QC the server refuses sees its note; the same QC with no refusal sees the panel', async () => {
    const view = renderCockpit({ role: 'qc', adminId: ASSIGNED_ADMIN_ID, writes: { can_qc: true },
      stage: 'awaiting_qc', build: { outcome: 'recommend', qc_refusal: 'self_assigned_qc_forbidden' } })
    await loaded()
    expect(screen.getByTestId('qc-refusal').textContent)
      .toBe('admin.scholarship.qcDecision.refusal.self_assigned_qc_forbidden')
    expect(qcPanel()).toBeNull()
    view.unmount()
    renderCockpit({ role: 'qc', adminId: ASSIGNED_ADMIN_ID, writes: { can_qc: true },
      stage: 'awaiting_qc', build: { outcome: 'recommend', qc_refusal: null } })
    await loaded()
    expect(screen.queryByTestId('qc-refusal')).toBeNull()
    expect(qcPanel()).toBeTruthy()
  })
})

describe('the pre-award Close card follows the served can_close_pre_award', () => {
  it.each([
    ['qc', true, true],
    ['reviewer', true, true],
    ['org_admin', false, false],
    ['super', false, false],
  ] as const)('%s with can_close_pre_award=%s: the card shows=%s', async (role, flag, shows) => {
    renderCockpit({ role, writes: { can_write: true, can_close_pre_award: flag }, stage: 'submitted' })
    await loaded()
    expect(!!closeCard()).toBe(shows)
  })
})
