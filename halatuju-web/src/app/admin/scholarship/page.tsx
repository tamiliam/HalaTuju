'use client'

import '@/lib/messagesScholarship'   // TD-416: this page's scholarship.* words (their own slice)
import { isThirdRoute } from '@/lib/qualification'   // third results route S2b: named, not 'MATRIC'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { PHONE_PILL, PHONE_PILL_SM } from '@/lib/phonePill'   // pills on a phone (Mobile M8)
import { useProgrammeScope } from '@/lib/programmeScope'
import { useGiftInUrl } from '@/lib/useGiftInUrl'
import { ApplicationUrlChips, useApplicationUrlFilters } from '@/components/admin/ApplicationUrlFilters'
import TableFrame from '@/components/admin/TableFrame'
import CaseListPhoneTools, { type CaseSortKey } from '@/components/admin/CaseListPhoneTools'
import { bucketBadge, type Reviewer } from '@/lib/assignOptions'
import { AssigneeOptions, AssignLangNote, AssignLegend, legendIdFor } from '@/components/admin/AssignListPicker'
import { canAccess, effectiveRole } from '@/lib/navigation'
import {
  getScholarshipApplications,
  getAssignableAdmins,
  getSourceNames,
  assignApplication,
  DEFAULT_ADMIN_PAGE_SIZE,
  type AdminScholarshipListData,
} from '@/lib/admin-api'
import { Pagination } from '@/components/Pagination'
import { lazySource } from '@/components/source/LazySource'
// import AiReliabilityCard from '@/components/AiReliabilityCard' // hidden 2026-06-13 — re-add when placement is decided (component retained)
import { referralAcronym } from '@/lib/scholarship'
import { FIXED_REFERRAL_CODES, referralLabel } from '@/lib/referralSources'
import { APPLICATION_STATUSES, statusLabelKey, statusTone, displayStatus } from '@/lib/applicationStatus'
import { SCHOLARSHIP_LIST_NAV, writeListNav } from '@/lib/listNav'

const SourceApplications = lazySource(
  () => import('@/components/source/SourceApplications').then((m) => m.default))

const PAGE_SIZE_OPTIONS = [10, 25, 50]

// ⚠ A SOURCE USER GETS ITS OWN SCREEN (source sign-in, 2026-10-30), chosen BEFORE any staff hook
// runs: the staff body calls staff endpoints, which refuse the role. The source component calls
// `admin/source/` only (`components/source/noStaffCalls.test.tsx`).
export default function AdminScholarshipList() {
  const { role } = useAdminAuth()
  return role?.role === 'source_partner' ? <SourceApplications /> : <StaffScholarshipList />
}

