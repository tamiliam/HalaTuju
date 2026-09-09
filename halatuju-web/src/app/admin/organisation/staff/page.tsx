'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import {
  getInvitations, inviteSponsor,
  type AdminItem, type InvitationKind, type InvitationRow, type InvitationsPayload,
} from '@/lib/admin-api'
import {
  MessageBanner, PageHeader, inputCls, useStaffAdmin,
} from '@/components/admin/StaffAdmin'
import InvitationsTable from '@/components/admin/InvitationsTable'
import PanelTabs from '@/components/admin/PanelTabs'
import InvitationEmailsCard from '@/components/admin/InvitationEmailsCard'

const KINDS: InvitationKind[] = ['admins', 'reviewers', 'source', 'sponsors']

/** The staff roles this page can grant. The SERVER decides which apply to the selected kind
 *  (`invitable_roles`); this type only keeps the invite client honest. */
type StaffRole = 'reviewer' | 'admin' | 'qc' | 'finance'

/** The staff row behind an invitation, for the two actions that act on the ACCOUNT rather than on
 *  the invitation. Only `id` and `is_active` are read; guarded by `admin_id` at every call site. */
const asStaffRow = (row: InvitationRow) =>
  ({ id: row.admin_id as number, is_active: row.is_active ?? true } as AdminItem)

/**
 * Organisation → **Invitations**. Who has been asked and **has not answered yet**.
 *
 * Owner's shape, 2026-08-03. FOUR kinds — admins, reviewers, source, sponsors — with **one table
 * on screen at a time**, chosen by the same buttons that decide what you are inviting.
 *
 * ⚠ **IT LISTS THE WAITING ONES ONLY (owner, 2026-09-09), AND THAT IS WHAT THE PAGE IS FOR.** It
 * used to list every invitation ever sent, so it drifted into being a staff roster: on this tenant
 * 18 of its 20 rows were accepted, the 13 reviewers duplicated the Reviewers page exactly, and it
 * would have got worse on its own as each waiting sponsor registered. Who is already in is now
 * answered in ONE place — Organisation → **People** — which is also where Revoke and Restore went.
 * The server does the filtering (`invitations.open_only`), so this page and the badge on each
 * button cannot disagree.
 *
 * ⚠ **THE WAITING COUNT ON EACH BUTTON IS LOAD-BEARING, not decoration.** Only one table is
 * visible, so an unanswered invitation under a kind you are not looking at would be invisible —
 * which is the exact failure this page exists to end.
 *
 * ⚠ **INVITABLE HERE ≠ LISTED HERE.** `org_admin` appears in the Admins table (an organisation
 * admin is an admin) but is never offered in the selector: appointing one is a platform act a super
 * performs. The server sends `invitable_roles`; this page does not keep its own copy.
 *
 * ⚠ **A SPONSOR INVITATION CREATES NOTHING.** It emails a link to the ordinary public registration,
 * where they consent, sign the terms and are vetted like anybody else — the owner's constraint,
 * "invite, but nothing is skipped". The peer-to-peer route (a sponsor inviting a sponsor) is
 * deliberately NOT shown here; it lives on the sponsor's own account page.
 *
 * ⚠ Sponsors never see any of this. They sign in through their own stack and see `/sponsor/*`.
 */
