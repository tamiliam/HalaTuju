'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useLatest } from '@/lib/useLatest'
import TableFrame from '@/components/admin/TableFrame'
import PanelTabs from '@/components/admin/PanelTabs'
import {
  listReviewers, type AdminItem, type AdminReviewer,
} from '@/lib/admin-api'
import { effectiveRole } from '@/lib/navigation'
import { mayOpen, mayReadMentors } from '@/lib/pageGuard'
import { lazySource } from '@/components/source/LazySource'
import { turnaroundBand } from '@/lib/reviewerDetail'
import {
  DEFAULT_SORT, REVIEWER_SORT_LABEL, firstDirFor, sortReviewers,
  type ReviewerSortKey,
} from '@/lib/reviewerTable'
import { PAGE_SIZE_OPTIONS, nextSort } from '@/lib/tableView'
import SortHeader from '@/components/admin/SortHeader'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import { Pagination } from '@/components/Pagination'
import TeamEmails, { TeamTerms } from '@/components/admin/TeamEmails'
import { formatDate } from '@/lib/formatDate'
import { roleBadgeClass } from '@/lib/roleBadge'
import { STAFF_STATUS_TONE, staffStatusKey } from '@/lib/staffStatus'
import { PHONE_PILL_SM } from '@/lib/phonePill'   // pills on a phone (Mobile M8)
import { byCategory } from '@/lib/adminStaff'
import { MessageBanner, StaffTable, useStaffAdmin } from '@/components/admin/StaffAdmin'
import { AlsoIn, RemoveControl, TeamAddSheet, TeamRemoveSheet } from '@/components/admin/TeamTables'
import type { TeamTableName } from '@/lib/admin-api'
import StaffAvatar from '@/components/admin/StaffAvatar'
import { TEAM_ROLES } from '@/lib/staffPermissions'

// Organisation → **People**: the directory of everybody who is already in.
//
// It began as the reviewers directory (request #10) — "Invitations invites; this is where you LOOK
// at somebody before handing them the next case" — and on 2026-09-09 it took the **Admins** tab as
// well, closing the two faults the owner reported:
//   * the 13 reviewers were listed HERE and on Invitations, identically, and
//   * the 5 admins had no directory at all, so their only home was a page about asking.
// The two tabs are the owner's own split, recorded in `adminStaff.ts` on 2026-08-03: *"There are
// two categories of people here: reviewers and admins. QC is a reviewer as well. And finance is
// also an admin."* Same two categories the Invitations page groups by, so nobody has to learn a
// second vocabulary.
//
// ⚠ **SUSPEND (REVOKE) AND RESTORE LIVE ON THE STAFF TAB, not on Invitations** — and, since M1b (owner O3),
// not on the group tables either: Staff holds Suspend / Restore and Delete; Admins, Reviewers and Mentors
// keep Add and Remove (O4).
//
// The reviewers table stays sorted by open caseload, because "who can take this case?" is asked daily.
//
// A corrections count is deliberately absent and must stay absent unless the owner says
// otherwise: it reads as a competence score, and the reopens live on the detail page WITH their
// reasons.
//
// ⚠ THE GIFT WAS ABSENT FOR THE SAME KIND OF REASON AND IS NOW CONDITIONAL (S-ASSIGN,
// 2026-09-04). Owner, 2026-08-02: "with one programme it could only ever say one thing". That
// is still true of a one-gift organisation, so it renders only above one gift — the ruling is
// honoured rather than reversed. It is a line under the name, not a column: inventing a sort
// key and a header for a fact most organisations never see is furniture.
//
// Multi-gift tagging (owner design, 2026-11-06) made the line chips with an edit pencil.
//
// ⚠ GIFTS AND LANGUAGES ARE NOT ON THIS TABLE (owner, 2026-11-07): both are shown on the reviewer's
// own page, and the gifts are edited there (`[id]/page.tsx`, `ReviewerGiftsCell`), never from the
// table. Do not add either back as a column or a line under the name.

// A caseload figure: grey at zero (normal, never a flag), bold otherwise.
/** Whose name opens the person page on the Admins table: the team roles and (O10) the organisation admin. */
const PERSON_PAGE_ROLES = [...TEAM_ROLES, 'org_admin'] as const
const figureTone = (n: number) => (n === 0 ? 'text-ground-400' : 'font-semibold text-ground-900')