function StaffScholarshipList() {
  const { token, role } = useAdminAuth()
  const effRole = effectiveRole(role)
  const isSuper = effRole === 'super'
  /*
   * ⚠ A SECOND LINE, NOT A FENCE (2026-09-08). A real role (`finance`, `_b40_scope` 'none') was once routed
   * here and failed quietly; `defaultRoute` is the actual fix, and the registry already says who may open
   * this page, so the page says it too. The endpoint refuses on its own — see `navigation.ts`.
   */
  const mayView = canAccess('/admin/scholarship', effRole, role?.permissions)
  // Assignment (the "Assigned" column + inline dropdown) is a super or org_admin power —
  // an org_admin assigns their own org's reviewers (backend fences the target + application).
  const canAssign = isSuper || role?.role === 'org_admin'
  // Only super + admin see every application, so only they benefit from the assignee filter.
  // A reviewer's list is already hard-scoped to their own assigned applicants server-side, so
  // the filter is redundant for them (and "Unassigned" would always return nothing).
  const canFilterByAssignee = isSuper || role?.role === 'admin' || role?.role === 'org_admin'
  const { t } = useT()
  /*
   * ⚠ THE HEADING USED TO NAME THE TENANT'S FLAGSHIP, WHATEVER GIFT WAS PICKED.
   * `admin.scholarship.title` is '{programmeName} Applicants', and `programmeName` is one of the
   * five BRANDING auto-tokens `t()` injects beneath explicit call-site params — the organisation's
   * flagship name, not the selected gift. So it read "BrightPath Bursary Applicants" over the crumb
   * saying Test Programme, above 143 people who are not Test Programme's. That is a correctness
   * problem, not a missing feature, which is why it is fixed before the filtering.
   *
   * Passing `programmeName` EXPLICITLY shadows the auto-token, so the one string serves both and
   * the ms/ta translations need no new keys. With nothing chosen the gift cannot be named at all,
   * so the heading drops to a neutral one rather than asserting a gift.
   */
  const { chosen, programme } = useProgrammeScope()
  // `?programme=` narrows this list to that gift (TD-296); with none it stays the all-gifts list.
  const urlRead = useGiftInUrl()
  const [data, setData] = useState<AdminScholarshipListData | null>(null)
  // Inline reviewer assignment (the "Assigned" column dropdown) — super or org_admin.
  const [reviewers, setReviewers] = useState<Reviewer[]>([])
  // Past assignees (org-fenced, incl. inactive/role-changed) — the filter's "Past reviewers".
  const [pastAssignees, setPastAssignees] = useState<Array<{ id: number; name: string }>>([])
  const [assignNote, setAssignNote] = useState<Record<number, string>>({})
  const [bucket, setBucket] = useState('')
  const [statusF, setStatusF] = useState('')
  const [source, setSource] = useState('')
  // Every source row's name by code (switched-off ones too, so old applicants stay filterable).
  const [sourceNames, setSourceNames] = useState<Record<string, string>>({})
  const [assignedF, setAssignedF] = useState('')
  // Request #26 (owner ruling B): only the students whose parent phone needs a call — super/org_admin.
  const [parentCallF, setParentCallF] = useState(false)
  // The Overview's pending cards link here with ?status=&assigned=&ready=1&band= (ApplicationUrlFilters).
  const { readyF, setReadyF, bandF, setBandF, withdrawalF, setWithdrawalF, urlFiltersRead } = useApplicationUrlFilters(statusF, setStatusF, assignedF, setAssignedF)
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('') // debounced value actually sent to the API
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_ADMIN_PAGE_SIZE)
  // Column sorting (server-side). '' = default (newest submitted first).
  type SortKey = CaseSortKey
  const [sort, setSort] = useState<'' | SortKey>('')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  // Click a sortable header: same column flips direction; a new column starts at a
  // sensible default (merit high→low; name/source/status/assigned A→Z). Resets to page 1.
  const toggleSort = (key: SortKey) => {
    if (sort === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSort(key)
      setSortDir(key === 'merit' ? 'desc' : 'asc')
    }
    setPage(1)
  }
  const sortArrow = (key: SortKey) => (sort === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '')

  // Switching gift narrows the set, so page 5 of the old one may not exist in the new one — the
  // same reason every filter resets the page. Not folded into `changeFilter`: the gift comes from
  // the shell's breadcrumb, not from a control on this page.
  useEffect(() => { setPage(1) }, [chosen])

  // Debounce the search box so a request doesn't fire on every keystroke.
  useEffect(() => {
    const id = setTimeout(() => {
      setQ(search.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(id)
  }, [search])

  useEffect(() => {
    if (!token || !mayView || !urlRead || !urlFiltersRead) return
    // Only this effect's newest read may land (TD-298): a slow reply for the gift — or filter — you
    // left must not overwrite the list you are now looking at.
    let current = true
    setLoading(true)
    getScholarshipApplications(
      {
        bucket: bucket || undefined,
        status: statusF || undefined,
        source: source || undefined,
        assigned: assignedF || undefined,
        ready: readyF || undefined,
        band: bandF || undefined,
        withdrawal: withdrawalF || undefined,
        parentCall: parentCallF ? 'needed' : undefined,
        q: q || undefined,
        page,
        pageSize,
        sort: sort || undefined,
        dir: sort ? sortDir : undefined,
        // The chosen gift, sent as an EXPLICIT value the server re-fences — never a header or a
        // cookie. Empty (several gifts, none chosen) sends nothing and lists every gift the
        // caller may see, which is the honest answer for a READ.
        programme: chosen || undefined,
      },
      { token },
    )
      .then((d) => { if (current) setData(d) })
      .catch(() => { if (current) setError(t('admin.scholarship.loadFailed')) })
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, urlRead, chosen, bucket, statusF, source, assignedF, readyF, bandF, withdrawalF, urlFiltersRead, parentCallF, q, page, pageSize, sort, sortDir])

  const apps = data?.applications ?? []

  // Reviewers for the assignment dropdown — fetched once, for callers who can assign
  // (super or org_admin). The endpoint org-scopes the pool for a non-super caller.
  useEffect(() => {
    if (!token || !canAssign) return
    getAssignableAdmins({ token })
      .then((r) => {
        setReviewers(r.admins.map((a) => ({ id: a.id, name: a.name, role: a.role, languages: a.languages || [], assignable: a.assignable, gifts: a.gifts })))
        setPastAssignees(r.past_assignees ?? [])
      })
      .catch(() => {})
  }, [token, canAssign])

  // The Source filter and tooltips: the source names, read separately — NOT added to the list
  // endpoint (pinned at 4 queries). Since sources Sprint C every list role may read them (reviewer
  // and QC included); on a failure the fixed three and the bare code still render.
  // Request #41: scoped to the chosen gift (the same code the list sends), the names are only THAT
  // gift's sources — its linked ones plus any its applicants answered — and re-read when the gift
  // changes. Waits for `urlRead`, like the list, so a shared link never reads the wrong gift's names
  // first. Only the newest reply lands; after a SUCCESSFUL read, a selected source the new gift does
  // not have (and that is not one of the fixed three) falls back to All sources. A row whose source
  // is not in the list keeps falling back to its bare code.
  useEffect(() => {
    if (!token || !mayView || !urlRead) return
    let current = true
    getSourceNames({ programme: chosen || undefined }, { token })
      .then((d) => {
        if (!current) return
        const names: Record<string, string> = Object.fromEntries(d.sources.map((s) => [s.code, s.name]))
        setSourceNames(names)
        setSource((sel) => (sel && !Object.prototype.hasOwnProperty.call(names, sel)
          && !(FIXED_REFERRAL_CODES as readonly string[]).includes(sel) ? '' : sel))
      })
      .catch(() => {})
    return () => { current = false }
  }, [token, mayView, urlRead, chosen])
  const sourceFilterCodes = [
    ...Object.keys(sourceNames).filter((c) => !(FIXED_REFERRAL_CODES as readonly string[]).includes(c))
      .sort((a, b) => sourceNames[a].localeCompare(sourceNames[b])),
    ...FIXED_REFERRAL_CODES,
  ]
  const sourceTitle = (code?: string | null) => referralLabel(code, t, sourceNames)

  // Inline (re)assign — option A: attempt and surface a 'not ready' / error inline. The
  // backend enforces super-only + reviewer-target; first-assign needs the app to be ready.
  const handleAssign = async (appId: number, reviewerId: number | null) => {
    if (!token) return
    setAssignNote((n) => ({ ...n, [appId]: '' }))
    try {
      const updated = await assignApplication(appId, reviewerId, { token })
      setData((d) => d && {
        ...d,
        applications: d.applications.map((a) => a.id === appId
          ? { ...a, assigned_to_id: updated.assigned_to_id, assigned_to_name: updated.assigned_to_name }
          : a),
      })
    } catch (e) {
      const code = e instanceof Error ? e.message : ''
      const known = ['not_ready', 'not_reviewer', 'reviewer_paused', 'bad_assignee',
                     'not_assignable', 'findings_submitted', 'gift_mismatch']
      setAssignNote((n) => ({ ...n, [appId]: known.includes(code)
        ? t(`admin.scholarship.assign.error.${code}`)
        : t('admin.scholarship.assignError') }))
    }
  }

  // #7: persist the current filtered/sorted page's ordered ids so the detail cockpit
  // can offer prev/next navigation that follows what the officer is looking at.
  useEffect(() => {
    if (typeof window === 'undefined' || !data) return
    writeListNav(SCHOLARSHIP_LIST_NAV, {
      ids: (data.applications ?? []).map((a) => a.id),
      backHref: '/admin/scholarship', labelKey: 'admin.scholarship.back',
    })
  }, [data])

  // Changing any filter resets to page 1 — otherwise you can land on a page
  // that no longer exists for the narrowed result set ("page 5 of 2").
  const changeFilter = (setter: (v: string) => void) => (value: string) => {
    setter(value)
    setPage(1)
  }

  // ⚠ `role &&` — while the role is still loading we render the page, not a refusal. Showing
  // "you may not see this" for a frame and then the table is worse than a blank moment.
  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  // The filters, ONCE (Mobile M6a): the desktop row and the phone Sheet both draw this, on the same state.
  // Each select is NAMED by its own "all" option (aria-label): a title= tooltip needs a hover a phone has not.
  const filterControls = (
    <>
        <select value={source} onChange={(e) => changeFilter(setSource)(e.target.value)}
          aria-label={t('admin.scholarship.allSources')}
          className="border rounded-lg px-3 py-2 text-sm w-40 truncate">
          <option value="">{t('admin.scholarship.allSources')}</option>
          {sourceFilterCodes.map((code) => <option key={code} value={code}>{sourceTitle(code)}</option>)}
        </select>
        <select value={bucket} onChange={(e) => changeFilter(setBucket)(e.target.value)} aria-label={t('admin.scholarship.allBuckets')} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.scholarship.allBuckets')}</option>
          <option value="A">Bucket A</option>
          <option value="B">Bucket B</option>
        </select>
        <select value={statusF} onChange={(e) => changeFilter(setStatusF)(e.target.value)} aria-label={t('admin.scholarship.allStatuses')} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.scholarship.allStatuses')}</option>
          {APPLICATION_STATUSES.map((s) => <option key={s} value={s}>{t(statusLabelKey(s))}</option>)}
        </select>
        {canFilterByAssignee && (
          // Admin/super view this filter (it's hidden for reviewers, whose list is self-scoped).
          // "Assigned to me" is dropped — applicants are assigned to reviewers, not to admins —
          // and replaced with each active reviewer, so an admin can filter by who's reviewing.
          <select value={assignedF} onChange={(e) => changeFilter(setAssignedF)(e.target.value)} aria-label={t('admin.scholarship.allAssignees')} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">{t('admin.scholarship.allAssignees')}</option>
            <option value="none">{t('admin.scholarship.unassigned')}</option>
            {assignedF === 'me' && <option value="me">{t('admin.scholarship.chip.me')}</option>}
            {reviewers.length > 0 && (
              <optgroup label={t('admin.scholarship.byReviewer')}>
                {reviewers.map((rv) => <option key={rv.id} value={rv.id}>{rv.name}</option>)}
              </optgroup>
            )}
            {/* Past reviewers — still on record as some application's assignee but no longer in
                the current staff list (inactive / role-changed). Filtering by them surfaces
                their old cases; they are NOT offered by the assign dropdowns. */}
            {(() => {
              const past = pastAssignees.filter((p) => !reviewers.some((rv) => rv.id === p.id))
              return past.length > 0 && (
                <optgroup label={t('admin.scholarship.pastReviewers')}>
                  {past.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </optgroup>
              )
            })()}
          </select>
        )}
        {canAssign && (
          <button type="button" aria-pressed={parentCallF} onClick={() => { setParentCallF((v) => !v); setPage(1) }}
            className={`rounded-full border px-3 py-2 text-sm ${PHONE_PILL} ${parentCallF ? 'border-caution-400 bg-caution-50 text-caution-800' : 'border-ground-300 text-ground-700'}`}>
            {t('admin.scholarship.call.needs')}
          </button>
        )}
    </>
  )
  const activeFilters = [source, bucket, statusF, assignedF, bandF].filter(Boolean).length + (parentCallF ? 1 : 0) + (readyF ? 1 : 0) + (withdrawalF ? 1 : 0)

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">
        {programme
          ? t('admin.scholarship.title', { programmeName: programme.name })
          : t('admin.scholarship.titleAll')}
      </h1>
      <p className="text-sm text-ground-500 mt-1 mb-4">
        {data ? t('admin.scholarship.countSubtitle', { count: String(data.count) }) : ' '}
      </p>

      <ApplicationUrlChips readyF={readyF} bandF={bandF} onClearReady={() => { setReadyF(false); setPage(1) }}
        onClearBand={() => { setBandF(''); setPage(1) }} withdrawalF={withdrawalF} onClearWithdrawal={() => { setWithdrawalF(''); setPage(1) }} />

      {/* AI reliability card hidden 2026-06-13 — placement TBD by owner; component kept in components/AiReliabilityCard.tsx */}

      {/* ⚠ ONE SET OF FILTERS, TWO PLACES (Mobile M6a). From `md` they sit in the row as they always
          did; on a phone the search stays on the page and the rest open in the shared Sheet behind
          "Filters", with Sort beside it (the table's sortable headers are desktop-only). Both read and
          write the SAME state, so a filter set on one shows on the other. */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative w-full md:w-auto md:flex-none md:min-w-[180px] lg:w-64">
          <svg className="w-4 h-4 text-ground-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-4.35-4.35M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('admin.searchPlaceholder')}
            aria-label={t('admin.searchPlaceholder')}
            className="w-full border rounded-lg pl-9 pr-3 py-2 max-md:min-h-11 text-sm bg-ground-0 focus:outline-none focus:ring-2 focus:ring-brand-shape focus:border-transparent"
          />
        </div>
        <CaseListPhoneTools filters={filterControls} activeFilters={activeFilters} sort={sort} sortDir={sortDir}
          canAssign={canAssign} count={data && !loading ? data.count : null}
          onSort={(key, dir) => { setSort(key); setSortDir(dir); setPage(1) }} />
        <div className="hidden md:contents">{filterControls}</div>
      </div>

      {error && <div className="text-critical-600">{error}</div>}
      {loading && !data ? (
        <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>
      ) : apps.length === 0 ? (
        <div className="text-center text-ground-500 mt-8">{t('admin.scholarship.empty')}</div>
      ) : (
        <>
        {/* ── PHONE: one card per application (owner, 2026-09-08) ─────────────────────────────
            Eight columns do not fit a phone. Three LEAD — the name (recognition), the status
            (what you scan a list of applications FOR) and the merit score — and the rest move to
            quieter lines. Nothing is dropped.

            ⚠ THE ASSIGN CONTROL COMES WITH ITS RULES OR NOT AT ALL. Its `disabled` conditions,
            its title, its "keep the current assignee selectable" option and the language-match
            ✓/⚠ prefixes are the same expressions as the table's — copied deliberately rather
            than simplified, because a phone select that offers an assignment the server refuses
            ('not_ready') is worse than no control. If that logic ever changes, it changes in
            both places; the alternative is a shared component, which is the next refactor if a
            third caller appears.

            Mobile M6a (rule 15, owner-approved mock-up): ROWS, not cards — hairlines between them on the
            16 px gutter — and the WHOLE row opens the case (name, status, merit, source and date are one
            link), with a chevron saying so. The Assign control stays OUTSIDE that link, under the row,
            with every rule it had; why it is asleep is now written under it (a title= needs a hover),
            and an assign error shows here as it does in the table. 12 px is the smallest text. */}
        <div className="divide-y divide-ground-100 border-y border-ground-100 md:hidden" data-testid="application-cards">
          {apps.map((a) => {
            const s = displayStatus(a)
            const blocked = a.assignable === false
              || (a.assigned_to_id == null && a.ready_for_assignment === false)
            return (
              <div key={a.id} data-app-row>
                <Link href={`/admin/scholarship/${a.id}`} data-row-link
                  className="flex min-h-11 items-center gap-2 py-3 text-ground-900 active:bg-ground-50">
                <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                  <span className="min-w-0 grow basis-40 break-words text-[15px] font-semibold">
                    {a.name || '—'}
                  </span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${statusTone(s)} ${PHONE_PILL_SM}`}>
                    {t(statusLabelKey(s))}
                  </span>
                </span>

                <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs">
                  <span className={`rounded-full px-2 py-0.5 font-semibold ${bucketBadge(a.bucket)} ${PHONE_PILL_SM}`}>
                    {a.bucket || '—'}
                  </span>
                  <span className="text-ground-600">{isThirdRoute(a.qualification) ? t(`admin.scholarship.qualificationLabel.${a.qualification}`) : a.qualification?.toUpperCase()}</span>
                  <span className="text-ground-500">·</span>
                  <span className="text-ground-700">
                    {t('admin.scholarship.merit')} <span className="font-medium">{a.merit_score ?? '—'}</span>
                  </span>
                </span>

                {/* The source by its full name: what the table's hover title says, written out. */}
                <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ground-500">
                  <span className="break-words">{a.referral_source ? sourceTitle(a.referral_source) : '—'}</span>
                  <span>{formatDate(a.submitted_at)}</span>
                </span>
                </span>
                <svg aria-hidden className="h-5 w-5 shrink-0 text-ground-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="m9 6 6 6-6 6" /></svg>
                </Link>

                {canAssign && (
                  <div className="pb-3">
                    <AssignLangNote lang={a.call_language} className="mb-1 text-xs text-ground-500" legendId={`assign-legend-${a.id}`} />
                    <select
                      value={a.assigned_to_id ?? ''}
                      onChange={(e) => handleAssign(a.id, e.target.value ? Number(e.target.value) : null)}
                      disabled={blocked}
                      aria-label={t('admin.scholarship.assigned')}
                      aria-describedby={legendIdFor(a.call_language, `assign-legend-${a.id}`)}
                      className="min-h-11 w-full rounded-lg border bg-ground-0 px-2 py-1.5 text-sm disabled:cursor-not-allowed disabled:bg-ground-100 disabled:text-ground-placeholder"
                    >
                      <AssigneeOptions reviewers={reviewers} row={a} isSuper={isSuper} />
                    </select>
                    {/* Why it is asleep: the SAME two reasons the table's title gives, written out. */}
                    {blocked && (
                      <p className="mt-1 text-xs text-ground-500" data-assign-reason>
                        {a.assignable === false
                          ? t('admin.scholarship.assign.error.not_assignable')
                          : t('admin.scholarship.assign.error.not_ready')}
                      </p>
                    )}
                    {assignNote[a.id] && <p className="mt-1 text-xs text-critical-600">{assignNote[a.id]}</p>}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <TableFrame className="hidden md:block" minWidth={980} label={t('admin.scholarship.title')}>
          <table className="w-full text-sm">
            <thead className="bg-ground-50/80 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('name')}
                    className="uppercase tracking-wider hover:text-ground-900">
                    {t('admin.scholarship.name')}{sortArrow('name')}
                  </button>
                </th>
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('source')}
                    className="uppercase tracking-wider hover:text-ground-900">
                    {t('admin.scholarship.source')}{sortArrow('source')}
                  </button>
                </th>
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">{t('admin.scholarship.bucket')}</th>
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">{t('admin.scholarship.qualShort')}</th>
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('merit')}
                    className="uppercase tracking-wider hover:text-ground-900">
                    {t('admin.scholarship.merit')}{sortArrow('merit')}
                  </button>
                </th>
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('status')}
                    className="uppercase tracking-wider hover:text-ground-900">
                    {t('admin.scholarship.status')}{sortArrow('status')}
                  </button>
                </th>
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('submitted')}
                    className="uppercase tracking-wider hover:text-ground-900">
                    {t('admin.scholarship.submitted')}{sortArrow('submitted')}
                  </button>
                </th>
                {canAssign && (
                  <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                    {/* Request #50: by reviewer name; unassigned stays at the bottom both ways (server). */}
                    <button type="button" onClick={() => toggleSort('assigned')}
                      className="uppercase tracking-wider hover:text-ground-900">
                      {t('admin.scholarship.assigned')}{sortArrow('assigned')}
                    </button>
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-ground-100">
              {apps.map((a) => (
                <tr key={a.id} className="hover:bg-info-50/40 transition-colors">
                  <td className="px-4 py-3 border-l-[3px] border-l-blue-500">
                    <Link href={`/admin/scholarship/${a.id}`} className="text-primary-600 font-medium hover:underline">
                      {a.name || '—'}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-ground-600" title={sourceTitle(a.referral_source)}>{referralAcronym(a.referral_source, sourceNames[a.referral_source ?? '']) || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${bucketBadge(a.bucket)}`}>{a.bucket || '—'}</span>
                  </td>
                  <td className="px-4 py-3 text-ground-600">{isThirdRoute(a.qualification) ? t(`admin.scholarship.qualificationLabel.${a.qualification}`) : a.qualification?.toUpperCase()}</td>
                  <td className="px-4 py-3 text-ground-700 tabular-nums">{a.merit_score ?? '—'}</td>
                  <td className="px-4 py-3">
                    {(() => {
                      // A super-reopened decision shows "Reopened", overriding the stored accepted/rejected.
                      const s = displayStatus(a)
                      return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusTone(s)}`}>{t(statusLabelKey(s))}</span>
                    })()}
                  </td>
                  <td className="px-4 py-3 text-ground-500">{formatDate(a.submitted_at)}</td>
                  {canAssign && (
                    <td className="px-4 py-3">
                      <AssignLangNote lang={a.call_language} className="mb-1 text-[11px] text-ground-500" />
                      <select
                        value={a.assigned_to_id ?? ''}
                        onChange={(e) => handleAssign(a.id, e.target.value ? Number(e.target.value) : null)}
                        aria-describedby={legendIdFor(a.call_language, 'assign-legend-table')}
                        // A case may only change hands while there IS a review to do (Completed /
                        // interviewing). Shortlisted and rejected aren't ready; awaiting-QC and
                        // beyond are over. AND a FIRST assignment waits until the app is ready — all
                        // student tasks done OR the 5-day window lapsed — mirroring the detail
                        // cockpit's firstAssignBlocked, so the list can't offer an assign the server
                        // refuses ('not_ready'). The server refuses either way; disabling here means
                        // the officer isn't invited to take an action that will bounce.
                        disabled={a.assignable === false
                          || (a.assigned_to_id == null && a.ready_for_assignment === false)}
                        title={a.assignable === false
                          ? t('admin.scholarship.assign.error.not_assignable')
                          : (a.assigned_to_id == null && a.ready_for_assignment === false)
                            ? t('admin.scholarship.assign.error.not_ready')
                            : undefined}
                        className="border rounded-lg px-2 py-1 text-sm bg-ground-0 max-w-[220px] disabled:bg-ground-100 disabled:text-ground-placeholder disabled:cursor-not-allowed"
                      >
                        {/* The holder always; else the served `assignable` (T1: the Reviewers table)
                            who covers this case's gift (`listAssignees`). */}
                        <AssigneeOptions reviewers={reviewers} row={a} isSuper={isSuper} />
                      </select>
                      {assignNote[a.id] && <p className="text-xs text-critical-600 mt-1 max-w-[180px]">{assignNote[a.id]}</p>}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </TableFrame>
        {canAssign && <AssignLegend id="assign-legend-table" className="hidden md:block mt-2 text-xs text-ground-500" />}
        {data && (
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            total={data.count}
            pageSize={data.page_size}
            onPageChange={setPage}
            pageSizeOptions={PAGE_SIZE_OPTIONS}
            onPageSizeChange={(size) => {
              setPageSize(size)
              setPage(1)
            }}
            rangeKey="admin.scholarship.showingRange"
          />
        )}
        </>
      )}
    </div>
  )
}
