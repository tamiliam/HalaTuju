'use client'
// Student spending — the officer's view of what students bought, by SHOP, and the one correction
// that outranks every rung of the sorter.
//
// Access: super / org_admin / admin. ⚠ `finance` is DELIBERATELY ABSENT, unlike the neighbouring
// Payments page: `_b40_scope` promises a finance admin never sees student data beyond the Payments
// allowlist, and this screen carries names beside purchases. The backend refuses it too — this is
// not the fence, only the door.
//
// ⚠ **A SUPER SEES EVERY ORGANISATION HERE (S6, 2026-09-11).** Until then a super was refused
// outright — the owner opened their own console and got "Could not load the spending figures".
// Nothing about that scope is decided in this file: `_spending_admin` resolves it server-side and
// the page renders whatever it is handed. The breadcrumb's organisation is a DISPLAY preference
// and must never become the thing that decides what this page fetches.
//
// ── S6 reorganised this page into three tabs (owner, 2026-09-11) ──────────────────────────────
//
// It was one long scroll: four figures, every shop, every student, the model's recent guesses, the
// wallet faults. The four figures stay ABOVE the tabs, because they describe the whole page and a
// figure that changes when you switch tab is a figure nobody trusts. Under them:
//
//   Shops     — every shop, and the box you correct it in.
//   Students  — who spent what, and the wallet faults (owner, 2026-09-11: a wallet is a fact
//               about a STUDENT, so it belongs beside them, not in a tab about money).
//   Unsorted  — the shops with money we could not place.
//
// ⚠ **"WHAT THE MODEL DECIDED RECENTLY" WAS DELETED HERE (S7), NOT MOVED.** It was this same
// shop data filtered to `ai` within 14 days, rendered READ-ONLY beside a table that can be
// corrected — so a reader found a wrong guess in it and had to scroll up to act. The owner
// asked what action it expected; there wasn't one. Filter the shops table by "how we decided"
// instead, and the decided DATE is now a column. Do not reintroduce it.
//
// ⚠ **THE SHOPS LIST IS DRAWN BY ONE COMPONENT IN BOTH TABS** (`SpendingShops`). Copying it would
// set up the failure `StaffAdmin` already had — a rule fixed in one of two renderings of the same
// row, with nothing failing at the time.

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import PanelTabs, { type PanelTab } from '@/components/admin/PanelTabs'
import SortHeader from '@/components/admin/SortHeader'
import SpendingShops, { rm } from '@/components/admin/SpendingShops'
import TableFrame from '@/components/admin/TableFrame'
import { Pagination } from '@/components/Pagination'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { useProgrammeParam } from '@/lib/programmeScope'
import { formatDate } from '@/lib/formatDate'
import { PAGE_SIZE_OPTIONS, nextSort } from '@/lib/tableView'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import {
  STUDENT_DEFAULT_SORT, STUDENT_SORT_LABEL, filterStudents, shopsWithUnplacedMoney,
  sortStudents, studentFirstDir, type StudentSortKey,
} from '@/lib/spendingTable'
import {
  getSpendingOverview, setSpendingCategory, type SpendingOverview,
} from '@/lib/admin-api'

const TABS: readonly PanelTab<'shops' | 'students' | 'unsorted'>[] = [
  { key: 'shops', labelKey: 'admin.spending.tab.shops' },
  { key: 'students', labelKey: 'admin.spending.tab.students' },
  { key: 'unsorted', labelKey: 'admin.spending.tab.unsorted' },
]
type Tab = (typeof TABS)[number]['key']

