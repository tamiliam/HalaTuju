'use client'

/**
 * The Requests list (Requests list R1, 2026-11-03): four tabs, a kind filter, a search box and a
 * pager, all answered by the SERVER — this component decides nothing about which request goes
 * where, what kind it is, or which tag it wears.
 *
 * ⚠ THE TABS PARTITION THE LIST (owner, option A). Each request is in exactly one of Needs action /
 * In progress / Closed, and All is their sum; Needs action is the same rule as the nav badge
 * (`org_requests_queue.needs_action_q`), so the badge's number is the first tab's number. The
 * counts are of the WHOLE list and never move with the kind filter or the search box (decisions.md,
 * S7 2026-09-11); "Showing a–b of N" beside the pager is the filtered total.
 *
 * ⚠ It replaces a status dropdown that never filtered anything — the server ignored `?status=`.
 *
 * URL state: `?tab=&kind=&q=&page=`, defaults left out, read ONCE from `window.location` on mount
 * (`useSearchParams` in a page needs a Suspense boundary — see admin/programme/page.tsx) and written
 * back with `router.replace`. The list also leaves its page's ids in `lib/listNav`, with its own URL,
 * so the detail page can offer Previous / Next and a "Back to <tab>" that lands here unchanged.
 *
 * ⚠ LATEST REPLY WINS. Typing, switching tab and paging all fetch; a slow reply to an older
 * question must never overwrite a newer one, so each fetch takes a ticket and only the newest
 * ticket's reply is applied.
 */
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'
import PanelTabs from '@/components/admin/PanelTabs'
import { Pagination } from '@/components/Pagination'
import {
  getOrgRequests, type OrgRequestGroup, type OrgRequestListPage, type OrgRequestTag,
} from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { REQUESTS_LIST_NAV, writeListNav } from '@/lib/listNav'
import { kindLabelKey, statusLabelKey, statusTone } from '@/lib/requestStatus'

type Kind = '' | 'bug' | 'feature'

export interface RequestsListState {
  tab: OrgRequestGroup
  kind: Kind
  q: string
  page: number
}

const GROUPS: readonly OrgRequestGroup[] = ['action', 'progress', 'closed', 'all']
const KINDS: readonly Kind[] = ['', 'bug', 'feature']

/** Needs action first (D9): it is why anybody opens the page, and what the badge counted. */
export const DEFAULT_LIST_STATE: RequestsListState = { tab: 'action', kind: '', q: '', page: 1 }

// Literal keys, never assembled, so the i18n orphan guard can see every one of them.
const TAB_LABEL: Record<OrgRequestGroup, string> = {
  action: 'admin.requests.list.tabAction',
  progress: 'admin.requests.list.tabProgress',
  closed: 'admin.requests.list.tabClosed',
  all: 'admin.requests.list.filterAll',
}
const KIND_LABEL: Record<Kind, string> = {
  '': 'admin.requests.list.kindAll',
  bug: 'admin.requests.list.kindBug',
  feature: 'admin.requests.list.kindFeature',
}
const TAG: Record<OrgRequestTag, { key: string; tone: string }> = {
  answer_needed: { key: 'admin.requests.list.answerNeeded', tone: 'bg-caution-100 text-caution-700' },
  analysis_draft: { key: 'admin.requests.list.analysisDraft', tone: 'bg-caution-100 text-caution-700' },
  analysed: { key: 'admin.requests.list.analysed', tone: 'bg-positive-100 text-positive-800' },
}

/** How long the search box waits for typing to pause before it asks the server. */
export const SEARCH_DEBOUNCE_MS = 300

/** The list's state from a query string. Anything unknown falls back to its default. */
export function readListState(search: string): RequestsListState {
  const p = new URLSearchParams(search)
  const tab = p.get('tab') as OrgRequestGroup | null
  const kind = (p.get('kind') ?? '') as Kind
  const page = Number(p.get('page'))
  return {
    tab: tab && GROUPS.includes(tab) ? tab : DEFAULT_LIST_STATE.tab,
    kind: KINDS.includes(kind) ? kind : '',
    q: (p.get('q') ?? '').trim(),
    page: Number.isInteger(page) && page > 1 ? page : 1,
  }
}

/** The query string for a state — '' for the defaults, which stay out of the address bar. */
export function listQuery(s: RequestsListState): string {
  const p = new URLSearchParams()
  if (s.tab !== DEFAULT_LIST_STATE.tab) p.set('tab', s.tab)
  if (s.kind) p.set('kind', s.kind)
  if (s.q) p.set('q', s.q)
  if (s.page > 1) p.set('page', String(s.page))
  const qs = p.toString()
  return qs ? `?${qs}` : ''
}

