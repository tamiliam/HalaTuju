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
//   Students  — who spent what.
//   Unsorted  — the work: shops with money we could not place, the model's recent guesses, and
//               the wallet faults. One tab holding everything that wants a human.
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
import { formatDate } from '@/lib/formatDate'
import { PAGE_SIZE_OPTIONS, nextSort } from '@/lib/tableView'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import {
  STUDENT_DEFAULT_SORT, STUDENT_SORT_LABEL, shopsWithUnplacedMoney, sortStudents, studentFirstDir,
  type StudentSortKey,
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

  const [tab, setTab] = useState<Tab>('shops')
  const [data, setData] = useState<SpendingOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState('')

  const load = useCallback(() => {
    if (!token || !allowed) { setLoading(false); return }
    getSpendingOverview({ token })
      .then(setData)
      .catch(() => setError(t('admin.spending.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed])

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
      await setSpendingCategory(merchant, category, { token })
      const fresh = await getSpendingOverview({ token })
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

  // ── the student table's own sort and page ──
  const { sort: studentSort, setSort: setStudentSort } =
    useSort<StudentSortKey>(STUDENT_DEFAULT_SORT)
  const students = usePagedRows(
    sortStudents(data?.students ?? [], studentSort.key, studentSort.dir))
  const onStudentSort = (col: StudentSortKey) =>
    setStudentSort(nextSort(studentSort, col, studentFirstDir(col)))

  // ── the model's recent guesses get a page of their own ──
  // Live today: 102 of them. An unpaged list of 102 shops below two other blocks is a list nobody
  // reaches the bottom of.
  const decisions = usePagedRows(data?.model_decisions ?? [])

  if (role && !allowed) {
    return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const totals = data?.totals
  const categories = data?.categories ?? []
  const merchants = data?.merchants ?? []
  const unplaced = shopsWithUnplacedMoney(merchants)
  const noWallet = data?.wallet_gaps.students_without_wallet ?? []
  const shared = Object.entries(data?.wallet_gaps.shared_wallets ?? {})

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
        <PanelTabs tabs={TABS} active={tab} onSelect={setTab}
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

          {/* ── what the model decided lately ── */}
          <h2 className="mt-10 text-lg font-semibold text-ground-900">
            {t('admin.spending.model.title')}
          </h2>
          <p className="mt-1 text-sm text-ground-600">{t('admin.spending.model.help')}</p>
          <ul className="mt-3 space-y-1.5" data-testid="model-decisions">
            {decisions.rows.map((d) => (
              <li key={d.merchant} className="flex flex-wrap items-baseline gap-x-3 text-sm">
                <span className="font-medium text-ground-900">{d.merchant}</span>
                <span className="text-ground-600">
                  {categories.find((c) => c.code === d.category)?.label ?? d.category}
                </span>
                {d.decided_at && (
                  <span className="text-xs text-ground-400">{formatDate(d.decided_at.slice(0, 10))}</span>
                )}
              </li>
            ))}
            {!loading && decisions.rows.length === 0 && (
              <li className="text-sm text-ground-400">{t('admin.spending.model.empty')}</li>
            )}
          </ul>
          {decisions.visible && (
            <div className="mt-3">
              <Pagination
                page={decisions.page} totalPages={decisions.totalPages}
                pageSize={decisions.pageSize} onPageChange={decisions.setPage}
                pageSizeOptions={PAGE_SIZE_OPTIONS} onPageSizeChange={decisions.setPageSize}
              />
            </div>
          )}

          {/* ── the two wallet gaps that ARE derivable. The third reaches staff by email. ── */}
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
    </div>
  )
}
