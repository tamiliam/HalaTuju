'use client'

// Organisation → Gift programmes (Sabah S2b, 2026-09-02).
//
// The list of gifts this organisation runs, and the one place a new one is created. Before this,
// a Programme row could not be created anywhere — no endpoint, no screen, not even Django admin —
// so a second gift meant an engineer writing SQL. The owner's acceptance test for the whole arc is
// "Suresh, as org admin, can do everything on his own without any work from me".
//
// ⚠ CREATING A GIFT IS AN ORGANISATION-LEVEL ACT, which is why this page lives under Organisation
// and not under Programme. The Programme group is for working INSIDE one gift; you cannot be
// inside the gift you are about to make.
//
// ⚠ THE FENCE IS THE ENDPOINT. This page renders what the server chose to return, and a cross-org
// id is a 404 there. Nothing here decides who may see what.

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import InfoBox from '@/components/InfoBox'
import {
  getAdminProgrammes, createAdminProgramme, updateAdminProgramme, type AdminProgramme,
} from '@/lib/admin-api'

const CODE_OK = /^[a-z0-9][a-z0-9-]{1,49}$/

export default function AdminProgrammesPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const mayView = canAccess('/admin/organisation/programmes', effectiveRole(role))

  const [rows, setRows] = useState<AdminProgramme[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [nameEn, setNameEn] = useState('')

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      setRows((await getAdminProgrammes({ token })).programmes)
      setError('')
    } catch {
      setError(t('admin.programmes.loadFailed'))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => { if (mayView) void load(); else setLoading(false) }, [mayView, load])

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const errKey = (c?: string) =>
    c === 'bad_code' ? 'badCode'
      : c === 'code_taken' ? 'codeTaken'
        : c === 'name_required' ? 'nameRequired'
          : c === 'has_open_year' ? 'hasOpenYear'
            : c === 'no_org' ? 'noOrg' : 'generic'

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('')
    try {
      await fn()
      await load()
      return true
    } catch (e) {
      setError(t(`admin.programmes.error.${errKey((e as { code?: string })?.code)}`))
      return false
    } finally {
      setBusy(false)
    }
  }

  const create = async () => {
    const ok = await run(() => createAdminProgramme(
      { code: code.trim().toLowerCase(), name_en: nameEn.trim() }, { token: token! }))
    if (ok) { setOpen(false); setCode(''); setNameEn('') }
  }

  const inputCls = 'w-full rounded-lg border border-ground-300 px-3 py-2 text-sm'
    + ' focus:border-brand-shape focus:ring-2 focus:ring-brand-shape outline-none'

  return (
    <div className="max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ground-900">{t('admin.programmes.title')}</h1>
          <p className="mt-1 text-sm text-ground-600">{t('admin.programmes.subtitle')}</p>
        </div>
        <button type="button" onClick={() => { setCode(''); setNameEn(''); setError(''); setOpen(true) }}
          className="shrink-0 rounded-lg bg-brand-fill px-4 py-2.5 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
          + {t('admin.programmes.new')}
        </button>
      </div>

      {error && <div className="mt-4"><InfoBox kind="block">{error}</InfoBox></div>}

      <div className="mt-6 space-y-3">
        {rows.map((p) => (
          <section key={p.id} className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm"
            data-testid={`programme-${p.code}`}>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-ground-900">{p.name_en}</h2>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                p.is_active ? 'bg-positive-100 text-positive-800' : 'bg-ground-100 text-ground-600'}`}>
                {t(p.is_active ? 'admin.programmes.active' : 'admin.programmes.notActive')}
              </span>
            </div>
            <p className="mt-0.5 font-mono text-xs text-ground-400">{p.code}</p>

            <dl className="mt-4 flex flex-wrap gap-x-9 gap-y-3">
              {([
                ['years', String(p.intake_years)],
                ['applications', String(p.applications)],
                // A programme is never "open"; one of its years is. Say which, or say none.
                ['takingApplications', p.open_year === null
                  ? t('admin.programmes.none') : String(p.open_year)],
              ] as const).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-[10px] font-semibold uppercase tracking-wider text-ground-400">
                    {t(`admin.programmes.col.${k}`)}
                  </dt>
                  <dd className="mt-0.5 text-sm font-semibold tabular-nums text-ground-700">{v}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-4 flex items-center justify-end gap-4 border-t border-ground-100 pt-3">
              <Link href={`/admin/programme/years?programme=${p.id}`}
                className="text-sm font-medium text-primary-600 hover:underline">
                {t('admin.programmes.intakeYears')}
              </Link>
              {/* Switching a gift on is deliberate and separate from creating it. Switching one OFF
                  is refused by the server while a year is taking applications — the message says so
                  rather than the button hiding, because hiding it explains nothing. */}
              <button type="button" disabled={busy}
                onClick={() => run(() => updateAdminProgramme(p.id, { is_active: !p.is_active }, { token: token! }))}
                className="text-sm font-medium text-ground-600 hover:text-ground-900 disabled:opacity-50">
                {t(p.is_active ? 'admin.programmes.switchOff' : 'admin.programmes.switchOn')}
              </button>
            </div>
          </section>
        ))}
        {!loading && rows.length === 0 && (
          <p className="rounded-2xl border border-dashed border-ground-300 px-4 py-10 text-center text-sm text-ground-400">
            {t('admin.programmes.empty')}
          </p>
        )}
        {loading && <p className="text-sm text-ground-400">{t('common.loading')}</p>}
      </div>

      <p className="mt-4 text-xs text-ground-500">{t('admin.programmes.durableNote')}</p>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !busy && setOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.programmes.new')}</h2>

            <label htmlFor="p-name" className="mt-4 block text-sm font-medium text-ground-700">
              {t('admin.programmes.field.name')}
            </label>
            <input id="p-name" value={nameEn} onChange={(e) => setNameEn(e.target.value)}
              className={`mt-1 ${inputCls}`} />

            <label htmlFor="p-code" className="mt-4 block text-sm font-medium text-ground-700">
              {t('admin.programmes.field.code')}
            </label>
            <input id="p-code" value={code} onChange={(e) => setCode(e.target.value)}
              className={`mt-1 ${inputCls}`} />
            <p className="mt-1 text-xs text-ground-500">{t('admin.programmes.field.codeHint')}</p>

            <div className="mt-4">
              <InfoBox kind="warning">{t('admin.programmes.codeWarning')}</InfoBox>
            </div>
            {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}

            <div className="mt-5 flex items-center justify-end gap-3">
              <button type="button" onClick={() => setOpen(false)} disabled={busy}
                className="text-sm font-medium text-ground-500 hover:text-ground-700">
                {t('common.cancel')}
              </button>
              <button type="button" onClick={create}
                disabled={busy || !nameEn.trim() || !CODE_OK.test(code.trim().toLowerCase())}
                className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('admin.programmes.create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