export default function OrganisationInvitationsPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = effectiveRole(role)
  const canManage = r === 'super' || r === 'org_admin'
  const mayView = canAccess('/admin/organisation/staff', r)

  const { message, setMessage, busy, busyId, invite, resend } = useStaffAdmin(token)
  // Which SPONSOR row is mid-resend. The staff actions carry their own `busyId` from the hook;
  // a sponsor invitation has no staff account, so it needs its own.
  const [resendingId, setResendingId] = useState<number | null>(null)

  const [panel, setPanel] = useState<'invitations' | 'emails'>('invitations')
  const [kind, setKind] = useState<InvitationKind>('admins')
  const [data, setData] = useState<InvitationsPayload | null>(null)
  const [subRole, setSubRole] = useState('')
  const [sName, setSName] = useState('')
  const [sEmail, setSEmail] = useState('')
  const [note, setNote] = useState('')
  // Which gift a sponsor is being invited into (S-ASSIGN). Starts BLANK and stays blank — the
  // picker only appears when there is a real choice, and it must never default to one. Until
  // now this form never asked, so a benefactor invited for Sabah would have registered
  // straight into the flagship, silently.
  const [sProgramme, setSProgramme] = useState('')

  const load = useCallback(async () => {
    if (!token) return
    try {
      const payload = await getInvitations(kind, { token })
      setData(payload)
      setSubRole((cur) => (payload.invitable_roles.includes(cur)
        ? cur : (payload.invitable_roles[0] || '')))
    } catch { setData(null) }
  }, [token, kind])

  useEffect(() => { void load() }, [load])

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    let ok = false
    if (kind === 'sponsors') {
      try {
        // Omitted when blank, which is the ONE-GIFT case: the server takes the organisation's
        // sole active gift. With several it refuses `programme_required` rather than picking,
        // and the picker below is `required` so the form never reaches that refusal.
        await inviteSponsor({
          email: sEmail, name: sName, note,
          ...(sProgramme ? { programme_id: Number(sProgramme) } : {}),
        }, { token: token! })
        ok = true
      } catch { ok = false }
    } else {
      ok = await invite({ email: sEmail, name: sName, role: subRole as StaffRole })
    }
    if (ok) { setSName(''); setSEmail(''); setNote(''); setSProgramme('') }
    void load()
  }

  /**
   * Send a DONOR their invitation again (BrightPath #16).
   *
   * ⚠ THERE IS NO SEPARATE RESEND ENDPOINT AND THERE SHOULD NOT BE. `create_or_refresh` is
   * idempotent on an open invitation to the same address: inviting again finds the existing row,
   * moves its expiry, sends the letter and records whether it went. That is a resend, and it is
   * what typing the address into the form above already did. Until now the Resend link on a donor
   * row was drawn and wired to nothing — it checked for a staff account, found none, and returned
   * in silence, which is why the owner could not tell whether it had worked.
   *
   * ⚠ NO NOTE IS SENT, BY DECISION (owner, 2026-09-08). The personal note is used once at send
   * time and is not stored — there is no column for it — so a resend cannot repeat it. Passing
   * nothing is the honest option; the letter stands on its own. Storing it would be a migration,
   * which is more than this is worth.
   *
   * ⚠ NO `programme_id` EITHER, and that is load-bearing rather than an omission: `create_or_refresh`
   * leaves the existing gift alone when none is named, and overwrites it when one is. A resend must
   * not silently re-home a benefactor into whichever gift the form happens to be showing.
   */
  const resendSponsor = async (row: InvitationRow) => {
    if (!token) return
    setResendingId(row.id)
    setMessage(null)
    try {
      await inviteSponsor({ email: row.email, name: row.name }, { token })
      setMessage({ type: 'success', text: t('admin.invitations.resent') })
    } catch {
      // The endpoint answers 502 when the letter did not go, and records the reason on the row —
      // so the banner says it failed and the reloaded row says why. Both, not one.
      setMessage({ type: 'warning', text: t('admin.invitations.resendFailed') })
    } finally {
      setResendingId(null)
      void load()
    }
  }

  const rows = data?.invitations ?? []
  const waiting = data?.waiting
  const invitable = data?.invitable_roles ?? []

  /**
   * What an empty table means — and it is TWO different things, which is why the server sends
   * `totals` beside `waiting`.
   *
   * ⚠ **AN EMPTY TABLE IS THE NORMAL STATE HERE, so these words are the page.** The table lists
   * only unanswered invitations; on a settled organisation three of the four kinds are empty every
   * day. The old sentence — "Nobody has been invited in this group yet" — would have been printed
   * over thirteen reviewers who had all accepted, which is not a smaller truth but the opposite
   * one. The second case earns a route to where those people actually are.
   */
  const total = data?.totals?.[kind] ?? 0
  const peopleHref = kind === 'sponsors' ? '/admin/sponsors' : '/admin/organisation/reviewers'
  const emptyWords = total === 0 ? t('admin.invitations.noneInKind') : (
    <>
      {t('admin.invitations.allAccepted')}{' '}
      <Link href={peopleHref} className="font-medium text-primary-600 hover:text-primary-800">
        {t(kind === 'sponsors' ? 'admin.invitations.seeSponsors' : 'admin.invitations.seePeople')}
      </Link>
    </>
  )
  const giftChoices = data?.programmes ?? []
  const canInviteHere = canManage && (kind === 'sponsors' || invitable.length > 0)

  return (
    <div>
      <PageHeader title={t('admin.invitations.title')} subtitle={t('admin.invitations.subtitle')} />

      {/* The same bar every organisation surface wears — one component, so they cannot drift. */}
      <PanelTabs ariaLabelKey="admin.invitations.tabsAria" active={panel} onSelect={setPanel}
        tabs={[
          { key: 'invitations', labelKey: 'admin.invitations.tab.invitations' },
          { key: 'emails', labelKey: 'admin.invitations.tab.emails' },
        ]} />

      <MessageBanner message={message} />

      {panel === 'emails' && <InvitationEmailsCard token={token} t={t} />}

      {panel === 'invitations' && (<>
        <div className="mb-6 rounded-xl border bg-ground-0 p-6 shadow-sm">
          <p className="mb-2 text-sm font-semibold text-ground-900">{t('admin.inviteAs')}</p>
          <div className="grid max-w-xl grid-cols-2 gap-2 sm:grid-cols-4">
            {KINDS.map((k) => {
              const n = waiting?.[k] ?? 0
              return (
                <button key={k} type="button" onClick={() => setKind(k)}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                    kind === k ? 'border-primary-600 bg-brand-fill text-brand-fill-ink'
                               : 'border-ground-300 bg-ground-0 text-ground-700 hover:bg-ground-50'}`}>
                  {/* ⚠ SINGULAR here, PLURAL on the table heading below (owner, 2026-08-04). The
                      sentence being completed is "Invite as … Admin"; the heading sits above a
                      list of them. One key cannot be right in both places, so there are two. */}
                  {t(`admin.invitations.kindOne.${k}`)}
                  {/* The waiting badge — see the ⚠ in the docblock. */}
                  {n > 0 && (
                    <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-[11px] ${
                      kind === k ? 'bg-ground-0/25 text-white' : 'bg-info-100 text-info-700'}`}>
                      {n}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {kind === 'source' ? (
            <p className="mt-4 text-sm text-ground-500">{t('admin.invitations.sourceComingSoon')}</p>
          ) : canInviteHere ? (
            <form onSubmit={submit} className="mt-4 space-y-4">
              {invitable.length > 1 && (
                <div className="flex flex-wrap gap-2">
                  {invitable.map((role_) => (
                    <button key={role_} type="button" onClick={() => setSubRole(role_)}
                      className={`rounded-full border px-3 py-1 text-xs font-medium ${
                        subRole === role_ ? 'border-primary-600 bg-primary-50 text-primary-700'
                                          : 'border-ground-300 bg-ground-0 text-ground-600'}`}>
                      {t(`admin.administration.staffRole.${role_}`)}
                    </button>
                  ))}
                </div>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                <input className={inputCls} placeholder={t('admin.name')} value={sName}
                  onChange={(e) => setSName(e.target.value)} required />
                <input className={inputCls} type="email" placeholder={t('admin.emailLabel')}
                  value={sEmail} onChange={(e) => setSEmail(e.target.value)} required />
              </div>
              {/* ⚠ ONE GIFT ASKS NOTHING. The picker appears only when the organisation runs
                  more than one, so the form is unchanged for BrightPath today. With several it
                  is REQUIRED and starts blank — never a silent default, which is exactly how a
                  Sabah benefactor would otherwise have landed in the flagship. */}
              {kind === 'sponsors' && giftChoices.length > 1 && (
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-ground-700">
                    {t('admin.invitations.giftLabel')}
                  </span>
                  <select className={inputCls} value={sProgramme} required
                    onChange={(e) => setSProgramme(e.target.value)}>
                    <option value="">{t('admin.invitations.giftChoose')}</option>
                    {giftChoices.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </label>
              )}
              {/* ⚠ A TEXTAREA, NOT AN INPUT, AND THE REASON IS NOT COSMETIC (BrightPath #17).
                  Enter inside a single-line box submits the form it sits in — that is the
                  browser's own behaviour, not anything this page asked for — so the main action
                  fired, and the main action here SENDS AN INVITATION TO A DONOR. Somebody
                  starting a second line posted a half-written note to an outsider, with no way
                  to take it back. In a textarea Enter is a new line and only the button sends.
                  A rendered test presses Enter in this box and asserts nothing was sent; do not
                  "tidy" this back to an <input> to match the two above it. The email carries the
                  line breaks through — it is plain text, and a backend test pins that. */}
              {kind === 'sponsors' && (
                <textarea className={inputCls} rows={3}
                  placeholder={t('admin.invitations.notePlaceholder')}
                  value={note} onChange={(e) => setNote(e.target.value)} />
              )}
              <button type="submit" disabled={busy}
                className="rounded-lg bg-brand-fill px-6 py-2.5 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('admin.sendInvite')}
              </button>
            </form>
          ) : null}
        </div>

        {/* ⚠ THE HEADING NAMES THE STATE, NOT THE KIND (2026-09-09). Which kind you are looking at
            is already said by the pressed button above; what the table holds is no longer "the
            reviewers" but "the reviewers who have not answered", and a heading reading "Reviewers
            (0)" over a settled organisation says the opposite of the truth. */}
        <h2 className="mb-2 text-sm font-semibold text-ground-900">
          {t('admin.invitations.waitingHeading')}{' '}
          <span className="font-normal text-ground-400">({rows.length})</span>
        </h2>
        {kind === 'source' ? (
          <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500">
            {t('admin.invitations.sourceComingSoon')}
          </div>
        ) : (
          <InvitationsTable
            rows={rows} canAct={canManage} busyId={busyId ?? resendingId}
            /* ⚠ ONLY THE STAFF KINDS CARRY A ROLE. Admins holds Admin · Finance · Org admin and
               Reviewers holds Reviewer · QC, so the column separates things there. A sponsor
               invitation creates no account and has no role, so on that table the column could
               only ever print a dash for every row — which reads as a value we failed to fetch.
               Named by KIND, never derived from the rows: a staff row arriving with a blank role
               is a missing value to show, not a column to drop. */
            showRole={kind === 'admins' || kind === 'reviewers'}
            /* `resend` acts on the ACCOUNT, so it takes the staff row behind the invitation.
               ⚠ REVOKE USED TO SIT BESIDE IT AND HAS MOVED to Organisation → People, beside
               Pause: this table now holds only people who have NOT arrived, and revoking is
               something you do to somebody who has. */
            /* ⚠ TWO KINDS OF RESEND BEHIND ONE LINK, and the fork is the account. A STAFF
               invitation resends through the account (it also rotates the temporary password, so
               it must go through `resend`); a DONOR invitation has no account and resends by
               re-issuing the invitation itself. Before #16 only the first arm existed, so the
               link on a donor row fell off the end of an `if` and did nothing at all. */
            onResend={canManage ? (row: InvitationRow) => {
              if (row.admin_id) void resend(asStaffRow(row)).then(load)
              else void resendSponsor(row)
            } : undefined}
            empty={emptyWords}
          />
        )}
        {!canManage && (
          <p className="mt-3 text-sm text-ground-500">{t('admin.administration.viewOnlyNote')}</p>
        )}
      </>)}
    </div>
  )
}