// Team tables T3: Team -> Mentors — the old Mentors page's chunk (one chunk for the table and the mentor
// detail page; no new entry in the webpack runtime every route downloads).
const TeamMentors = lazySource(() => import('@/components/mentors/MentorsAdmin').then((m) => m.default))
// Sprint M1b: Team -> Staff, the first tab and the default — in the console's shared `'ad'` chunk (the
// greyed-button tip and the person pages are there already), so no new entry in the webpack runtime every
// route downloads. Suspend and Delete live there ONLY (owner O3); the group tables keep Add and Remove (O4).
const StaffList = lazySource(() =>
  import(/* webpackChunkName: 'ad' */ '@/components/admin/StaffList').then((m) => m.default))

export default function AdminReviewersList() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  // UX only — the endpoint is the fence. This just avoids rendering a table that would 403.
  const mayView = mayOpen('/admin/organisation/reviewers', role)   // T1: with the served tables
  // The same pill idiom the Sponsors and Sources screens use, so the console has one way of doing
  // this. Reviewers is the default: "who can take this case?" is the daily question, and both
  // "who still has access?" and "what are volunteers told?" are deliberate second clicks.
  // ⚠ THE TAB IS IN THE URL because another page links straight to one. The Invitations empty
  // state says "everyone invited has accepted — see who is in", and under the ADMINS kind that
  // link must land on the Admins tab; without this it dropped you on Reviewers, which is a
  // different answer to the question you asked (owner, 2026-09-09).
  const search = useSearchParams()
  const asked = search?.get('tab')
  // Team tables T2 (owner ruling 1): Admins · Reviewers · Mentors · Emails · Terms. M1b: Staff comes first
  // and is the tab you land on (`?tab=staff`); `?tab=` opens any other.
  type Panel = 'staff' | 'admins' | 'reviewers' | 'mentors' | 'emails' | 'terms'
  const [panel, setPanel] = useState<Panel>(
    asked === 'admins' || asked === 'mentors' || asked === 'reviewers' ? asked : 'staff')
  // Editing what every reviewer is told is an editorial power, not a reading one — so the tab is
  // offered to the roles the endpoint admits and not to `finance`, which may read the list. The
  // endpoint is the authority; this only avoids offering a 403.
  const mayEditEmails = ['super', 'org_admin', 'admin'].includes(effectiveRole(role))
  // T3: the Mentors tab — exactly who read the old Mentors page (the server's `mentor_invite.may_read`).
  const mayMentors = mayReadMentors(role)
  // ⚠ THE SAME GATE REVOKE HAD ON INVITATIONS, moved with the control and not widened: only a
  // super or an organisation admin may switch somebody off. `admin` and `finance` still READ the
  // tab — the endpoint is the authority, and `soleOrgAdmin` keeps the last org_admin's Revoke off
  // the screen because the backend refuses it anyway.
  const canManage = ['super', 'org_admin'].includes(effectiveRole(role))
  const { admins, message: staffMessage, setMessage: setStaffMessage, busyId: staffBusyId,
          resend, soleOrgAdmin, reload: reloadStaff } = useStaffAdmin(token)
  const viewerSuper = effectiveRole(role) === 'super'
  // ⚠ A TEAM MEMBER'S PERMISSIONS LIVE ON THEIR OWN PAGE (2026-10-22, owner's option A). The
  // Admins tab used to open the card above this list; now the NAME opens the person's page, which
  // has a Permissions tab — the same place a reviewer's are. Only where the viewer may manage, and
  // only for a team member who is not revoked. O10 (owner, 2026-11-10): the organisation admin's name
  // opens their page too, as every other admin's does. M1b: an organisation admin may now READ a fellow
  // organisation admin's page (and their own) — the page draws it read-only, no action — so their row links
  // whatever `manageable` says. Any other row still links only where it is manageable.
  const personHref = (a: AdminItem) =>
    a.is_active && (a.role === 'org_admin' || a.manageable !== false)
      && (PERSON_PAGE_ROLES as readonly string[]).includes(a.role)
      ? `/admin/organisation/reviewers/admins/${a.id}` : null
  // T3 (owner): no permission column on the Team tables — permissions are set only on the person's own
  // page, Permissions tab (one section per table they sit in). The NAME opens it, as before.
  // T2: the Add sheet (which table) and the Remove confirm (who, from which table).
  const [adding, setAdding] = useState<TeamTableName | null>(null)
  // Add Mentor's sheet lives in the Mentors chunk; its button is on the tab row with the other two.
  const [addingMentor, setAddingMentor] = useState(false)
  const [removing, setRemoving] = useState<{ id: number; name: string; table: TeamTableName; toNoGroup?: boolean } | null>(null)
  const teamDone = (text: string) => {
    setAdding(null); setRemoving(null)
    setStaffMessage({ type: 'success', text })
    reloadStaff(); load()
  }
  const [reviewers, setReviewers] = useState<AdminReviewer[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const { sort, setSort } = useSort<ReviewerSortKey>(DEFAULT_SORT)

  const tRef = useLatest(t)   // read inside the loader so a language switch does not re-run it
  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    listReviewers({ token })
      .then((d) => setReviewers(d.reviewers))
      .catch(() => setError(tRef.current('admin.reviewers.loadFailed')))
      .finally(() => setLoading(false))
  }, [token, tRef])

  useEffect(() => { load() }, [load])

  // Sort the whole list, then page the sorted result — the other order would sort one page at a
  // time and shuffle rows between pages.
  const sorted = sortReviewers(reviewers, sort.key, sort.dir)
  // T2: the Admins table's rows — by the served `tables` for anyone active, by the old label for a
  // revoked person (who sits at no table but must keep their Restore), and by the label for a payload
  // from before T2 (no `tables`).
  const adminRows = byCategory(admins).reviewers.concat(byCategory(admins).admins).filter((a) =>
    a.is_active && a.tables ? a.tables.includes('admins')
      : byCategory([a]).admins.length > 0)
    .sort((x, y) => admins.indexOf(x) - admins.indexOf(y))
  // The organisation admin's line on the Reviewers table (owner ruling 5: never QC what they reviewed).
  const leadNote = (r: AdminReviewer) => r.lead
    ? <span className="mt-0.5 block text-[11px] text-ground-500" data-testid="lead-no-self-qc">{t('admin.team.noSelfQc')}</span>
    : null
  const paged = usePagedRows(sorted)
  const onSort = (col: ReviewerSortKey) => setSort(nextSort(sort, col, firstDirFor(col)))

  // Below every hook on purpose — an early return above them would change the hook order between
  // the signed-out render and the signed-in one.
  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">{t('admin.people.title')}</h1>
      <p className="text-sm text-ground-500 mt-1 mb-4">{t('admin.team.desc')}</p>

      {/* ⚠ THE TAB BAR NOW RENDERS FOR EVERYONE WHO MAY READ THE PAGE. It used to appear only for
          the roles that may edit the emails, which was harmless while Emails was the only other
          panel — but Admins is a READING tab, and hiding the bar would have left `finance` with no
          way to reach it at all. Each tab keeps its own gate instead. */}
      {/* Owner 2026-11-08: Add sits on the TAB ROW, at its right end, sized like a tab — not on a row of
          its own. It stays OUTSIDE the tablist (a button there is not a tab to a screen reader), so the
          row is a flex pair: the tabs take the room, Add keeps its own width on the right. */}
      <div className="flex items-start gap-3">
      <div className="min-w-0 flex-1">
      <PanelTabs ariaLabelKey="admin.people.tabsAria" active={panel}
        onSelect={(k) => setPanel(k as Panel)}
        tabs={[
          { key: 'staff', labelKey: 'admin.staff.tab' },
          { key: 'admins', labelKey: 'admin.people.tabAdmins' },
          { key: 'reviewers', labelKey: 'admin.reviewers.tabReviewers' },
          // T3: the Mentors TABLE (owner ruling 6) — for who read the old Mentors page (`mayReadMentors`).
          ...(mayMentors ? [{ key: 'mentors', labelKey: 'admin.team.tabMentors' }] : []),
          ...(mayEditEmails ? [{ key: 'emails', labelKey: 'admin.reviewers.tabEmails' }] : []),
          // T4: Terms opens — three "Soon" sections (Admin, Reviewer, Mentor). Nobody signs anything on
          // Team yet; it was a disabled tab with no content before, so nothing is lost. Everyone who reads
          // the page may read it (it says only what is coming).
          { key: 'terms', labelKey: 'admin.reviewers.tabTerms' },
        ]} />
      </div>
      {/* T2: Add Admin / Add Reviewer / Add Mentor — an EXISTING member only; new people are invited on
          Invitations. Offered to whoever may edit permissions on Team (super, org_admin); the endpoint
          re-checks. */}
      {canManage && (panel === 'admins' || panel === 'reviewers' || (panel === 'mentors' && mayMentors)) && (
        <button type="button" data-testid={`team-add-${panel}-open`}
          onClick={() => (panel === 'mentors' ? setAddingMentor(true) : setAdding(panel))}
          className="shrink-0 rounded-lg border border-transparent bg-brand-fill px-4 py-1.5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover max-md:min-h-11">
          {t(panel === 'mentors' ? 'admin.mentors.addMentor' : `admin.team.add.${panel}`)}
        </button>
      )}
      </div>

      {/* Mounted only while its tab is selected, so each reveal re-reads the templates and an
          emails hiccup can never take the reviewers table down with it. T4: three sections — Admin
          (read-only list), Reviewer (the five, moved whole), Mentor (the invitation, Invitations' card). */}
      {panel === 'emails' && mayEditEmails && <TeamEmails token={token} t={t} />}
      {panel === 'terms' && <TeamTerms t={t} />}

      <TeamAddSheet open={adding !== null} table={adding ?? 'admins'} token={token}
        onClose={() => setAdding(null)} onDone={teamDone} />
      <TeamRemoveSheet person={removing} table={removing?.table ?? 'admins'} token={token}
        onClose={() => setRemoving(null)} onDone={teamDone} />

      {/* M1b: Staff — every accepted member, with Suspend / Restore and Delete (O3), its own chunk. */}
      {panel === 'staff' && (
        <StaffList token={token} canManage={canManage} viewerSuper={viewerSuper}
          onChanged={() => { reloadStaff(); load() }} />
      )}

      {/* T3: the Mentors table, its own chunk (the old Mentors page's, `lazySource`), handed this page's
          "Also in" chips so the chunk imports nothing the route already carries. */}
      {panel === 'mentors' && mayMentors && (
        <TeamMentors AlsoIn={AlsoIn} adding={addingMentor} onAddClose={() => setAddingMentor(false)} />
      )}

      {panel === 'admins' && (<>
        <MessageBanner message={staffMessage} />
        {/* The SAME table the platform's two staff screens use — one component, so a third copy
            of "who is in, and may I switch them off" cannot drift from the other two. It already
            knows that revoked beats paused, and already draws phone cards. */}
        {/* T2: everybody who sits at the Admins table (`tables`, served) — a reviewer holding admin keys
            too. A revoked person sits at no table, so they are placed by their old label and keep
            their Restore. "Change role" is gone: Finance and QC are no longer labels (rulings 4, 8). */}
        {/* M1b (O4): Add and Remove only — Suspend and Delete are on Staff. */}
        <StaffTable rows={adminRows} busyId={staffBusyId} canAct={canManage}
          onResend={canManage ? resend : undefined}
          nameHref={canManage ? personHref : undefined}
          soleOrgAdmin={soleOrgAdmin} viewerSuper={viewerSuper}
          team={{ onRemove: (a, toNoGroup) => setRemoving({ id: a.id, name: a.name, table: 'admins', toNoGroup }) }} />
        {!canManage && (
          <p className="mt-3 text-sm text-ground-500">{t('admin.administration.viewOnlyNote')}</p>
        )}
      </>)}

      {panel === 'reviewers' && (<>
      {/* A role change's refusal (open cases…) or failure, from the shared staff actions. */}
      <MessageBanner message={staffMessage} />
      {error && <div className="text-critical-600 mb-3">{error}</div>}
      {/* ⚠ `error` is tested BEFORE the empty check, and that is not a style choice. A failed
          fetch also leaves the list empty, so the other order prints "No reviewers yet — invite
          one" underneath the error: it tells an org_admin they have nobody when the truth is we
          could not ask. "We don't know" and "there are none" must never render the same. */}
      {loading ? (
        <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>
      ) : error ? null : reviewers.length === 0 ? (
        <div className="text-center text-ground-500 mt-8">{t('admin.reviewers.empty')}</div>
      ) : (
        <>
        {/* ── PHONE: one card per reviewer (owner, 2026-09-08) ────────────────────────────────
            Seven columns do not fit. The name and the STATUS lead — a paused volunteer is the
            thing you scan this list for — and **awaiting review** and **interviewing** are the
            large figures, because "who is free" is the question this page answers (request #51
            split the old Open now in two). Completed and turnaround follow them as context, on
            one line, in the same order as the table's columns.

            ⚠ THE TWO "NORMAL EMPTY" READINGS SURVIVE, and they are the reason this page has
            careful greys: an empty caseload is a volunteer between assignments (greyed, never
            flagged), and a blank gift means EVERY gift, which is the live default for all 17
            org-scoped staff. Both must read as answers, not as missing data. */}
        <div className="space-y-2.5 md:hidden" data-testid="reviewer-cards">
          {paged.rows.map((r) => {
            const band = turnaroundBand(r.turnaround_days)
            return (
              <div key={r.id}
                className="rounded-xl border border-ground-200 border-l-[3px] border-l-blue-500 bg-ground-0 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-2">
                    <StaffAvatar name={r.name} photoUrl={r.photo_url} size={32} />
                    <div className="min-w-0">
                      <Link href={`/admin/organisation/reviewers/${r.id}`}
                        className="text-sm font-semibold text-primary-600 hover:text-primary-800">
                        {r.name || '—'}
                      </Link>
                      <div className="mt-0.5 truncate text-[11px] text-ground-500">{r.email || '—'}</div>
                    </div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${PHONE_PILL_SM} ${
                    STAFF_STATUS_TONE[staffStatusKey(r)]}`}>
                    {t(`admin.reviewers.status.${staffStatusKey(r)}`)}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px] text-ground-600">
                  {([['colAwaiting', r.awaiting_review], ['colInterviewing', r.interviewing]] as const)
                    .map(([key, n]) => (
                      <span key={key} className="flex items-baseline gap-1.5">
                        <span className="text-ground-500">{t(`admin.reviewers.${key}`)}</span>
                        <span className={`text-base tabular-nums ${figureTone(n)}`}>{n}</span>
                      </span>
                    ))}
                  <span>
                    <span className="text-ground-500">{t('admin.reviewers.colCompleted')}</span>{' '}
                    <span className="tabular-nums">{r.completed > 0 ? r.completed : '—'}</span>
                  </span>
                  <span className={band === 'waiting' ? 'font-semibold text-caution-700' : ''}>
                    <span className="font-normal text-ground-500">{t('admin.reviewers.colTurnaround')}</span>{' '}
                    {band === 'unknown'
                      ? t('admin.reviewers.noTurnaround')
                      : t('admin.reviewers.days', { days: String(r.turnaround_days) })}
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {leadNote(r)}
                  <AlsoIn row={r} here="reviewers" />
                  {canManage && <RemoveControl remove={r.remove} table="reviewers" busy={staffBusyId === r.id}
                    counts={{ open_cases: r.open_now }}
                    onRemove={(toNoGroup) => setRemoving({ id: r.id, name: r.name, table: 'reviewers', toNoGroup })} />}
                </div>
              </div>
            )
          })}
        </div>

        <TableFrame className="hidden md:block" minWidth={1200} label={t('admin.reviewers.title')}>
          <table className="w-full text-sm">
            <thead className="bg-ground-50/80 border-b">
              <tr>
                <SortHeader col="name" label={t('admin.nameHeader')} sort={sort} onSort={onSort} />
                {/* T2: "Also in" replaces the Role column. T3: no permission column (the person's page). */}
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                  {t('admin.team.colAlsoIn')}
                </th>
                <SortHeader col="awaitingReview" label={t(REVIEWER_SORT_LABEL.awaitingReview)} sort={sort} onSort={onSort} align="right" />
                <SortHeader col="interviewing" label={t(REVIEWER_SORT_LABEL.interviewing)} sort={sort} onSort={onSort} align="right" />
                <SortHeader col="completed" label={t(REVIEWER_SORT_LABEL.completed)} sort={sort} onSort={onSort} align="right" />
                <SortHeader col="turnaround" label={t(REVIEWER_SORT_LABEL.turnaround)} sort={sort} onSort={onSort} align="right" />
                <SortHeader col="status" label={t(REVIEWER_SORT_LABEL.status)} sort={sort} onSort={onSort} />
                {/* Plain headers, not sortable: "last seen" sorts by a column that is empty for
                    anybody predating it, which would bunch "not recorded" at one end and read as
                    an ordering of people. The action column has nothing to sort by at all. */}
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wider text-ground-600">
                  {t('admin.reviewers.colLastSeen')}
                </th>
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wider text-ground-600">
                  {t('admin.actionHeader')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ground-100">
              {paged.rows.map((r) => {
                const band = turnaroundBand(r.turnaround_days)
                return (
                  <tr key={r.id} className="hover:bg-info-50/40 transition-colors align-top">
                    <td className="px-4 py-3 border-l-[3px] border-l-blue-500">
                      {/* The name opens the whole record — credentials, outcomes, reopens. */}
                      <div className="flex items-start gap-2">
                        <StaffAvatar name={r.name} photoUrl={r.photo_url} size={28} />
                        <div className="min-w-0">
                          <Link href={`/admin/organisation/reviewers/${r.id}`}
                            className="font-medium text-primary-600 hover:text-primary-800">
                            {r.name || '—'}
                          </Link>
                          <div className="text-xs text-ground-500 mt-0.5">{r.email || '—'}</div>
                          {r.lead && (
                            <span className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[11px] ${roleBadgeClass('org_admin')}`}>
                              {t('admin.role.org_admin')}
                            </span>
                          )}
                          {leadNote(r)}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3"><AlsoIn row={r} here="reviewers" /></td>
                    {/* An empty figure is the normal state of a volunteer between assignments —
                        greyed, never flagged. A grey Awaiting review is the signal request #51
                        asked for: this person can take more, even while interviews run. */}
                    <td className={`px-4 py-3 text-right tabular-nums ${figureTone(r.awaiting_review)}`}
                      data-testid={`awaiting-${r.id}`}>
                      {r.awaiting_review}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums ${figureTone(r.interviewing)}`}
                      data-testid={`interviewing-${r.id}`}>
                      {r.interviewing}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-ground-700">
                      {r.completed > 0 ? r.completed : <span className="text-ground-400">—</span>}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums ${
                      band === 'waiting' ? 'text-caution-700 font-semibold' : 'text-ground-700'}`}
                      title={band === 'unknown' ? t('admin.reviewers.noTurnaroundHint')
                        : t('admin.reviewers.turnaroundHint')}>
                      {band === 'unknown'
                        ? <span className="text-ground-400">{t('admin.reviewers.noTurnaround')}</span>
                        : t('admin.reviewers.days', { days: String(r.turnaround_days) })}
                    </td>
                    {/* ⚠ NOT `r.paused` ANY MORE. Revoked beats paused, and the rule lives in
                        `lib/staffStatus` so this table and the staff table cannot disagree —
                        which they have done twice. */}
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        STAFF_STATUS_TONE[staffStatusKey(r)]}`}>
                        {t(`admin.reviewers.status.${staffStatusKey(r)}`)}
                      </span>
                    </td>
                    {/* ⚠ "NOT RECORDED" IS NOT "NEVER SIGNED IN". The column is best-effort and
                        empty for everybody predating it, so a blank must never read as an
                        accusation. 20 of 21 staff carry a value. */}
                    <td className="px-4 py-3 text-ground-700">
                      {r.last_seen_at
                        ? formatDate(r.last_seen_at)
                        : <span className="text-ground-400">{t('admin.reviewers.lastSeenUnknown')}</span>}
                    </td>
                    <td className="px-4 py-3">
                      {canManage && (
                        <div className="flex flex-wrap items-center gap-3">
                          {/* T2: "Change role" (Reviewer ↔ QC) is gone — QC is a permission now. M1b (O4):
                              Remove only; Suspend and Delete are on Staff. */}
                          <RemoveControl remove={r.remove} table="reviewers" busy={staffBusyId === r.id}
                            counts={{ open_cases: r.open_now }}
                            onRemove={(toNoGroup) => setRemoving({ id: r.id, name: r.name, table: 'reviewers', toNoGroup })} />
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {paged.visible && (
            <div className="px-4 sm:px-5 pb-4">
              <Pagination
                page={paged.page} totalPages={paged.totalPages} pageSize={paged.pageSize}
                onPageChange={paged.setPage}
                pageSizeOptions={PAGE_SIZE_OPTIONS} onPageSizeChange={paged.setPageSize}
              />
            </div>
          )}
        </TableFrame>
        </>
      )}
      <p className="text-xs text-ground-500 mt-4 max-w-3xl">{t('admin.reviewers.footnote')}</p>
      </>)}
    </div>
  )
}
