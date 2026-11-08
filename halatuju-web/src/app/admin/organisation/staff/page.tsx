'use client'

import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { effectiveRole } from '@/lib/navigation'
import { mayOpen } from '@/lib/pageGuard'
import {
  cancelInvitation, getInvitations, inviteSponsor,
  type AdminItem, type InvitationKind, type InvitationRow, type InvitationsPayload,
} from '@/lib/admin-api'
import {
  MessageBanner, PageHeader, inputCls, useStaffAdmin,
} from '@/components/admin/StaffAdmin'
import InvitationsTable from '@/components/admin/InvitationsTable'
import { FIELD_LABEL, InviteField, InviteFoot } from '@/components/admin/InviteForm'
import PanelTabs from '@/components/admin/PanelTabs'
import InvitationEmailsCard from '@/components/admin/InvitationEmailsCard'
import { GiftTickList } from '@/components/admin/ReviewerGifts'
import {
  EVERY_GIFT, idsToSave, nothingTicked, sponsorStartTicks, type GiftTicks,
} from '@/lib/reviewerGifts'
import { lazySource } from '@/components/source/LazySource'

// The Source tab's form and roster: their own chunk, fetched when the tab is first opened.
const SourceInviteForm = lazySource(
  () => import('@/components/sources/SourceInvite').then((m) => m.SourceInviteForm))
const SourceRoster = lazySource(
  () => import('@/components/sources/SourceInvite').then((m) => m.SourceRoster))
// S7b follow-up: the Mentor tab's form and roster ride the SAME chunk as the Source tab's (re-exported
// by `SourceInvite`) — a chunk of their own would add a runtime entry every route pays for.
const MentorInviteForm = lazySource(
  () => import('@/components/sources/SourceInvite').then((m) => m.MentorInviteForm))
const MentorRoster = lazySource(
  () => import('@/components/sources/SourceInvite').then((m) => m.MentorRoster))

// Team tables T2 (owner ruling 7): Admin, Reviewer, Mentor, Source, Sponsor.
const KINDS: InvitationKind[] = ['admins', 'reviewers', 'mentor', 'source', 'sponsors']

/** The staff roles this page can grant. The SERVER decides which apply to the selected kind
 *  (`invitable_roles`); this type only keeps the invite client honest. */
type StaffRole = 'reviewer' | 'admin'   // T2: "Finance" and "QC" are no longer invited (owner rulings 4, 8)

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
 *
 * ⚠ **SOURCE (source sign-in S2, 2026-10-30)** is its own form and roster
 * (`components/sources/SourceInvite`): pick a source or add a new one, name its person; then who
 * has not replied (Resend / Cancel). Super and org_admin invite; the Sources page's "Invite a
 * source" lands here with `?kind=source`. One person per source (I2, 2026-11-08): a joined source
 * leaves the dropdown, and its person — with Remove — is on the Sources page, not here.
 *
 * ⚠ **MENTOR (student maintenance S7b follow-up, 2026-11-01)** follows the source pattern exactly
 * (`components/mentors/MentorInvite`): name + email, then the mentors who have not signed in yet with
 * the Mentors page's own Resend / Revoke. Shown to super and org_admin only (`mentor_invite.may_invite`);
 * the Mentors page's "Invite a mentor" lands here with `?kind=mentor`.
 *
 * ⚠ **ONE FORM AND ONE WAITING TABLE ON ALL FIVE TABS (I1, 2026-11-08).** Every tab's form wears
 * `admin/InviteForm` (a label above every box, the tab's note under the fields, Send Invite at the
 * left) and every waiting list is `admin/InvitationsTable` — Source and Mentor pass their own Resend /
 * Cancel handlers into it rather than drawing a table of their own.
 */