export default function RequestsList({ token, org, isSuper, reloadKey, onDark }: {
  token: string | null | undefined
  /** The organisation crumb (TD-228); re-fenced by the server. */
  org: string | null | undefined
  isSuper: boolean
  /** Bumped by the page after it creates a request, so the list asks again. */
  reloadKey: number
  /** The list answered 404 — the Requests space is dark. */
  onDark: () => void
}) {
  const { t } = useT()
  const router = useRouter()
  const [state, setState] = useState<RequestsListState | null>(null)
  const [draft, setDraft] = useState('')
  const [data, setData] = useState<OrgRequestListPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const ticket = useRef(0)
  const onDarkRef = useRef(onDark)
  onDarkRef.current = onDark

  // The address bar is read once, after mount, so the server and the first client render agree.
  useEffect(() => {
    const s = readListState(window.location.search)
    setState(s)
    setDraft(s.q)
  }, [])

  // The address bar follows the state; defaults are left out.
  useEffect(() => {
    if (!state) return
    const want = window.location.pathname + listQuery(state)
    if (want !== window.location.pathname + window.location.search) router.replace(want)
  }, [state, router])

  // The search box asks the server once typing pauses, and a new search starts at page 1.
  useEffect(() => {
    const timer = setTimeout(() => {
      setState((s) => (s && s.q !== draft.trim() ? { ...s, q: draft.trim(), page: 1 } : s))
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [draft])

  useEffect(() => {
    if (!token || !state) return
    const mine = ++ticket.current
    setLoading(true)
    setFailed(false)
    getOrgRequests(
      { group: state.tab, kind: state.kind, q: state.q, page: state.page, org: org || undefined },
      { token },
    )
      .then((d) => {
        if (mine !== ticket.current) return            // a newer question has been asked
        setData(d)
        writeListNav(REQUESTS_LIST_NAV, {
          ids: d.ids, backHref: window.location.pathname + listQuery(state),
          labelKey: TAB_LABEL[state.tab],
        })
      })
      .catch((e) => {
        if (mine !== ticket.current) return
        const notFound = (e as { status?: number })?.status === 404 || /404/.test(String(e))
        // A page past the end (the list shrank, or an old link) is a 404 from the pager, not a
        // dark feature: go back to the first page once before concluding anything.
        if (notFound && state.page > 1) setState({ ...state, page: 1 })
        else if (notFound) onDarkRef.current()
        else setFailed(true)
      })
      .finally(() => { if (mine === ticket.current) setLoading(false) })
  }, [token, org, state, reloadKey])

  const pick = (patch: Partial<RequestsListState>) =>
    setState((s) => (s ? { ...s, page: 1, ...patch } : s))

  const tabs = GROUPS.map((key) => ({ key, labelKey: TAB_LABEL[key], count: data?.summary[key] }))
  const rows = data?.requests ?? []
  const from = data && data.count ? (data.page - 1) * data.page_size + 1 : 0
  const to = data ? from + rows.length - 1 : 0

  return (
    <div>
      <PanelTabs tabs={tabs} active={state?.tab ?? DEFAULT_LIST_STATE.tab}
        onSelect={(tab) => pick({ tab })} ariaLabelKey="admin.requests.list.tabsLabel" />

      <div className="flex flex-wrap gap-3 mb-4">
        <select value={state?.kind ?? ''} onChange={(e) => pick({ kind: e.target.value as Kind })}
          aria-label={t('admin.requests.list.kindLabel')}
          className="min-h-11 border rounded-lg px-3 py-2 text-sm">
          {KINDS.map((k) => <option key={k} value={k}>{t(KIND_LABEL[k])}</option>)}
        </select>
        <input type="search" value={draft} onChange={(e) => setDraft(e.target.value)}
          aria-label={t('admin.requests.list.searchLabel')}
          placeholder={t('admin.requests.list.searchPlaceholder')}
          className="min-h-11 min-w-0 flex-1 basis-56 border rounded-lg px-3 py-2 text-sm" />
      </div>

      {failed ? (
        <div className="rounded-lg bg-critical-50 border border-critical-200 text-critical-600 p-3">
          {t('admin.requests.error.generic')}
        </div>
      ) : loading && !data ? (
        <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>
      ) : rows.length === 0 ? (
        <div className="text-center text-ground-500 mt-8">{t('admin.requests.list.empty')}</div>
      ) : (
        <div className={`space-y-2 max-md:space-y-0 max-md:divide-y max-md:divide-ground-100 ${loading ? 'opacity-60' : ''}`} aria-busy={loading || undefined}>
          {rows.map((r) => (
            <Link key={r.id} href={`/admin/requests/${r.id}`} data-request-row={r.id}
              className="block md:bg-ground-0 md:rounded-xl md:border hover:border-info-300 hover:bg-info-50/40 transition-colors py-3 md:p-4">
              {/* Mobile M8: below md the status goes UNDER the row — beside it, a long Malay or Tamil status (222 px)
                  left the title 70 px and words spilled out of it; and long words wrap anywhere. */}
              <div className="flex items-start justify-between gap-3 max-md:flex-col max-md:gap-1.5">
                <div className="min-w-0 max-md:max-w-full [overflow-wrap:anywhere]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="min-w-0 font-medium text-ground-900 break-words">{r.title}</span>
                    {/* The FINAL classification — what the organisation is charged on. Served. */}
                    <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-ground-100 text-ground-600">{t(kindLabelKey(r.kind))}</span>
                    {r.filed_kind && (
                      <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-caution-50 text-caution-700">
                        {t('admin.requests.kind.filedAs', { kind: t(kindLabelKey(r.filed_kind)) })}
                      </span>
                    )}
                    {r.tags.filter((tag) => TAG[tag]).map((tag) => (
                      <span key={tag} className={`text-[11px] px-1.5 py-0.5 rounded-full ${TAG[tag].tone}`}>
                        {t(TAG[tag].key)}
                      </span>
                    ))}
                  </div>
                  <div className="text-xs text-ground-500 mt-1">
                    {isSuper && r.organisation_name ? `${r.organisation_name} · ` : ''}
                    {t('admin.requests.list.submittedBy', { name: r.submitted_by_name })} · {formatDate(r.created_at)}
                  </div>
                </div>
                <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-semibold max-md:max-w-full ${statusTone(r.status)}`}>
                  {t(statusLabelKey(r.status))}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {data && data.count > 0 && !failed && (
        <>
          <p className="mt-4 text-sm text-ground-500" data-list-showing>
            {t('admin.requests.list.showing', {
              from: String(from), to: String(to), total: String(data.count),
            })}
          </p>
          <Pagination page={data.page} totalPages={data.total_pages} pageSize={data.page_size}
            onPageChange={(page) => setState((s) => (s ? { ...s, page } : s))} />
        </>
      )}
    </div>
  )
}