export default function SpendingPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = canAccess('/admin/spending', effectiveRole(role))
  // ⚠ WHICH GIFT — from the breadcrumb, sent as an EXPLICIT value the server re-fences on the
  // caller's own organisation (TD-241). It is not an auth context and never becomes one; a
  // client that sent nothing would reach exactly the rows the organisation fence allows.
  // `undefined` when several gifts exist and none is chosen — the scope refuses to guess.
  const programme = useProgrammeParam()

  const [tab, setTab] = useState<Tab>('shops')
  const [data, setData] = useState<SpendingOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState('')

  const load = useCallback(() => {
    if (!token || !allowed) { setLoading(false); return }
    setLoading(true)
    getSpendingOverview(programme, { token })
      .then(setData)
      .catch(() => setError(t('admin.spending.loadFailed')))
      .finally(() => setLoading(false))
    // ⚠ `programme` IS A DEPENDENCY. Switching gift in the breadcrumb must re-read; without
    // it the crumb would say one gift while the table showed another — the exact failure the
    // 2026-09-03 defect produced, arriving from the other direction.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed, programme])

  useEffect(() => { load() }, [load])

  // ⚠ Re-read the whole overview after a correction rather than patching the row in place. One
  // change moves the shop's category, every payment at it, all four figures at the top, and
  // whether the shop still belongs in the Unsorted tab at all; a local patch would leave the
  // headline percentage disagreeing with the table under it.
  async function correct(merchant: string, category: string) {
    if (!token) return
    setSaving(merchant)
    setError('')
    try {
      await setSpendingCategory(merchant, category, programme, { token })
      const fresh = await getSpendingOverview(programme, { token })
      setData(fresh)
    } catch (e) {
      const code = e instanceof Error ? e.message : ''
      const known = ['unknown_merchant', 'unknown_category', 'merchant_required']
      setError(known.includes(code)
        ? t(`admin.spending.error.${code}`)
        : t('admin.spending.saveFailed'))
    } finally {
      setSaving('')
    }
  }

  // ── the student table's own search, sort and page ──
  const { sort: studentSort, setSort: setStudentSort } =
    useSort<StudentSortKey>(STUDENT_DEFAULT_SORT)
  const [studentQuery, setStudentQuery] = useState('')
  const [onlyUnplaced, setOnlyUnplaced] = useState(false)
  const allStudents = data?.students ?? []
  // ⚠ FILTER, then SORT, then PAGE — the same order the shops list uses, for the same reason.
  const shownStudents = filterStudents(allStudents,
                                       { query: studentQuery, onlyUnplaced })
  const students = usePagedRows(
    sortStudents(shownStudents, studentSort.key, studentSort.dir))
  const onStudentSort = (col: StudentSortKey) =>
    setStudentSort(nextSort(studentSort, col, studentFirstDir(col)))
  const studentsFiltered = shownStudents.length !== allStudents.length

  if (role && !allowed) {
    return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const totals = data?.totals
  const categories = data?.categories ?? []
  const merchants = data?.merchants ?? []
  const unplaced = shopsWithUnplacedMoney(merchants)
  const noWallet = data?.wallet_gaps.students_without_wallet ?? []
  const shared = Object.entries(data?.wallet_gaps.shared_wallets ?? {})

  // ⚠ COUNTS OF THE WHOLE LIST, and only once the data has arrived. While `data` is null the
  // counts are `undefined`, which hides the pills — a tab reading "0" before the fetch returns
  // would say "there are none", which is a different claim from "we do not know yet".
  const tabs = TABS.map((tab) => ({
    ...tab,
    count: !data ? undefined
      : tab.key === 'shops' ? merchants.length
        : tab.key === 'students' ? (data.students ?? []).length
          : unplaced.length,
  }))

  return (
    <div>
      <h1 className="text-2xl font-semibold text-ground-900">{t('admin.spending.title')}</h1>
      <p className="mt-1 text-sm text-ground-600">{t('admin.spending.subtitle')}</p>

      {error && <p className="mt-4 text-sm text-critical-600" role="alert">{error}</p>}

      {/* ── the four figures. Every one COMPUTED by the server; none is an estimate.
          ⚠ THEY SIT ABOVE THE TABS ON PURPOSE. They describe the whole page, and a headline that
          changed as you switched tab would be a headline nobody could quote. ── */}
      <dl className="mt-6 grid grid-cols-2 gap-6 border-b border-ground-200 pb-6 md:grid-cols-4"
        data-testid="spending-totals">
        {[
          ['spent', totals ? `RM${rm(totals.spent)}` : '—'],
          ['sorted', totals ? `${totals.placed_pct}%` : '—'],
          ['unsorted', totals ? `RM${rm(totals.unplaced)}` : '—'],
          ['toCheck', totals ? String(totals.merchants_to_check) : '—'],
        ].map(([key, value]) => (
          <div key={key}>
            <dt className="text-[11px] font-semibold uppercase tracking-wider text-ground-500">
              {t(`admin.spending.stat.${key}`)}
            </dt>
            <dd className="mt-1 text-xl font-medium tabular-nums text-ground-900">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-6">
        <PanelTabs tabs={tabs} active={tab} onSelect={setTab}
          ariaLabelKey="admin.spending.tabs.aria" />
      </div>

      {/* ── Shops ── */}
      {tab === 'shops' && (
        <>
          <SpendingShops
            rows={merchants} categories={categories} onCorrect={correct}
            saving={saving} loading={loading}
            emptyKey="admin.spending.empty" labelKey="admin.spending.title"
            testId="merchant"
          />
          <p className="mt-2 text-xs text-ground-500">{t('admin.spending.kept')}</p>
        </>
      )}

      {/* ── Students ── */}
      {tab === 'students' && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <input
              type="search"
              value={studentQuery}
              onChange={(e) => setStudentQuery(e.target.value)}
              placeholder={t('admin.spending.searchStudents')}
              aria-label={t('admin.spending.searchStudents')}
              className="min-w-0 flex-1 rounded-md border border-ground-200 bg-ground-0 px-3 py-1.5 text-sm text-ground-800 placeholder:text-ground-placeholder sm:max-w-xs"
            />
            <label className="flex items-center gap-1.5 text-sm text-ground-700">
              <input type="checkbox" checked={onlyUnplaced}
                onChange={(e) => setOnlyUnplaced(e.target.checked)} />
              {t('admin.spending.filter.onlyUnplaced')}
            </label>
            {studentsFiltered && (
              <span className="text-xs tabular-nums text-ground-500"
                data-testid="student-showing">
                {t('admin.spending.filter.showing', {
                  shown: String(shownStudents.length), total: String(allStudents.length),
                })}
              </span>
            )}
          </div>

          {/* PHONE: one card per student. Four short numeric columns would survive a sideways
              drag, but this is a list of PEOPLE, and the guard's own rule says those get cards. */}
          <div className="space-y-2.5 md:hidden" data-testid="student-cards">
            {students.rows.map((s) => (
              <div key={s.application_id}
                className="rounded-xl border border-ground-200 bg-ground-0 p-3">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-semibold text-ground-900">{s.name}</span>
                  <span className="shrink-0 text-sm font-medium tabular-nums text-ground-900">
                    RM{rm(s.spent)}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ground-600">
                  <span>{t('admin.spending.students.payments')}{' '}
                    <span className="tabular-nums">{s.payments}</span></span>
                  <span>{t('admin.spending.students.unsorted')}{' '}
                    <span className="tabular-nums">RM{rm(s.unplaced)}</span></span>
                </div>
              </div>
            ))}
            {!loading && students.rows.length === 0 && (
              <p className="py-6 text-center text-sm text-ground-400">
                {t('admin.spending.students.empty')}
              </p>
            )}
          </div>

          <TableFrame className="hidden md:block" minWidth={560}
            label={t('admin.spending.students.title')}>
            <table className="w-full text-sm">
              <thead className="bg-ground-50 border-b">
                <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
                  <SortHeader col="name" label={t(STUDENT_SORT_LABEL.name)}
                    sort={studentSort} onSort={onStudentSort} />
                  <SortHeader col="payments" label={t(STUDENT_SORT_LABEL.payments)}
                    sort={studentSort} onSort={onStudentSort} align="right" />
                  <SortHeader col="spent" label={t(STUDENT_SORT_LABEL.spent)}
                    sort={studentSort} onSort={onStudentSort} align="right" />
                  <SortHeader col="unplaced" label={t(STUDENT_SORT_LABEL.unplaced)}
                    sort={studentSort} onSort={onStudentSort} align="right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-ground-100">
                {students.rows.map((s) => (
                  <tr key={s.application_id}>
                    <td className="px-4 py-3 text-ground-900">{s.name}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ground-700">{s.payments}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ground-900">RM{rm(s.spent)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ground-500">RM{rm(s.unplaced)}</td>
                  </tr>
                ))}
                {!loading && students.rows.length === 0 && (
                  <tr><td colSpan={4} className="px-4 py-8 text-center text-ground-400">
                    {t('admin.spending.students.empty')}
                  </td></tr>
                )}
              </tbody>
            </table>
          </TableFrame>

          {students.visible && (
            <div className="mt-3">
              <Pagination
                page={students.page} totalPages={students.totalPages} pageSize={students.pageSize}
                onPageChange={students.setPage}
                pageSizeOptions={PAGE_SIZE_OPTIONS} onPageSizeChange={students.setPageSize}
              />
            </div>
          )}
          {/* ── the wallet faults. ⚠ MOVED HERE FROM THE UNSORTED TAB (owner, 2026-09-11): a
              wallet is a fact about a STUDENT, so it belongs beside the students rather than in
              a tab about money that could not be categorised. The two derivable faults only —
              the third (a wallet matching NO student) is never stored, and the note says so. ── */}
          <h2 className="mt-10 text-lg font-semibold text-ground-900">
            {t('admin.spending.gaps.title')}
          </h2>
          <div className="mt-3 space-y-2 text-sm" data-testid="wallet-gaps">
            {noWallet.length > 0 && (
              <p className="text-ground-700">
                {t('admin.spending.gaps.noWallet')}:{' '}
                <span className="tabular-nums">{noWallet.join(', ')}</span>
              </p>
            )}
            {shared.length > 0 && (
              <p className="text-ground-700">
                {t('admin.spending.gaps.shared')}:{' '}
                <span className="tabular-nums">
                  {shared.map(([wallet, ids]) => `${wallet} (${ids.join(', ')})`).join(' · ')}
                </span>
              </p>
            )}
            {!loading && noWallet.length === 0 && shared.length === 0 && (
              <p className="text-ground-400">{t('admin.spending.gaps.none')}</p>
            )}
            <p className="text-xs text-ground-500">{t('admin.spending.gaps.note')}</p>
          </div>
        </>
      )}

      {/* ── Unsorted: everything that wants a human ── */}
      {tab === 'unsorted' && (
        <>
          <h2 className="text-lg font-semibold text-ground-900">
            {t('admin.spending.unplaced.title')}
          </h2>
          <p className="mt-1 mb-3 text-sm text-ground-600">{t('admin.spending.unplaced.help')}</p>
          <SpendingShops
            rows={unplaced} categories={categories} onCorrect={correct}
            saving={saving} loading={loading}
            emptyKey="admin.spending.unplaced.empty"
            labelKey="admin.spending.unplaced.title"
            testId="unplaced"
          />
          <p className="mt-2 text-xs text-ground-500">{t('admin.spending.kept')}</p>

        </>
      )}
    </div>
  )
}