export default function OrganisationInvitationsPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = effectiveRole(role)
  const canManage = r === 'super' || r === 'org_admin'
  const mayView = mayOpen('/admin/organisation/staff', role)   // T1: with the served tables
  // The Mentor chip only for the roles that may invite a mentor (super, org_admin).
  const kinds = canManage ? KINDS : KINDS.filter((k) => k !== 'mentor')

  const { message, setMessage, busy, busyId, invite, resend } = useStaffAdmin(token)
  // Which SPONSOR row is mid-resend. The staff actions carry their own `busyId` from the hook;
  // a sponsor invitation has no staff account, so it needs its own.
  const [resendingId, setResendingId] = useState<number | null>(null)

  const [panel, setPanel] = useState<'invitations' | 'emails'>('invitations')
  const [kind, setKind] = useState<InvitationKind>('admins')
  const [data, setData] = useState<InvitationsPayload | null>(null)
  const [failedKind, setFailedKind] = useState<InvitationKind | null>(null)
  const [subRole, setSubRole] = useState('')
  const [sName, setSName] = useState('')
  const [sEmail, setSEmail] = useState('')
  const [note, setNote] = useState('')
  // Which gifts a sponsor is invited into (S-ASSIGN, then Invitations I3, 2026-11-08: several, or
  // Every gift). Starts with NOTHING ticked — never a silent default, which is how a Sabah
  // benefactor would otherwise have landed in the flagship — except with exactly ONE gift, which
  // is pre-ticked because there is nothing to choose. With two or more a choice is required.
  const [sGifts, setSGifts] = useState<GiftTicks>(sponsorStartTicks([]))
  const [sGiftMissing, setSGiftMissing] = useState(false)
  // A REVIEWER invite names its gifts (TD-501, A1.3). Multi-gift (owner design, 2026-11-06): a tick
  // list with "Every gift" ticked BY DEFAULT — the owner's ruling replaces A1.3's "must be chosen".
  // Always sent as `programme_ids` (`[]` = every gift), so the server never sees a blank.
  const [rGifts, setRGifts] = useState<GiftTicks>(EVERY_GIFT)

  // The kind on screen NOW: a reply for a kind you have already left (the mount's Admins read, when
  // `?kind=source` switches the tab a moment later) must not land under the new tab.
  const kindNow = useRef(kind)
  kindNow.current = kind
  const load = useCallback(async () => {
    if (!token) return
    try {
      const payload = await getInvitations(kind, { token })
      if (kindNow.current !== kind) return
      setData(payload)
      setFailedKind(null)
      setSubRole((cur) => (payload.invitable_roles.includes(cur)
        ? cur : (payload.invitable_roles[0] || '')))
    } catch {
      // The tab on screen could not be read (review L5): say so, never an empty list that reads as
      // "nobody is waiting".
      if (kindNow.current !== kind) return
      setData(null)
      setFailedKind(kind)
    }
  }, [token, kind])

  useEffect(() => { void load() }, [load])

  // The sponsor ticks start again only when the gift CHOICES change (a new payload with other
  // gifts) — never on the reload after a resend or a cancel, which would wipe a half-made choice.
  const giftKey = (data?.programmes ?? []).map((p) => p.id).join(',')
  useEffect(() => {
    setSGifts(sponsorStartTicks(giftKey ? giftKey.split(',').map(Number).map((id) => ({ id })) : []))
    setSGiftMissing(false)
  }, [giftKey])

  // `?kind=source` (the Sources page's "Invite a source") opens that tab. Read once, on mount, from
  // `window.location` — `useSearchParams` would need a Suspense boundary in a page file.
  useEffect(() => {
    const asked = new URLSearchParams(window.location.search).get('kind')
    // `?kind=mentor` only for the roles that see the Mentor chip; re-read once the role arrives.
    const open = canManage ? KINDS : KINDS.filter((k) => k !== 'mentor')
    if (asked && (open as string[]).includes(asked)) setKind(asked as InvitationKind)
  }, [canManage])

  // The Source tab draws only a Source payload — never the previous tab's rows while its own load.
  const sourceData = data?.kind === 'source' ? data : null
  const mentorData = data?.kind === 'mentor' ? data : null
  /** A Source-tab action finished: say so, and read the tab again. */
  const sourceDone = (banner: Parameters<typeof setMessage>[0]) => { setMessage(banner); void load() }

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    let ok = false
    if (kind === 'sponsors') {
      // I3: with two or more gifts a choice is REQUIRED — nothing is sent until one is made. With
      // one (pre-ticked) or none, nothing ticked sends no gift and the server takes the sole one.
      const choices = data?.programmes ?? []
      if (nothingTicked(sGifts) && choices.length > 1) { setSGiftMissing(true); return }
      try {
        await inviteSponsor({
          email: sEmail, name: sName, note,
          ...(nothingTicked(sGifts) ? {} : { programme_ids: idsToSave(sGifts) }),
        }, { token: token! })
        ok = true
      } catch {
        // Said, never silent: a refused or failed invite must not read as one that went.
        setMessage({ type: 'warning', text: t('admin.invitations.inviteFailed') })
      }
      if (ok) setSGifts(sponsorStartTicks(choices))
    } else {
      const gift = subRole !== 'reviewer' ? {} : { programme_ids: idsToSave(rGifts) }
      ok = await invite({ email: sEmail, name: sName, role: subRole as StaffRole, ...gift })
    }
    if (ok) { setSName(''); setSEmail(''); setNote(''); setRGifts(EVERY_GIFT) }
    void load()
  }

  /** TD-214: withdraw an invitation sent by mistake. Asks first — for a staff invitation it also
   *  switches the never-used account off — and reloads, so the row leaves the waiting list. */
  const cancel = async (row: InvitationRow) => {
    if (!token || !window.confirm(t('admin.invitations.cancelConfirm', { email: row.email }))) return
    setResendingId(row.id)
    try {
      await cancelInvitation(row.id, { token })
      setMessage({ type: 'success', text: t('admin.invitations.cancelled') })
    } catch {
      setMessage({ type: 'warning', text: t('admin.invitations.cancelFailed') })
    } finally {
      setResendingId(null)
      void load()
    }
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
   * ⚠ NO `programme_ids` (nor `programme_id`) EITHER, and that is load-bearing rather than an
   * omission: the server keeps a waiting invitation's gifts when none are named, and replaces them
   * when some are (I3). A resend must not silently re-home a benefactor into whichever gifts the
   * form happens to be showing.
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
  // ⚠ THE TAB IS PART OF THE ANSWER (owner, 2026-09-09). Sent bare, this link dropped an
  // org_admin who had just asked about ADMINS onto the Reviewers tab — a different question.
  const peopleHref = kind === 'sponsors' ? '/admin/sponsors'
    : `/admin/organisation/reviewers?tab=${kind === 'admins' ? 'admins' : 'reviewers'}`
  const emptyWords = total === 0 ? t('admin.invitations.noneInKind') : (
    <>
      {t('admin.invitations.allAccepted')}{' '}
      <Link href={peopleHref} className="font-medium text-primary-600 hover:text-primary-800">
        {t(kind === 'sponsors' ? 'admin.invitations.seeSponsors' : 'admin.invitations.seePeople')}
      </Link>
    </>
  )
  const giftChoices = data?.programmes ?? []
  // TD-501 (A1.3 review): the server's own list for the organisation the invite binds to, so a
  // super is never offered a gift that the invite would then refuse.
  const reviewerGiftChoices = data?.reviewer_programmes ?? []
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
          <div className={`grid grid-cols-2 gap-2 ${kinds.length > 4 ? 'max-w-2xl sm:grid-cols-5' : 'max-w-xl sm:grid-cols-4'}`}>
            {kinds.map((k) => {
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
            // Source sign-in S2: inviting a source's person IS how a source is added now.
            canManage && <SourceInviteForm data={sourceData} token={token} t={t} onDone={sourceDone} />
          ) : kind === 'mentor' ? (
            canManage && <MentorInviteForm token={token} t={t} onDone={sourceDone}
              options={mentorData?.mentor_programmes ?? []} />
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
                <InviteField label={t('admin.name')}>
                  <input className={inputCls} value={sName}
                    onChange={(e) => setSName(e.target.value)} required />
                </InviteField>
                <InviteField label={t('admin.emailLabel')}>
                  <input className={inputCls} type="email"
                    value={sEmail} onChange={(e) => setSEmail(e.target.value)} required />
                </InviteField>
              </div>
              {/* I3 (owner ruling 1): the reviewer's tick list, ALWAYS shown — several gifts, or
                  Every gift (= every gift open when they register; one pending request per gift,
                  each approved on its own). Nothing ticked to start (one gift: pre-ticked); with
                  two or more the form will not send until a choice is made. */}
              {kind === 'sponsors' && (
                <div className="text-sm" role="group" aria-labelledby="invite-sponsor-gift-label">
                  <span id="invite-sponsor-gift-label" className={FIELD_LABEL}>
                    {t('admin.invitations.sponsorGiftLabel')}
                  </span>
                  <div className={`rounded-lg border px-2 py-1 ${
                    sGiftMissing ? 'border-critical-600' : 'border-ground-300'}`}>
                    <GiftTickList ticks={sGifts} options={giftChoices} allowNone
                      onChange={(next) => { setSGifts(next); setSGiftMissing(false) }}
                      everyLabel={t('admin.invitations.reviewerGiftEvery')} testId="invite-sponsor-gift" />
                  </div>
                  {sGiftMissing && (
                    <p role="alert" className="mt-1 text-xs text-critical-600">
                      {t('admin.invitations.sponsorGiftRequired')}
                    </p>
                  )}
                </div>
              )}
              {kind !== 'sponsors' && subRole === 'reviewer' && (
                <div className="text-sm" role="group" aria-labelledby="invite-reviewer-gift-label">
                  <span id="invite-reviewer-gift-label" className={FIELD_LABEL}>
                    {t('admin.invitations.reviewerGiftLabel')}
                  </span>
                  <div className="rounded-lg border border-ground-300 px-2 py-1">
                    <GiftTickList ticks={rGifts} options={reviewerGiftChoices} onChange={setRGifts}
                      everyLabel={t('admin.invitations.reviewerGiftEvery')} testId="invite-reviewer-gift" />
                  </div>
                </div>
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
                <InviteField label={t('admin.invitations.noteLabel')}>
                  <textarea className={inputCls} rows={3}
                    placeholder={t('admin.invitations.notePlaceholder')}
                    value={note} onChange={(e) => setNote(e.target.value)} />
                </InviteField>
              )}
              {/* I1: the tab's note sits UNDER the fields, then Send Invite at the left. Admin's says
                  where an Admin starts (T2, owner ruling 4: one Admin, at the minimum); Reviewer's is
                  the gift help; Sponsor's (I3) says each gift is its own request. */}
              <InviteFoot busy={busy} label={t('admin.sendInvite')}
                note={kind === 'admins' ? t('admin.team.inviteAdminNote')
                  : kind === 'sponsors' ? t('admin.invitations.sponsorGiftHelp')
                  : subRole === 'reviewer' ? t('admin.invitations.reviewerGiftHelp')
                  : undefined} />
            </form>
          ) : null}
        </div>

        {/* ⚠ THE HEADING NAMES THE STATE, NOT THE KIND (2026-09-09). Which kind you are looking at
            is already said by the pressed button above; what the table holds is no longer "the
            reviewers" but "the reviewers who have not answered", and a heading reading "Reviewers
            (0)" over a settled organisation says the opposite of the truth. */}
        {failedKind === kind ? (
          <p role="alert" data-testid="invitations-load-failed"
            className="rounded-lg border border-critical-200 bg-critical-50 p-4 text-sm text-critical-600">
            {t('admin.invitations.loadFailed')}
          </p>
        ) : kind === 'source' ? (
          <SourceRoster data={sourceData} token={token} t={t} canManage={canManage}
            onCancel={(row) => { void cancel(row) }} onDone={sourceDone} />
        ) : kind === 'mentor' ? (
          <MentorRoster data={mentorData} token={token} t={t} canManage={canManage} onDone={sourceDone} />
        ) : (<>
        <h2 className="mb-2 text-sm font-semibold text-ground-900">
          {t('admin.invitations.waitingHeading')}{' '}
          <span className="font-normal text-ground-400">({rows.length})</span>
        </h2>
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
            onCancel={canManage ? (row: InvitationRow) => { void cancel(row) } : undefined}
            /* An org_admin cancels only what this page lets them invite (`invitable_roles`) —
               never an organisation admin's invitation; a sponsor row carries no role. A super
               cancels any. The server holds the same rule (404). */
            canCancel={(row: InvitationRow) =>
              r === 'super' || !row.role || (data?.cancellable_roles ?? invitable).includes(row.role)}
            empty={emptyWords}
          />
        </>)}
        {!canManage && (
          <p className="mt-3 text-sm text-ground-500">{t('admin.administration.viewOnlyNote')}</p>
        )}
      </>)}
    </div>
  )
}
